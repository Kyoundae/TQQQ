"""
TQQQ 매수/매도 신호 자동 갱신 + 텔레그램(폰 푸시) 알림 — 순수 파이썬 버전

엑셀/LibreOffice에 의존하지 않고, tqqq_signals.py에 이식한 로직으로
직접 신호를 계산합니다.

동작 순서:
  1. price_history.json에서 마지막 저장된 날짜를 찾는다.
  2. Twelve Data API에서 전체 일봉(최대 5,000개)을 받아 date 기준으로 덮어쓴다.
     (엑셀 Power Query와 동일한 방식 — 과거에 잠정치로 저장된 거래량 등이 자동 보정됨)
  3. 전체 이력(현재 약 4,150여 개 캔들)에 대해 tqqq_signals.compute_signals()로
     매수(BF)/매도(AJ) 신호를 처음부터 다시 계산한다. (4천여 개 캔들 기준
     0.1~0.2초 수준이라 매번 새로 계산해도 충분히 빠르다.)
  4. state.json에 기록된 '마지막으로 알림을 보낸 날짜' 이후 행 중
     신호가 발생한 행을 찾아 텔레그램으로 보낸다.
     (텔레그램 봇 메시지는 폰에 텔레그램 앱이 설치되어 있으면 그대로
      일반 푸시 알림으로 옵니다.)
  5. price_history.json, state.json을 갱신한다.
     (커밋/푸시는 GitHub Actions 워크플로에서 처리)

환경변수 (GitHub Actions Secrets로 주입):
  TWELVEDATA_API_KEY   - https://twelvedata.com/apikey 무료 발급
  TELEGRAM_BOT_TOKEN   - @BotFather 로 생성한 봇 토큰
  TELEGRAM_CHAT_IDS    - 알림을 받을 chat_id 목록 (쉼표로 구분, 예: "111111,222222,333333")
"""

import json
import os
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tqqq_signals import compute_signals

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "price_history.json"
STATE_PATH = ROOT / "state.json"

SYMBOL = "TQQQ"

# 엑셀(Power Query)과 동일하게 매번 전체 이력(최대 5,000개)을 다시 받아 덮어쓴다.
# (예전에는 '새 날짜'만 이어붙여서, 장중/잠정 거래량으로 한 번 저장된 값이
#  영원히 고쳐지지 않아 신호가 엑셀과 어긋났다.)
FULL_OUTPUTSIZE = 5000
MIN_EXPECTED_BARS = 500        # 이보다 적게 오면 API 이상으로 보고 중단
RECHECK_BARS = 5               # 최근 N개 봉은 매번 신호를 다시 검사(보정 후 뒤늦게 생기는 신호 포착)
ET = ZoneInfo("America/New_York")
MARKET_CLOSE_ET = dtime(16, 15)  # 이 시각 전의 '오늘' 봉은 미완성으로 보고 제외

SIGNAL_LABELS = {
    "3X매수": ("매수", "3X매수 — 2년 최대 거래량 + RSI 과매도권 진입"),
    "찐쌍바닥": ("매수", "쌍바닥 확인 — 저점 두 번 지지 후 반등"),
    "매도": ("매도", "RSI 약세 다이버전스 매도 신호"),
    "쌍고점": ("매도", "쌍고점 확인 — 고점 두 번 저항 후 하락 전환"),
}


def log(msg):
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def load_history():
    if not HISTORY_PATH.exists():
        raise FileNotFoundError(f"{HISTORY_PATH} 가 없습니다. 초기 이력 파일이 필요합니다.")
    return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))


def save_history(rows):
    HISTORY_PATH.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"last_notified_date": None}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def fetch_all_bars(api_key, now_et=None):
    """Twelve Data에서 전체 일봉(최대 5,000개)을 받아 date 오름차순 리스트로 반환.

    엑셀 Power Query와 같은 요청이다. 아직 장이 끝나지 않은 '오늘' 봉
    (미국 동부시간 기준)은 거래량이 잠정치라 제외한다.
    """
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": "1day",
        "outputsize": FULL_OUTPUTSIZE,
        "apikey": api_key,
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data API 오류: {data.get('message')}")

    now_et = now_et or datetime.now(ET)
    bars = []
    skipped_today = None
    for row in data.get("values", []):
        d = datetime.strptime(row["datetime"], "%Y-%m-%d").date()
        if d == now_et.date() and now_et.time() < MARKET_CLOSE_ET and now_et.weekday() < 5:
            skipped_today = d
            continue
        bars.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(float(row["volume"])),
        })
    if skipped_today:
        log(f"장 마감 전 봉({skipped_today}) 제외")
    bars.sort(key=lambda b: b["date"])
    if len(bars) < MIN_EXPECTED_BARS:
        raise RuntimeError(
            f"API가 {len(bars)}개 봉만 반환했습니다(최소 {MIN_EXPECTED_BARS}개 필요). 저장하지 않고 중단합니다."
        )
    return bars


