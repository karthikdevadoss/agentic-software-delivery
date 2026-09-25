"""
CI entry point for the hermetic Python test suite.

WHY THIS EXISTS RATHER THAN A BARE `python -m unittest discover`
Two real defects, both found 2026-09-25 by actually running the obvious
command rather than assuming it worked:

1. FALSE GREEN. `python -m unittest discover -p "test_*.py"` in agent/ runs
   for >12 minutes, never prints a `Ran N tests` summary, and **exits 0**.
   A CI job built on it would report success having completed nothing. This
   is the same defect class as verify_change.py's "PASSED after running zero
   commands" bug fixed the same day: an exit code that means "nothing ran",
   read as "nothing wrong".

2. TWO SOURCE MODULES LOOK LIKE TESTS. `agent/test_impact_analysis.py` (the
   Test Impact Analysis engine) and `agent/test_architect.py` (the Test
   Architect) are implementation, not tests -- their names merely start with
   `test_`. Any `discover -p "test_*.py"` sweeps them in. Their real test
   files are `test_test_impact_analysis.py` and `test_test_architect.py`,
   both of which ARE in the list below.

So the module list is explicit, and the result is asserted rather than
trusted. Exit code is only 0 when real tests really ran and really passed.

Run:  python agent/ci_python_tests.py
      python agent/ci_python_tests.py --list     # print the two lists, run nothing
"""

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# HERMETIC MODULES -- no live Postgres, no Railway, no spawned web_server, no
# network, no dependence on this developer machine's toolchain or dotfiles.
# These BLOCK CI.
#
# HOW THIS LIST IS VALIDATED, and how it was wrong the first time: the original
# version was built from (a) grepping each test FILE for DATABASE_URL /
# railway.app / psycopg and (b) the module passing locally. Both signals are
# unsound, and the first real CI run proved it by failing 4 modules:
#   - grep reads the test file, not what it IMPORTS. test_knowledge_candidates
#     never names a database; it imports the event ledger, which does.
#   - "passes locally" is meaningless on a machine that happens to hold an
#     EVENT_LEDGER_DATABASE_URL, a JDK, and a ~/.claude/settings.json.
# The only sound validation is a real run in an environment that has none of
# those -- i.e. CI itself. Treat any future addition here as provisional until
# it has gone green on a fresh runner, not when it goes green on this laptop.
# ---------------------------------------------------------------------------
HERMETIC_MODULES = [
    "test_acceptance_contract",
    "test_agent_decision_eval_runner",
    "test_agent_loop",
    "test_aggregate_evidence",
    "test_ai_intelligence",
    "test_ask_codebase",
    "test_backend_catalogue",
    "test_backend_planning",
    "test_backend_rag_index",
    "test_backlog",
    "test_build_tools",
    "test_capability_boundaries",
    "test_change_risk",
    "test_check_config_drift",
    "test_demo_catalogue",
    "test_demo_execution",
    "test_dev_check",
    "test_estimation",
    "test_eval_runner",
    "test_execution_tools",
    "test_interview_walkthrough_data",
    "test_learn_tree",
    "test_main",
    "test_mcp_server",
    "test_non_llm_intelligence_metrics",
    "test_pricing_config",
    # Promoted from the live-infra list 2026-09-25 once it was isolated: it now
    # redirects INDEX_PATH into a temp dir and can no longer touch (or be
    # blocked by) the real index. Verified passing with the real index absent.
    "test_rag_index",
    "test_reasoning_gateway",
    "test_reasoning_gateway_enforcement",
    "test_risk_policy",
    # Promoted out of PENDING_OWNER_DECISION 2026-09-25 after a real content
    # re-verification (capabilities resolve, evidence paths exist, 8/9 URLs
    # live) and an honest last_verified bump. The 9th URL, the custom domain,
    # is annotated unreachable in showcase.yaml rather than hidden.
    "test_showcase_data",
    "test_static_gate",
    "test_test_architect",
    "test_test_impact_analysis",
    "test_tools",
    "test_triage_promotion",
    "test_verify_change",
    "test_verify_claude_permissions_config",
    "test_write_tools",
]

# ---------------------------------------------------------------------------
# LIVE-INFRASTRUCTURE MODULES -- deliberately NOT blocking CI, with the real
# reason recorded per module. These are NOT skipped, disabled, or weakened:
# they are real integration tests that require credentials/services this CI
# job intentionally does not hold. They must still be run locally or in an
# environment that has the real dependency.
#
# This list is PRINTED ON EVERY CI RUN so the exclusion cannot quietly decay
# into "nobody ever runs these". Closing it is tracked work, not a silent gap.
# ---------------------------------------------------------------------------
LIVE_INFRA_MODULES = {
    "test_backend_execution": "spawns a real web_server subprocess",
    # --- The four below were MISCLASSIFIED as hermetic and were caught by the
    # first real CI run (2026-09-25, run 36172353680), not by local testing.
    # Root cause of the misclassification: "hermetic" was judged from grepping
    # each test FILE for DATABASE_URL/railway/psycopg plus the fact that it
    # passed locally. Both signals were wrong. The grep missed dependencies
    # reached through IMPORTS rather than named in the test file, and the local
    # pass was an artifact of this dev machine holding an EVENT_LEDGER_DATABASE_URL
    # and a JDK that CI's Python job deliberately does not have. This is the
    # repo's own documented "green on a long-lived dev machine, red on a fresh
    # checkout" trap, reproduced exactly.
    "test_knowledge_candidates": "imports the event ledger; needs a live EVENT_LEDGER_DATABASE_URL",
    "test_claude_code_hook": "RealLedgerDistinctnessTestCase queries the live Postgres ledger",
    "test_environment_preflight": "asserts a live JDK on the host; CI's Python job has no Java installed",
    "test_verify_claude_hooks_config": "asserts ~/.claude/settings.json exists on this developer machine",
    "test_event_ledger": "requires a live DATABASE_URL (real Postgres event ledger)",
    "test_learn_pdf": "hits the live Railway deployment",
    "test_session_history": "hits the live Railway deployment",
    "test_triage_execution": "hits live Railway over urllib + spawns a subprocess",
    "test_web_server": "spawns a real web_server subprocess and hits live Railway",
}

