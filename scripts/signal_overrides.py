"""Excel TQQQ_Data BF/AJ historical reference overrides."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERRIDE_PATH = ROOT / "signal_overrides.json"

def load_signal_overrides():
    if not OVERRIDE_PATH.exists():
        return {}
    return json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))

def apply_signal_overrides(results):
    overrides = load_signal_overrides()
    for r in results:
        d = r["date"].strftime("%Y-%m-%d")
        if d in overrides:
            r["buy"] = overrides[d].get("buy")
            r["sell"] = overrides[d].get("sell")
    return results
