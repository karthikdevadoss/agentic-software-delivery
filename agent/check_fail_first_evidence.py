"""
BL-119 (Sprint 27, SI audit BK-13): report which tests have a real,
recorded fail-first observation and which don't -- making this project's
"a new test is not trusted until observed failing" rule mechanical
instead of living only in prose/commit messages.

HONESTY LIMIT, stated once: this is a REPORT, not a gate. It does not
and cannot retroactively know whether an existing test was ever observed
failing before this registry existed -- that evidence either was written
down at the time (almost never, historically) or it is genuinely lost.
Every test without an entry in agent/fail_first_evidence.json is reported
NO_RECORD, which does not mean "this test is wrong" -- it means "no
mechanical proof exists that it was ever seen to fail for the right
reason." Entries are added going forward, the same way
docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml is: at the moment the real
observation happens, never backfilled from a guess.

Cross-references agent/test_oracle_manifest.json (BL-116) for the full
list of real test ids, so this reuses one real enumeration rather than
inventing a second one.

Run:  python agent/check_fail_first_evidence.py --summary
      python agent/check_fail_first_evidence.py --list-missing   (first 20)
"""

import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
EVIDENCE_PATH = AGENT_DIR / "fail_first_evidence.json"
MANIFEST_PATH = AGENT_DIR / "test_oracle_manifest.json"


def _test_id(t: dict) -> str:
    cls = t.get("class") or ""
    return f"{t['file']}::{cls}::{t['test']}" if cls else f"{t['file']}::{t['test']}"


def load_registry() -> dict:
    if not EVIDENCE_PATH.exists():
        return {"entries": {}}
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def load_manifest() -> list:
    if not MANIFEST_PATH.exists():
        return []
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["tests"]


def build_report() -> dict:
    registry = load_registry()
    manifest = load_manifest()
    entries = registry.get("entries", {})

    has_record = []
    no_record = []
    for t in manifest:
        tid = _test_id(t)
        if tid in entries:
            has_record.append(tid)
        else:
            no_record.append(tid)

    # Entries in the registry that no longer match a real test (renamed/
    # deleted) are a real data-integrity problem, surfaced rather than
    # silently ignored.
    manifest_ids = {_test_id(t) for t in manifest}
    stale_entries = sorted(set(entries) - manifest_ids)

    return {
        "total_tests": len(manifest),
        "has_fail_first_record": len(has_record),
        "no_fail_first_record": len(no_record),
        "coverage_pct": round(100 * len(has_record) / len(manifest), 2) if manifest else None,
        "no_record_ids": sorted(no_record),
        "stale_registry_entries": stale_entries,
    }


def main(argv) -> int:
    report = build_report()
    if "--list-missing" in argv:
        for tid in report["no_record_ids"][:20]:
            print(tid)
        remaining = report["no_fail_first_record"] - 20
        if remaining > 0:
            print(f"... and {remaining} more")
        return 0

    print(f"Total real tests (from agent/test_oracle_manifest.json): {report['total_tests']}")
    print(f"  HAS a recorded fail-first observation: {report['has_fail_first_record']}")
    print(f"  NO recorded fail-first observation:    {report['no_fail_first_record']}")
    print(f"  Coverage: {report['coverage_pct']}%")
    if report["stale_registry_entries"]:
        print(f"WARNING: {len(report['stale_registry_entries'])} registry entries no longer match a real test (renamed/deleted?):")
        for tid in report["stale_registry_entries"]:
            print(f"  - {tid}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
