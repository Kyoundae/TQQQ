"""
TQQQ 매수/매도 신호 자동 갱신 + 텔레그램(폰 푸시) 알림 — 순수 파이썬 버전

엑셀/LibreOffice에 의존하지 않고, tqqq_signals.py에 이식한 로직으로
직접 신호를 계산합니다.

동작 순서:
  1. price_history.json에서 마지막 저장된 날짜를 찾는다.
  2. Twelve Data API에서 그 이후의 신규 일봉을 가져와 이어붙인다.
  3. 전체 이력(현재 약 4,150여 개 캔들)에 대해 tqqq_signals.compute_signals()로
     매수(BC)/매도(AI) 신호를 처음부터 다시 계산한다. (4천여 개 캔들 기준
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
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tqqq_signals import compute_signals

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "price_history.json"
STATE_PATH = ROOT / "state.json"

SYMBOL = "TQQQ"

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


def fetch_new_bars(api_key, since_date_str):
    """Twelve Data에서 since_date 다음 날부터 오늘까지의 일봉을 가져온다."""
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": SYMBOL,
        "interval": "1day",
        "outputsize": 30,
        "apikey": api_key,
        "format": "JSON",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Twelve Data API 오류: {data.get('message')}")

    since_date = datetime.strptime(since_date_str, "%Y-%m-%d") if since_date_str else None
    values = data.get("values", [])
    bars = []
    for row in values:
        d = datetime.strptime(row["datetime"], "%Y-%m-%d")
        if since_date is not None and d.date() <= since_date.date():
            continue
        bars.append({
            "date": d.strftime("%Y-%m-%d"),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(float(row["volume"])),
        })
    bars.sort(key=lambda b: b["date"])
    return bars


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

    new_bars = fetch_new_bars(api_key, last_date_str)
    if not new_bars:
        log("새로운 시세 데이터가 없습니다. 종료.")
        return

    log(f"신규 시세 {len(new_bars)}건: {new_bars[0]['date']} ~ {new_bars[-1]['date']}")
    history.extend(new_bars)

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
    last_notified = state.get("last_notified_date")
    last_notified_dt = datetime.strptime(last_notified, "%Y-%m-%d") if last_notified else None

    sent = 0
    for r in results:
        if last_notified_dt is not None and r["date"] <= last_notified_dt:
            continue
        for tag in (r["buy"], r["sell"]):
            if tag and tag in SIGNAL_LABELS:
                msg = build_message(r["date"].strftime("%Y-%m-%d"), tag, r["close"])
                ok_count = send_to_all(bot_token, chat_ids, msg)
                log(f"알림 발송: {r['date'].date()} {tag} ({ok_count}/{len(chat_ids)}명 성공)")
                sent += 1

    save_history(history)
    state["last_notified_date"] = history[-1]["date"]
    save_state(state)

    log(f"완료. 발송된 알림 {sent}건.")


if __name__ == "__main__":
    main()
