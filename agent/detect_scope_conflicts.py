"""
Real, mechanical, ADVISORY check for the content-conflict dimension of
parallel-fork dispatch. External research on 142k+ real agent-authored
PRs found cross-agent conflict rates roughly double intra-agent
sequential rates, with content conflicts (57.6%) and add/add -- two
agents independently creating something at the same path (15.1%) -- the
two largest categories. This project has hit the add/add case twice for
real: the TESTING_ARCHITECTURE_V1.md section-S/section-S collision
(Sprint 3) and the ACT-015 id collision (Sprint 4).

Deliberately ADVISORY, not a hard gate: this project's own BL-030 fork
found and fixed a real bug in code adjacent to (not inside) its declared
scope this same sprint -- a rigid exclusive-lock model would have blocked
a genuine, valuable find. This script reports overlaps for the parent
session's own merge-ordering judgment; it does not block a fork from
touching anything.

Usage (run BEFORE merging, once you know or suspect which worktree
branches are in flight):
    python agent/detect_scope_conflicts.py <base-ref> <branch1> <branch2> [...]

Reports, per pair of branches, the real files both branches' diffs (from
base-ref) touch -- computed via two real `git diff --name-only` calls,
never guessed from task descriptions.
"""

import subprocess
import sys
from itertools import combinations
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(args: list[str]) -> str:
    result = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    return result.stdout


def files_changed_since(base: str, branch: str) -> set[str]:
    out = _run(["git", "diff", "--name-only", f"{base}...{branch}"])
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip()}


def detect(base: str, branches: list[str]) -> dict:
    per_branch = {}
    for b in branches:
        per_branch[b] = files_changed_since(base, b)

    overlaps = []
    for a, b in combinations(branches, 2):
        shared = per_branch[a] & per_branch[b]
        if shared:
            overlaps.append({"branches": [a, b], "shared_files": sorted(shared)})

    return {
        "base": base,
        "branches_checked": branches,
        "files_per_branch": {b: sorted(files) for b, files in per_branch.items()},
        "has_overlaps": len(overlaps) > 0,
        "overlaps": overlaps,
        "note": "advisory only -- an overlap means merge order/conflict-resolution needs real attention, not that either branch's work is wrong",
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3:
        print("usage: python agent/detect_scope_conflicts.py <base-ref> <branch1> <branch2> [<branch3> ...]")
        sys.exit(2)

    import json
    base, branches = args[0], args[1:]
    report = detect(base, branches)
    print(json.dumps(report, indent=2))
    sys.exit(1 if report["has_overlaps"] else 0)