def merge_bars(history, new_bars):
    """date 기준으로 병합: API에 있는 날짜는 최신 값으로 덮어쓰고, 없는 옛 날짜는 유지.
    반환: (병합된 리스트, 추가된 날짜 수, 값이 바뀐 날짜 목록)"""
    by_date = {r["date"]: r for r in history}
    added, changed = 0, []
    for b in new_bars:
        old = by_date.get(b["date"])
        if old is None:
            added += 1
        elif any(old[k] != b[k] for k in ("open", "high", "low", "close", "volume")):
            changed.append(b["date"])
        by_date[b["date"]] = b
    merged = [by_date[d] for d in sorted(by_date)]
    return merged, added, changed


def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }, timeout=15)
    if not resp.ok:
        # 특정 chat_id 하나가 실패해도(예: 사용자가 봇을 차단) 전체가 멈추지
        # 않도록 로그만 남기고 계속 진행한다.
        log(f"  ! chat_id {chat_id} 발송 실패: {resp.status_code} {resp.text[:200]}")
        return False
    return True


def send_to_all(token, chat_ids, text):
    ok = 0
    for cid in chat_ids:
        if send_telegram(token, cid.strip(), text):
            ok += 1
        time.sleep(0.3)
    return ok


def build_message(date_str, tag, close):
    side, desc = SIGNAL_LABELS.get(tag, ("신호", tag))
    emoji = "🔺" if side == "매수" else "🔻"
    return (
        f"{emoji} <b>TQQQ {side} 신호 발생</b>\n"
        f"유형: {tag}\n"
        f"{desc}\n"
        f"날짜: {date_str}\n"
        f"종가: ${close:,.2f}"
    )


def main():
    api_key = os.environ.get("TWELVEDATA_API_KEY")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_ids_raw = os.environ.get("TELEGRAM_CHAT_IDS")
    if not all([api_key, bot_token, chat_ids_raw]):
        log("환경변수(TWELVEDATA_API_KEY / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_IDS)가 누락되었습니다.")
        sys.exit(1)
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]
    log(f"알림 수신 대상: {len(chat_ids)}명")

    history = load_history()
    last_date_str = history[-1]["date"] if history else None
    log(f"보유 이력 마지막 날짜: {last_date_str} (총 {len(history)}건)")

    new_bars = fetch_all_bars(api_key)
    history, added, changed = merge_bars(history, new_bars)
    log(f"시세 병합 완료: 신규 {added}건, 값 보정 {len(changed)}건 (최신 {history[-1]['date']})")
    if changed:
        log(f"  보정된 날짜(최근 10개): {', '.join(changed[-10:])}")

    dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in history]
    opens = [r["open"] for r in history]
    highs = [r["high"] for r in history]
    lows = [r["low"] for r in history]
    closes = [r["close"] for r in history]
    volumes = [r["volume"] for r in history]

    t0 = time.time()
    results = compute_signals(dates, opens, highs, lows, closes, volumes)
    log(f"신호 재계산 완료 ({len(results)}건, {time.time()-t0:.2f}s)")

    state = load_state()
    window_start = max(0, len(results) - RECHECK_BARS)

    def keys_of(r):
        d = r["date"].strftime("%Y-%m-%d")
        return [f"{d}|{tag}" for tag in (r["buy"], r["sell"]) if tag and tag in SIGNAL_LABELS]

    if "notified" in state:
        notified = set(state["notified"])
    else:
        # 구버전 state.json(last_notified_date만 있음) 마이그레이션:
        # 최근 검사 구간 '이전'의 신호는 이미 처리된 것으로 보고, 구간 안의 신호는 한 번 다시 확인한다.
        notified = {k for r in results[:window_start] for k in keys_of(r)}
        log("state 마이그레이션: notified 목록 새로 생성")

    sent = 0
    for r in results[window_start:]:
        for tag in (r["buy"], r["sell"]):
            if not tag or tag not in SIGNAL_LABELS:
                continue
            key = f"{r['date'].strftime('%Y-%m-%d')}|{tag}"
            if key in notified:
                continue
            msg = build_message(r["date"].strftime("%Y-%m-%d"), tag, r["close"])
            ok_count = send_to_all(bot_token, chat_ids, msg)
            log(f"알림 발송: {r['date'].date()} {tag} ({ok_count}/{len(chat_ids)}명 성공)")
            if ok_count > 0:
                notified.add(key)   # 한 명도 못 받았으면 다음 실행에서 재시도
            sent += 1

    save_history(history)
    state["last_notified_date"] = history[-1]["date"]
    cutoff = (datetime.strptime(history[-1]["date"], "%Y-%m-%d").date().toordinal() - 60)
    state["notified"] = sorted(k for k in notified
                               if datetime.strptime(k.split("|")[0], "%Y-%m-%d").date().toordinal() >= cutoff)
    save_state(state)

    log(f"완료. 발송된 알림 {sent}건.")


if __name__ == "__main__":
    main()
