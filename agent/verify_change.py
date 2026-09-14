"""
Testing & Verification Architecture V1 — the selective regression engine
(docs/TESTING_ARCHITECTURE_V1.md §D/§E). "verify-change": inspect the
real diff, classify risk/blast radius, decide and print a test plan
BEFORE running anything, execute it, preserve machine-readable evidence,
and return a real exit code.

Deliberately built as a thin orchestrator over agent/change_risk.py,
agent/test_impact_analysis.py, and the exact same real commands
agent/dev_check.py already wraps (mvnw test, python -m unittest, node
*.js) — no new test-execution mechanism, no shell=True, no fabricated
success.

Usage (from the repository root):
    python agent/verify_change.py                 # working-tree changes (staged+unstaged+untracked)
    python agent/verify_change.py --base origin/master   # changes vs. a base ref (for CI/PR use)
    python agent/verify_change.py --dry-run        # print the plan only, run nothing
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
APP_DIR = REPO_ROOT / "app"
EVIDENCE_DIR = AGENT_DIR / ".verify_change_evidence"

sys.path.insert(0, str(AGENT_DIR))
import change_risk  # noqa: E402
import test_impact_analysis as tia  # noqa: E402

ALWAYS_ON_SMOKE_JAVA = ["CustomerApplicationTests"]


def _git_changed_paths(base: str = None) -> list:
    """Real changed-file list, never a guess. `base` given -> a real
    merge-base diff (`git diff --name-only base...HEAD`, the right choice
    for "what did this branch actually change relative to where it
    forked," used in CI/PR contexts). No `base` -> the local dev-loop
    default: everything different from HEAD (staged + unstaged) plus
    untracked files, i.e. "what have I actually changed right now.\""""
    if base:
        out = subprocess.run(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        ).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]

    tracked = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    paths = set(line.strip() for line in tracked.splitlines() if line.strip())
    for line in status.splitlines():
        if not line.strip():
            continue
        # porcelain format: "XY path" (or "XY orig -> path" for renames)
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.add(path)
    return sorted(paths)


def _run(argv, cwd) -> dict:
    print(f"$ {' '.join(argv)}   (cwd={cwd})")
    started = time.monotonic()
    result = subprocess.run(argv, cwd=str(cwd))
    duration = round(time.monotonic() - started, 1)
    return {"argv": argv, "cwd": str(cwd), "exit_code": result.returncode, "duration_seconds": duration}


def _mvnw_test(test_classes=None) -> dict:
    mvnw = "mvnw.cmd" if sys.platform == "win32" else "mvnw"
    argv = [str(APP_DIR / mvnw), "test"]
    if test_classes:
        argv.append(f"-Dtest={','.join(test_classes)}")
    return _run(argv, APP_DIR)


def build_plan(paths, dry_run_only=False):
    selection = tia.analyze(paths)
    return selection


def print_plan(paths, selection: tia.ImpactSelection):
    print("=" * 70)
    print("VERIFY-CHANGE -- selected test plan")
    print("=" * 70)
    print(f"Changed files ({len(paths)}):")
    for p in paths:
        print(f"  - {p}")
    c = selection.classification
    print(f"\nOverall classification: risk={c.risk}  blast_radius={c.blast_radius}")
    for fc in c.files:
        print(f"  {fc.path}: risk={fc.risk} blast_radius={fc.blast_radius} ({fc.label})")

    if selection.fail_closed:
        print(f"\nFAIL CLOSED: {selection.fail_closed_reason}")
        print("-> running the full regression across every language, not a partial selection.")
    else:
        print("\nSelected:")
        if selection.java_tests:
            shown = "ALL Java tests (mvnw test)" if selection.java_tests == [tia.ALL_JAVA_MODULE_TESTS] else selection.java_tests
            print(f"  Java:       {shown}")
        else:
            print("  Java:       (none -- no impacted Java test found)")
        if selection.playwright_specs:
            print(f"  Playwright: {selection.playwright_specs}")
        print("\nWhy:")
        for r in selection.reasons:
            print(f"  - {r}")

    if selection.skipped:
        print("\nIntentionally skipped:")
        for s in selection.skipped:
            print(f"  - {s}")
    print("=" * 70)


def execute(paths, selection: tia.ImpactSelection, dry_run: bool) -> dict:
    evidence = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "changed_paths": paths,
        "classification": {
            "risk": selection.classification.risk,
            "blast_radius": selection.classification.blast_radius,
            "unrecognized_paths": selection.classification.unrecognized_paths,
        },
        "fail_closed": selection.fail_closed,
        "fail_closed_reason": selection.fail_closed_reason,
        "java_tests_selected": selection.java_tests,
        "reasons": selection.reasons,
        "skipped": selection.skipped,
        "commands": [],
        "dry_run": dry_run,
    }

    if dry_run:
        evidence["overall_exit_code"] = 0
        return evidence

    java_touched = any(p.startswith("app/") for p in paths)
    overall_rc = 0

    if selection.fail_closed:
        for name, argv, cwd in [
            ("java-full-suite", [str(APP_DIR / ("mvnw.cmd" if sys.platform == "win32" else "mvnw")), "test"], APP_DIR),
            ("python-regression", [sys.executable, "-m", "unittest", "discover", "-p", "test_*.py"], AGENT_DIR),
        ]:
            result = _run(argv, cwd)
            result["name"] = name
            evidence["commands"].append(result)
            overall_rc = overall_rc or result["exit_code"]
        for script in ("test_trainer_frontend.js", "test_usage_frontend.js", "test_learn_frontend.js"):
            result = _run(["node", script], AGENT_DIR)
            result["name"] = f"node:{script}"
            evidence["commands"].append(result)
            overall_rc = overall_rc or result["exit_code"]
    else:
        if java_touched:
            smoke_result = _mvnw_test(ALWAYS_ON_SMOKE_JAVA)
            smoke_result["name"] = "always-on-smoke"
            evidence["commands"].append(smoke_result)
            overall_rc = overall_rc or smoke_result["exit_code"]

        if selection.java_tests == [tia.ALL_JAVA_MODULE_TESTS]:
            result = _mvnw_test()
            result["name"] = "java-selected-all"
            evidence["commands"].append(result)
            overall_rc = overall_rc or result["exit_code"]
        elif selection.java_tests:
            classes = [c for c in selection.java_tests if c not in ALWAYS_ON_SMOKE_JAVA]
            if classes:
                result = _mvnw_test(classes)
                result["name"] = "java-selected"
                evidence["commands"].append(result)
                overall_rc = overall_rc or result["exit_code"]

    evidence["overall_exit_code"] = overall_rc
    return evidence


def _save_evidence(evidence: dict) -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    ts = evidence["timestamp_utc"].replace(":", "-")
    path = EVIDENCE_DIR / f"{ts}.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return path


def main():
    args = sys.argv[1:]
    base = None
    dry_run = "--dry-run" in args
    if "--base" in args:
        base = args[args.index("--base") + 1]

    paths = _git_changed_paths(base)
    if not paths:
        print("No changed files detected -- nothing to verify.")
        sys.exit(0)

    selection = build_plan(paths)
    print_plan(paths, selection)

    evidence = execute(paths, selection, dry_run)
    evidence_path = _save_evidence(evidence)
    print(f"\nEvidence written: {evidence_path.relative_to(REPO_ROOT)}")
    print(f"Overall exit code: {evidence['overall_exit_code']}")
    sys.exit(evidence["overall_exit_code"])


if __name__ == "__main__":
    main()
