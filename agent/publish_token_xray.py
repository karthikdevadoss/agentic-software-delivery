"""
Publishes agent/web/token-xray.json from the measured token experiment in
docs/evidence/token-xray-2026-10-21/ (results.json + headline.json, which
analyze.py in that folder rebuilds from the raw calls_run*.jsonl).

WHY THIS EXISTS
The home page and /tokens quote numbers (4.5x the tokens, 4.2x the cost,
56,188 vs 12,601 ...). Owner rule, 2026-10-21: no invented numbers; every
number on the site must come from data in the repository. This script is the
one place those numbers are derived, and test_token_xray.py checks that the
published JSON is current and that the pages quote only these values.

Run:  python agent/publish_token_xray.py          # writes the JSON
      python agent/publish_token_xray.py --check  # exit 1 if it is stale
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs" / "evidence" / "token-xray-2026-10-21"
OUT = Path(__file__).resolve().parent / "web" / "token-xray.json"

# Display order and plain-English labels for the six measured tasks.
TASKS = [
    ("trip", "Plan a family trip", "Family trip"),
    ("reply", "Reply to an unhappy customer", "Customer reply"),
    ("doc", "Question about a long document", "Long document"),
    ("suppliers", "Compare 3 supplier offers", "Supplier offers"),
    ("formula", "Fix a spreadsheet formula", "Spreadsheet formula"),
    ("longchat", "10 small tasks in one day", "10 small tasks"),
]


def multiple(x: float) -> str:
    """4.459 -> '4.5x'; 161.43 -> '161x' (whole numbers once it is large)."""
    return f"{x:.0f}x" if x >= 100 else f"{x:.1f}x"


def build() -> dict:
    results = json.loads((EVIDENCE / "results.json").read_text(encoding="utf-8"))
    head = json.loads((EVIDENCE / "headline.json").read_text(encoding="utf-8"))
    summary = results["summary"]
    tasks = []
    for key, label, short in TASKS:
        s = summary[key]
        tasks.append({
            "id": key,
            "label": label,
            "short_label": short,
            "wrong_tokens": int(s["wrong"]["proc"]),
            "right_tokens": int(s["right"]["proc"]),
            "token_multiple": multiple(s["x_tokens"]),
            "cost_multiple": multiple(s["x_nocache"]),
            "wrong_model": s["wrong"]["model"],
            "right_model": s["right"]["model"],
            "runs": s["wrong"]["n"],
        })
    if sum(t["wrong_tokens"] for t in tasks) != head["TW"] or sum(t["right_tokens"] for t in tasks) != head["TR"]:
        raise SystemExit("headline.json totals do not match the per-task results")
    token_multiples = [summary[k]["x_tokens"] for k, _, _ in TASKS]
    return {
        "source": "docs/evidence/token-xray-2026-10-21 (results.json, headline.json)",
        "measured_on": "2026-10-21",
        "provider": "Anthropic Claude only",
        "runs_per_task": 3,
        "statistic": "median of 3 runs",
        "model_calls": results["ncalls"],
        "cost_basis": "Anthropic list price, no caching",
        "totals": {
            "wrong_tokens": head["TW"],
            "right_tokens": head["TR"],
            "wrong_usd": round(head["CW"], 3),
            "right_usd": round(head["CR"], 3),
            "token_multiple": multiple(head["xt"]),
            "cost_multiple": multiple(head["xc"]),
        },
        "token_multiple_range": [multiple(min(token_multiples)), multiple(max(token_multiples))],
        "big_model_small_task_cost_multiple": multiple(summary["formula"]["x_nocache"]),
        "growing_chat_40_tasks_estimate": multiple(head["proj40"]),
        "tasks": tasks,
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main(argv) -> int:
    text = render(build())
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != text:
            print(f"{OUT} is stale: run python agent/publish_token_xray.py")
            return 1
        print("token-xray.json is current")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
