"""The one local command that answers: can this branch truthfully be called green?

    python agent/release_health.py              # the deterministic gates
    python agent/release_health.py --quick      # the seconds-long subset
    python agent/release_health.py --changed    # only what the real diff needs
    python agent/release_health.py --list       # print the plan, run nothing

WHY THIS EXISTS (Sprint 17, 2026-09-30)
---------------------------------------
There was no single answer to that question. There were six: a GitHub workflow
with eight jobs of which two were non-gating, a Python runner, three Node
harnesses invoked by hand, a Playwright config, a TIA engine, and a
verify_change.py dry run. Asking "is the branch green?" meant remembering all of
them and remembering which failures were expected -- and on 2026-09-30 one of
them had been failing for two sprints for a reason that was not a release
blocker at all. A green claim assembled from memory is not a green claim.

WHAT RELEASE HEALTH IS, precisely
---------------------------------
Deterministic checks whose failure means the branch genuinely cannot ship. Two
properties, both required: the same input gives the same verdict every run, and
the thing measured is a property of THIS REPOSITORY'S CODE.

That second half is what separates release health from a quality monitor. The
Standing Interview answer-quality monitor is deterministic CODE scoring a
NON-DETERMINISTIC subject -- what a language model said on the draws that
happened to be captured. It runs here, its real result is printed, and it does
not set the exit code. That is not leniency: a suite that is red for a reason
nobody can fix by changing code makes "RELEASE HEALTH = RED" mean nothing, and a
phrase that means nothing protects nothing.

WHAT IT NEVER DOES
------------------
It never invokes a paid suite. Not gated, not conditional, not with a flag --
there is no code path from this module to a provider call, and it prints the
paid-guard's real status so the claim is checkable rather than asserted. See
agent/paid_test_guard.py.

HONEST LIMITS, stated here rather than discovered later
-------------------------------------------------------
This is a LOCAL runner and this laptop is not a clean room. Three gates cannot
run here and say so instead of passing quietly:

  * Docker is not installed (docs/DECISIONS.md), so the Customer App's real
    Testcontainers Postgres tests and its Dockerfile build only ever run in CI.
  * The Java gates need a JDK and several minutes; --quick omits them by
    design and says so in the exclusion list.
  * Five Playwright specs fail locally for environment reasons proven
    pre-existing in Sprint 16 by stashing all changes and re-running against a
    clean tree (no ledger data, no verified run, Customer App not running).
    They pass in production.

A gate that could not execute is reported as SKIPPED, never folded into a pass.
CLAUDE.md: SKIPPED is not PASSED, and a report that cannot tell them apart is
the false-green defect this repository has already shipped once.
"""

from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paid_test_guard  # noqa: E402
import select_tests  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# Every gate: (id, human name, argv, cwd relative to REPO, tags, requirement).
# `requirement` is one of:
#   "blocking"     -- a real failure means the branch cannot ship
#   "monitor"      -- runs, reported in full, never sets the exit code
# A gate is never silently dropped; when its prerequisite is absent it is
# reported SKIPPED with the real reason.
GATES = [
    {
        "id": "static-gate",
        "name": "STATIC gate (file modes, shebangs, XML/HTML comment '--')",
        "argv": [sys.executable, "agent/static_gate.py"],
        "tags": ["quick", "full"],
        "requirement": "blocking",
        "why": "two real recurring defect classes that a rule in LESSONS.md failed to prevent twice",
    },
    {
        "id": "config-drift-gate",
        "name": "CONFIG-DRIFT gate (Spring profile files)",
        "argv": [sys.executable, "agent/check_config_drift.py"],
        "tags": ["quick", "full"],
        "requirement": "blocking",
        "why": "the Owner's real NRG stage-vs-prod incident class",
    },
    {
        "id": "python-hermetic",
        "name": "Python hermetic suite + quality monitors",
        "argv": [sys.executable, "ci_python_tests.py"],
        "cwd": "agent",
        "tags": ["quick", "full"],
        "requirement": "blocking",
        "why": ("the blocking half sets the exit code; the monitor half runs in the "
                "same invocation and is reported separately by that runner"),
    },
    {
        "id": "node-frontend",
        "name": "Node frontend harnesses (trainer, usage, learn)",
        "argv": None,  # three commands, handled below
        "cwd": "agent",
        "tags": ["quick", "full"],
        "requirement": "blocking",
        "why": "the only deterministic coverage of the rendered Usage/Workbench/Learn HTML",
        "multi": [
            [shutil.which("node") or "node", "test_trainer_frontend.js"],
            [shutil.which("node") or "node", "test_usage_frontend.js"],
            [shutil.which("node") or "node", "test_learn_frontend.js"],
        ],
        "needs": "node",
    },
    {
        "id": "rag-mcp-evals",
        "name": "RAG/MCP retrieval + routing evals (recorded thresholds)",
        "argv": [sys.executable, "eval_runner.py", "all"],
        "cwd": "agent",
        "tags": ["full"],
        "requirement": "blocking",
        "why": "deterministic retrieval thresholds, zero model calls",
    },
    {
        "id": "java-customer-app",
        "name": "Customer App (Java/Spring) unit + integration tests",
        "argv": None,
        "cwd": "app",
        "tags": ["full"],
        "requirement": "blocking",
        "why": "the real application under the Workbench demo",
        # ABSOLUTE, not "./mvnw.cmd". A relative command is resolved against
        # this PROCESS's cwd, not against subprocess's `cwd=` argument -- so the
        # first real run of this runner reported
        # "command not found: [WinError 2]" for a wrapper that exists. That is a
        # SKIP masquerading as a FAIL, which is the wrong direction but the same
        # family of defect as a skip masquerading as a pass.
        "multi": [[str(REPO / "app" / ("mvnw.cmd" if os.name == "nt" else "mvnw")),
                   "test", "-B"]],
        "needs": "java",
    },
    {
        "id": "playwright-functional",
        "name": "Playwright functional recruiter paths",
        "argv": None,
        "tags": ["full"],
        "requirement": "blocking",
        "why": "the layer that catches the defect class the Owner reports hitting most",
        "multi": [[shutil.which("npx") or "npx", "playwright", "test", "--reporter=list"]],
        "needs": "playwright",
    },
]

