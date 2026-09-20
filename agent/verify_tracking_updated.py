"""
Real, mechanical gate for a rule that had already failed FOUR times as a
written instruction before this script existed (Sprint 4: BL-026/ACT-011,
BL-028/ACT-005, and BL-030's ACT-002 test file were all real work shipped
by an earlier commit that never updated docs/ACTION_QUEUE.json or
docs/BACKLOG.json to reflect it -- discovered only when a later sprint
re-proposed the same "new" work as a duplicate; then BL-033 itself did
the exact same thing a fourth time in the same sprint that diagnosed the
first three). Restating "update the tracking doc" as a rule again had no
reason to work a fifth time -- so this checks it instead of asking.

A commit "claims resolution" when its message either:
  - starts with an item id prefix, e.g. "BL-033: ..." / "ACT-014: ...", or
  - contains "Closes ACT-NNN" / "Resolves BL-NNN" (case-insensitive) anywhere.

Two checks, not one -- the first alone is provably too weak (real
finding, same sprint: BL-033's own "resolving" commit DID touch
docs/BACKLOG.json, just never actually flipped BL-033's own status field
while editing other things in the same file -- a file-touched check would
have reported this clean, which is exactly wrong):
  1. the commit must touch docs/BACKLOG.json or docs/ACTION_QUEUE.json, AND
  2. the CURRENT (HEAD) state of the doc must show the referenced item
     actually resolved (BL-*: status == "done"; ACT-*: status in
     {"resolved", "verified"}) -- checked against HEAD, not the commit
     itself, so a later merge that silently drops the flip is also caught.

Usage:
    python agent/verify_tracking_updated.py <since-ref> [<until-ref>]
    (defaults: since=origin/master, until=HEAD)

Exits 0 if every resolution-claiming commit in range touched a tracking
doc; exits 1 and lists exactly which commit(s) didn't otherwise.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKING_DOCS = {"docs/BACKLOG.json", "docs/ACTION_QUEUE.json"}

ID_PREFIX_RE = re.compile(r"^\s*((?:BL|ACT)-\d+)\s*[:+]", re.IGNORECASE)
CLOSES_RE = re.compile(r"\b(?:closes|resolves|fixes)\s+((?:BL|ACT)-\d+)", re.IGNORECASE)


def _run(args: list[str]) -> str:
    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout


def claims_resolution(subject: str) -> list[str]:
    ids = []
    m = ID_PREFIX_RE.match(subject)
    if m:
        ids.append(m.group(1).upper())
    for m in CLOSES_RE.finditer(subject):
        ids.append(m.group(1).upper())
    seen = set()
    return [i for i in ids if not (i in seen or seen.add(i))]


def files_touched(commit_sha: str) -> set[str]:
    out = _run(["git", "show", "--name-only", "--format=", commit_sha])
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}


def _item_status_at(ref: str, item_id: str) -> str | None:
    """Real current status of item_id in whichever tracking doc it belongs
    to (BL-*/AEQ-* -> BACKLOG.json, ACT-* -> ACTION_QUEUE.json), read at
    `ref` (normally HEAD) -- never at the commit that claimed resolution,
    since a later merge can silently drop the change."""
    doc = "docs/ACTION_QUEUE.json" if item_id.upper().startswith("ACT-") else "docs/BACKLOG.json"
    raw = _run(["git", "show", f"{ref}:{doc}"])
    if not raw.strip():
        return None
    import json
    data = json.loads(raw)
    for it in data.get("items", []):
        if it.get("id", "").upper() == item_id.upper():
            return it.get("status")
    return None


def _is_resolved(item_id: str, status: str | None) -> bool:
    if status is None:
        return False
    if item_id.upper().startswith("ACT-"):
        return status in ("resolved", "verified")
    return status == "done"


def verify(since: str = "origin/master", until: str = "HEAD") -> dict:
    log = _run(["git", "log", "--format=%H\t%s", f"{since}..{until}"])
    violations = []
    checked = 0
    for line in log.splitlines():
        if not line.strip():
            continue
        sha, _, subject = line.partition("\t")
        ids = claims_resolution(subject)
        if not ids:
            continue
        checked += 1
        touched = files_touched(sha)
        touched_tracking_doc = bool(touched & TRACKING_DOCS)

        unresolved_ids = []
        for item_id in ids:
            status = _item_status_at(until, item_id)
            if not _is_resolved(item_id, status):
                unresolved_ids.append({"id": item_id, "current_status_at_head": status})

        if not touched_tracking_doc or unresolved_ids:
            violations.append({
                "commit": sha[:7], "subject": subject, "claims": ids,
                "touched_tracking_doc_in_same_commit": touched_tracking_doc,
                "files_touched": sorted(touched),
                "not_actually_resolved_at_head": unresolved_ids,
            })

    return {
        "range": f"{since}..{until}",
        "resolution_claiming_commits_checked": checked,
        "clean": len(violations) == 0,
        "violations": violations,
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    since = args[0] if len(args) >= 1 else "origin/master"
    until = args[1] if len(args) >= 2 else "HEAD"

    import json
    report = verify(since, until)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["clean"] else 1)
