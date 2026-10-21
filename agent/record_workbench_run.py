"""
Records one real public Workbench click into agent/web/workbench-recorded-run.json.

WHY THIS EXISTS
2026-10-21: the old "verified run" the site pointed to (a ledger run whose goal
was a typo'd test string, with no tokens captured) was not something to show
visitors. The Workbench now shows a recorded run instead, and falls back to it
when a live click cannot run. This script makes that recording reproducible:
it POSTs one catalogue example to a running server exactly as the browser
does and saves the server's response unchanged, plus when and how it was taken.
Nothing in the response is edited except the one-time preview id, which
expires with the server process.

Run (against a local server you started yourself):
    python agent/record_workbench_run.py --base-url http://127.0.0.1:8477
"""

import argparse
import datetime
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "web" / "workbench-recorded-run.json"
DEFAULT_REQUIREMENT = 'Change the footer text to "Built with care"'


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--requirement", default=DEFAULT_REQUIREMENT)
    args = ap.parse_args(argv)

    body = json.dumps({"requirement": args.requirement}).encode()
    req = urllib.request.Request(args.base_url.rstrip("/") + "/api/trainer/runs", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    if data.get("mode") != "sandbox" or (data.get("result") or {}).get("status") != "COMPLETED":
        print("Not a completed one-click run; nothing saved:\n" + json.dumps(data, indent=1))
        return 1
    data["result"]["preview_id"] = None
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parent).stdout.strip()
    record = {
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "recorded_how": f"one real POST /api/trainer/runs, as a visitor click, on commit {commit}",
        "request": {"requirement": args.requirement},
        "response": data,
    }
    OUT.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
