"""
app_data.json 생성 — TQQQ 매매신호 앱(HTML/PWA)이 매번 열릴 때 fetch 해가는
데이터 파일을 만듭니다.

price_history.json(원시 시세)을 읽어 tqqq_signals.compute_signals()로
매수/매도 신호 + 볼린저밴드 + 엔벨로프 + MA200까지 전부 계산한 뒤,
앱이 바로 쓸 수 있는 축약된 필드명(d,o,h,l,c,v,buy,sell,bbu,bbl,eu,el,ma200)
으로 저장합니다.

update_and_notify.py 실행 직후에 이어서 호출되며, 결과 파일은 GitHub Actions
워크플로가 그대로 커밋합니다. 저장소가 Public이면 아래 주소로 브라우저에서
바로 fetch 가능합니다:

    https://raw.githubusercontent.com/<사용자명>/<저장소명>/main/app_data.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tqqq_signals import compute_signals

ROOT = Path(__file__).resolve().parent.parent
HISTORY_PATH = ROOT / "price_history.json"
APP_DATA_PATH = ROOT / "data.json"


def r(v, nd=4):
    return round(v, nd) if isinstance(v, (int, float)) else v


def main():
    history = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    dates = [datetime.strptime(row["date"], "%Y-%m-%d") for row in history]
    opens = [row["open"] for row in history]
    highs = [row["high"] for row in history]
    lows = [row["low"] for row in history]
    closes = [row["close"] for row in history]
    volumes = [row["volume"] for row in history]

    results = compute_signals(dates, opens, highs, lows, closes, volumes)

    app_rows = []
    for res in results:
        row = {
            "d": res["date"].strftime("%Y-%m-%d"),
            "o": r(res["open"]),
            "h": r(res["high"]),
            "l": r(res["low"]),
            "c": r(res["close"]),
            "v": res["volume"],
        }
        if res["buy"]:
            row["buy"] = res["buy"]
        if res["sell"]:
            row["sell"] = res["sell"]
        if res["bb_upper"] is not None:
            row["bbu"] = r(res["bb_upper"])
        if res["bb_lower"] is not None:
            row["bbl"] = r(res["bb_lower"])
        if res["env_upper"] is not None:
            row["eu"] = r(res["env_upper"])
        if res["env_lower"] is not None:
            row["el"] = r(res["env_lower"])
        if res["ma200"] is not None:
            row["ma200"] = r(res["ma200"])
        if res["rsi"] is not None:
            row["rsi"] = r(res["rsi"], 2)
        if res["regime"] is not None:
            row["regime"] = res["regime"]  # "bull" / "bear"
        app_rows.append(row)

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_date": app_rows[-1]["d"] if app_rows else None,
        "rows": app_rows,
    }

    APP_DATA_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    print(f"data.json 생성 완료: {len(app_rows)}행, 마지막 날짜 {payload['last_date']}")


if __name__ == "__main__":
    main()