# Gates that exist but are NOT release health, each with the real reason. Printed
# on every run so the exclusion is visible rather than remembered.
NOT_RELEASE_HEALTH = {
    "si-answer-quality-monitor": (
        "QUALITY MONITOR -- scores what a language model actually said on a "
        "captured sample. Runs inside the python-hermetic gate above and is "
        "reported there in full. Known RED on question m. Not blocking, because "
        "no change to this repository's code can make it green."
    ),
    "si-answer-quality-paid": (
        "PAID. Would call the real provider via agent/si_recapture.py. Refused "
        "by agent/paid_test_guard.py unless ALLOW_PAID_TESTS and a positive "
        "PAID_TEST_BUDGET_USD are both set. There is no code path from this "
        "runner to it."
    ),
    "playwright-visual-regression": (
        "VISUAL. Gated behind VISUAL_REGRESSION=1 and deliberately NOT part of "
        "release health: the Owner has not accepted the new screenshot baseline, "
        "and gating on an unapproved baseline would block every branch on a "
        "diff nobody agreed to."
    ),
    "workbench-real-acceptance": (
        "LIVE. Submits a real requirement that commits, pushes and deploys a "
        "real change to the production Customer App. Operator-initiated only."
    ),
    "java-microservices": (
        "Six independent Maven projects; several need Docker, which this laptop "
        "does not have (docs/DECISIONS.md). Real gate, runs in CI's matrix."
    ),
    "real-topology": (
        "Starts four real JVM service processes and coordinates them. Real "
        "gate (GATING in CI since BL-056), too heavy for a local pre-commit "
        "check and needs a JDK plus several minutes."
    ),
    "customer-app-docker-build": (
        "Requires a Docker daemon, absent on this machine. The only place "
        "app/Dockerfile is genuinely proven to build is CI."
    ),
    "owasp-dependency-check": (
        "Informational in CI and currently non-functional without an NVD API "
        "key (a real NVD policy tightening, not a config mistake). Never "
        "blocking anywhere until it has been shown not to be noisy."
    ),
}


def _have(what: str) -> tuple:
    """Returns (available, reason). Checks the real prerequisite rather than
    assuming this machine has it -- the exact trap that made four Python modules
    look hermetic because this laptop happened to hold a JDK and a ledger URL."""
    if what == "node":
        exe = shutil.which("node")
        return (exe is not None, "node is not on PATH" if exe is None else "")
    if what == "java":
        wrapper = REPO / "app" / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        if not wrapper.exists():
            return False, f"maven wrapper not found at {wrapper}"
        if shutil.which("java") is None and not os.environ.get("JAVA_HOME"):
            return False, "no java on PATH and JAVA_HOME is unset"
        return True, ""
    if what == "playwright":
        if shutil.which("npx") is None:
            return False, "npx is not on PATH"
        if not (REPO / "node_modules" / "@playwright").exists():
            return False, "node_modules/@playwright is absent -- run `npm ci` first"
        return True, ""
    return True, ""


