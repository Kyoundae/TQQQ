"""
검증용 스크립트: price_history.json에 저장된 이력으로 계산한 신호가
과거 원본 엑셀 결과와 일치하는지 확인합니다. (개발/디버깅용)

사용법: python3 scripts/validate.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tqqq_signals import compute_signals

ROOT = Path(__file__).resolve().parent.parent


def main():
    history = json.loads((ROOT / "price_history.json").read_text(encoding="utf-8"))
    dates = [datetime.strptime(r["date"], "%Y-%m-%d") for r in history]
    opens = [r["open"] for r in history]
    highs = [r["high"] for r in history]
    lows = [r["low"] for r in history]
    closes = [r["close"] for r in history]
    volumes = [r["volume"] for r in history]

    results = compute_signals(dates, opens, highs, lows, closes, volumes)

    buy_count = sum(1 for r in results if r["buy"])
    sell_count = sum(1 for r in results if r["sell"])
    print(f"전체 캔들: {len(results)}")
    print(f"매수신호: {buy_count}건")
    print(f"매도신호: {sell_count}건")
    print()
    print("최근 신호 10건:")
    recent = [r for r in results if r["buy"] or r["sell"]][-10:]
    for r in recent:
        tag = r["buy"] or r["sell"]
        side = "매수" if r["buy"] else "매도"
        print(f"  {r['date'].date()}  {side:>2}  {tag:<6}  종가 ${r['close']:.2f}")


if __name__ == "__main__":
    main()