# BUILD-DERIVED PREREQUISITE, not a live-infra dependency: a few modules in the
# hermetic list read the on-disk RAG indexes, which are gitignored build output.
# CI already builds both (`python rag_index.py`, `python backend_rag_index.py`)
# before invoking this runner, which is why they belong in the blocking set
# despite needing state that is absent on a fresh checkout. Locally they fail
# until those two commands have been run at least once.
REQUIRES_PREBUILT_RAG_INDEX = ("test_mcp_server", "test_backend_rag_index", "test_ask_codebase")

# HELD BACK PENDING AN OWNER DECISION -- not excluded, not skipped, not
# forgotten. Empty is the healthy state, and it is empty right now: the one
# module that was parked here (test_showcase_data) was released into the
# blocking set on 2026-09-25 after a real re-verification, not by lowering the
# bar. A module parked here must carry a real reason AND a real route out; it
# is not a place to quietly retire an inconvenient test.
PENDING_OWNER_DECISION = {}

# Whole-file accounting, asserted at runtime below: every test_*.py in agent/
# must be in exactly one bucket. Two files are SOURCE modules, not tests --
# test_impact_analysis.py (the TIA engine) and test_architect.py (the Test
# Architect) -- and are the reason a bare discover -p "test_*.py" misbehaves.
SOURCE_MODULES_NOT_TESTS = ("test_impact_analysis", "test_architect")

# Real measured count on 2026-09-25 was 553 across the hermetic set. The floor
# is deliberately below that (suites legitimately grow and shrink a little),
# but far above zero -- its whole job is to fail when the suite silently
# collapses, which is exactly what the bare `discover` command did.
MIN_EXPECTED_TESTS = 520


def check_every_module_is_accounted_for() -> list:
    """A new test_*.py added to agent/ must land in exactly one bucket. Without
    this, a genuinely new test module is simply never run by CI and nobody
    notices -- the same silent-gap family as the false-green `discover` bug and
    the unreachable Playwright specs. Returns the unaccounted module names."""
    here = Path(__file__).resolve().parent
    on_disk = {p.stem for p in here.glob("test_*.py")}
    accounted = (
        set(HERMETIC_MODULES)
        | set(LIVE_INFRA_MODULES)
        | set(PENDING_OWNER_DECISION)
        | set(SOURCE_MODULES_NOT_TESTS)
    )
    return sorted(on_disk - accounted)


def main() -> int:
    unaccounted = check_every_module_is_accounted_for()
    if unaccounted:
        print("FAIL: test module(s) exist in agent/ but are in no bucket:")
        for m in unaccounted:
            print(f"  - {m}")
        print("Add each to HERMETIC_MODULES (preferred), LIVE_INFRA_MODULES with a real")
        print("reason, or PENDING_OWNER_DECISION. An unlisted module is never run.")
        return 1

    if "--list" in sys.argv:
        print(f"HERMETIC (blocking CI) -- {len(HERMETIC_MODULES)} modules:")
        for m in HERMETIC_MODULES:
            print(f"  {m}")
        print(f"\nLIVE-INFRA (not blocking CI, must still be run elsewhere) -- {len(LIVE_INFRA_MODULES)}:")
        for m, why in sorted(LIVE_INFRA_MODULES.items()):
            print(f"  {m:28s} {why}")
        return 0

    print("=" * 72)
    print(f"Running {len(HERMETIC_MODULES)} hermetic Python test modules (blocking).")
    print(f"NOT run here -- {len(LIVE_INFRA_MODULES)} live-infrastructure modules, real reasons:")
    for m, why in sorted(LIVE_INFRA_MODULES.items()):
        print(f"  - {m}: {why}")
    print("These are excluded for a stated environmental reason, NOT skipped or")
    print("weakened. They still need to run where the real dependency exists.")
    print("=" * 72)

    suite = unittest.defaultTestLoader.loadTestsFromNames(HERMETIC_MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    print("\n" + "=" * 72)
    print(f"tests run : {result.testsRun}")
    print(f"failures  : {len(result.failures)}")
    print(f"errors    : {len(result.errors)}")
    print(f"skipped   : {len(result.skipped)}")

    # --- the false-green guard, the whole reason this file exists ---
    if result.testsRun == 0:
        print("\nFAIL: zero tests actually ran. An exit code of 0 here would mean")
        print("'nothing ran', not 'nothing wrong'. Failing deliberately.")
        return 1

    if result.testsRun < MIN_EXPECTED_TESTS:
        print(f"\nFAIL: only {result.testsRun} tests ran, expected at least "
              f"{MIN_EXPECTED_TESTS}. The suite has silently shrunk -- either a")
        print("module stopped loading, or tests were removed. Investigate before")
        print("lowering this floor; lowering it to go green is the failure mode")
        print("this guard exists to prevent.")
        return 1

    if not result.wasSuccessful():
        print("\nFAIL: real test failures/errors above.")
        return 1

    print("\nPASS: real tests ran and really passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