def _run(argv, cwd: Path, timeout: int):
    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, errors="replace",
        )
    except FileNotFoundError as exc:
        return None, f"command not found: {exc}", round(time.monotonic() - start, 1)
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s", round(time.monotonic() - start, 1)
    return proc, "", round(time.monotonic() - start, 1)


def _extract_failure_lines(output: str) -> list:
    """Pull the lines that NAME a failure out of an arbitrarily long log.

    Deliberately pattern-based across the four runners this module drives
    (unittest, Playwright's list reporter, Maven surefire, the Node harnesses)
    rather than parsing any one of their formats properly -- the goal is "the
    reader learns WHICH thing failed without re-running it", not a structured
    report. Capped so a pathological log cannot flood the terminal, and the cap
    is stated when it bites rather than silently applied.
    """
    markers = (
        "FAIL:", "ERROR:", "Error:", "FAILED", "failed", "AssertionError",
        "✘", "Tests run:", "did not run", "Timeout", "timed out",
    )
    # Playwright's list reporter numbers each failure as "  1) [chromium] > spec"
    # with none of the words above on that line -- which is exactly the line that
    # names the broken spec. Smoke-testing the extractor on a real sample caught
    # that it was dropping it; the markers alone recovered only "2 failed".
    numbered_failure = re.compile(r"^\s*\d+\)\s")
    lines = []
    for raw in output.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if numbered_failure.match(line) or any(m in line for m in markers):
            # Playwright's progress lines contain "passed"/"failed" counts on
            # every tick; keep only the ones that name a spec or a test.
            lines.append(line.strip()[:240])
    seen, unique = set(), []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique.append(line)
    if len(unique) > 40:
        return unique[:40] + [f"... {len(unique) - 40} further failure line(s) not shown "
                              f"here; the full set is in this run's --json output"]
    return unique


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quick", action="store_true",
                    help="only the seconds-long gates (tag: quick)")
    ap.add_argument("--changed", metavar="BASE", nargs="?", const="origin/master",
                    help="run only the gates the real diff selects (default base origin/master)")
    ap.add_argument("--list", action="store_true", help="print the plan and run nothing")
    ap.add_argument("--timeout", type=int, default=1800, help="per-gate timeout in seconds")
    ap.add_argument("--json", metavar="PATH", help="also write the result as JSON")
    args = ap.parse_args(argv)

    guard = paid_test_guard.paid_tests_status()

    selected_ids = None
    selection = None
    if args.changed:
        out = subprocess.run(["git", "diff", "--name-only", f"{args.changed}...HEAD"],
                             cwd=str(REPO), capture_output=True, text=True, check=False)
        paths = [l.strip() for l in out.stdout.splitlines() if l.strip()]
        selection = select_tests.select(paths)
        selected_ids = {s["suite"] for s in selection["included_suites"]}

    plan, excluded = [], []
    for gate in GATES:
        if args.quick and "quick" not in gate["tags"]:
            excluded.append((gate["id"], "--quick was requested and this gate is not tagged quick"))
            continue
        if selected_ids is not None and gate["id"] not in selected_ids:
            excluded.append((gate["id"],
                             f"the real diff's change_class {selection['change_class']} does not "
                             f"select it (agent/select_tests.py)"))
            continue
        need = gate.get("needs")
        if need:
            ok, why = _have(need)
            if not ok:
                excluded.append((gate["id"], f"SKIPPED -- prerequisite absent: {why}"))
                continue
        plan.append(gate)

    print("=" * 78)
    print("RELEASE HEALTH -- deterministic gates whose failure means this branch")
    print("cannot truthfully be called green.")
    print(f"repo        : {REPO}")
    print(f"mode        : {'--quick' if args.quick else ('--changed ' + args.changed) if args.changed else 'full'}")
    print(f"paid suites : NEVER invoked by this runner. Guard authorized={guard['authorized']}, "
          f"max_paid_budget=${guard['max_paid_budget']:.2f}")
    print(f"expected paid model calls: 0")
    if selection is not None:
        print(f"change_class: {selection['change_class']} -- {selection['change_class_reason']}")
    print("-" * 78)
    print(f"WILL RUN ({len(plan)}):")
    for g in plan:
        print(f"  {g['id']:24s} {g['name']}")
        print(f"  {'':24s}   why: {g['why']}")
    print(f"\nNOT RUN THIS INVOCATION ({len(excluded)}):")
    for gid, why in excluded:
        print(f"  {gid:24s} {why}")
    print(f"\nNOT RELEASE HEALTH AT ALL ({len(NOT_RELEASE_HEALTH)}) -- real reasons, not omissions:")
    for gid, why in sorted(NOT_RELEASE_HEALTH.items()):
        print(f"  {gid:28s} {why}")
    print("=" * 78)

    if args.list:
        print("\n--list requested: nothing was executed.")
        return 0

    results = []
    for gate in plan:
        cwd = REPO / gate.get("cwd", ".")
        commands = gate.get("multi") or [gate["argv"]]
        gate_failed = False
        detail = []
        total_secs = 0.0
        for cmd in commands:
            print(f"\n>>> {gate['id']}: {' '.join(str(c) for c in cmd)}")
            proc, err, secs = _run(cmd, cwd, args.timeout)
            total_secs += secs
            if proc is None:
                gate_failed = True
                detail.append({"command": " ".join(str(c) for c in cmd),
                               "exit_code": None, "error": err})
                print(f"    ERROR: {err}")
                continue
            out = (proc.stdout or "") + (proc.stderr or "")
            # ON SUCCESS, a tail is enough. ON FAILURE, IT IS NOT -- and this was
            # a real defect in this runner's first full run (BL-R5): the
            # Playwright gate failed, and the 1500-character tail had already
            # scrolled past every failure name, leaving only "36 skipped / 7 did
            # not run / 358 passed" and no way to tell which specs broke without
            # re-running a seven-minute suite. A report that loses the one thing
            # you needed is worse than no report, because it looks complete.
            if proc.returncode == 0:
                print(out[-1200:].rstrip() or "    (no output)")
            else:
                print(out[-1200:].rstrip() or "    (no output)")
                failure_lines = _extract_failure_lines(out)
                if failure_lines:
                    print("")
                    print(f"    ---- {len(failure_lines)} failure line(s) recovered "
                          f"from the full output ----")
                    for line in failure_lines:
                        print(f"    {line}")
            detail.append({
                "command": " ".join(str(c) for c in cmd),
                "exit_code": proc.returncode,
                "error": "",
                # The full output goes in the JSON regardless of length, so a
                # failure is always reconstructable without a second run.
                "failure_lines": _extract_failure_lines(out) if proc.returncode else [],
                "output_chars": len(out),
            })
            if proc.returncode != 0:
                gate_failed = True
        results.append({
            "id": gate["id"], "name": gate["name"],
            "requirement": gate["requirement"],
            "passed": not gate_failed,
            "seconds": round(total_secs, 1),
            "commands": detail,
        })

    blocking_failures = [r for r in results
                         if r["requirement"] == "blocking" and not r["passed"]]

    print("\n" + "=" * 78)
    print("RELEASE HEALTH RESULT")
    print("=" * 78)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"  {mark:4s}  {r['id']:24s} {r['seconds']:>7.1f}s  {r['name']}")
    print(f"\n  ran      : {len(results)}")
    print(f"  passed   : {sum(1 for r in results if r['passed'])}")
    print(f"  failed   : {len(blocking_failures)}")
    print(f"  excluded : {len(excluded)} this invocation "
          f"+ {len(NOT_RELEASE_HEALTH)} never-release-health (both listed above)")
    print(f"  paid model calls: 0")

    verdict = "GREEN" if not blocking_failures else "RED"
    print(f"\n  RELEASE HEALTH = {verdict}")
    if blocking_failures:
        print("  blocked by:")
        for r in blocking_failures:
            for c in r["commands"]:
                if c["exit_code"] not in (0, None) or c["error"]:
                    print(f"    - {r['id']}: {c['command']} "
                          f"-> exit {c['exit_code']}{(' / ' + c['error']) if c['error'] else ''}")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "verdict": verdict,
            "mode": "quick" if args.quick else ("changed" if args.changed else "full"),
            "results": results,
            "excluded_this_invocation": [{"id": g, "reason": w} for g, w in excluded],
            "never_release_health": NOT_RELEASE_HEALTH,
            "expected_paid_model_calls": 0,
            "paid_guard": guard,
        }, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.json}")

    return 0 if verdict == "GREEN" else 1


if __name__ == "__main__":
    sys.exit(main())
