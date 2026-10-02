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
    "test_durable_workflow",          # BL-093/094: MemorySaver + a local git repo, no network
    "test_jd_match",                  # BL-097: injected model + injected embedder, no network
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
    "test_governance_clauses",   # Sprint 18 Phase 0: required governing clauses still present
    "test_eval_runner",
    "test_execution_tools",
    "test_interview_walkthrough_data",
    "test_learn_tree",
    "test_main",
    "test_mcp_server",
    "test_non_llm_intelligence_metrics",
    "test_pricing_config",
    # Sprint 18: the public proof surface gate. Hermetic -- it reads two
    # committed YAML files and asks the real in-process Starlette router
    # whether each internal destination resolves. No network, no model.
    "test_proof_registry",
    # Sprint 18: nothing private on a public surface. Hermetic -- it reads
    # committed public assets off disk and matches patterns, no network.
    "test_public_leakage",
    # Promoted from the live-infra list 2026-09-25 once it was isolated: it now
    # redirects INDEX_PATH into a temp dir and can no longer touch (or be
    # blocked by) the real index. Verified passing with the real index absent.
    "test_rag_index",
    "test_reasoning_gateway",
    "test_reasoning_gateway_enforcement",
    "test_risk_policy",
    # Sprint 17: the cost-aware selector and the fail-closed paid-test guard.
    # Hermetic by construction -- every case is pure Python over an injected env
    # dict or a literal path list, and the guard's whole job is to make a
    # provider call impossible without explicit authorization.
    "test_select_tests",
    # Sprint 17: the release-health runner's three-outcome verdict. Hermetic --
    # every case injects its own prerequisite answers rather than depending on
    # what this machine happens to have installed, which is the exact trap that
    # made four modules in this list look hermetic once before.
    "test_release_health",
    # Promoted out of PENDING_OWNER_DECISION 2026-09-25 after a real content
    # re-verification (capabilities resolve, evidence paths exist, 8/9 URLs
    # live) and an honest last_verified bump. The 9th URL, the custom domain,
    # is annotated unreachable in showcase.yaml rather than hidden.
    "test_showcase_data",
    # Reads the three real state documents + real git history; writes nothing.
    # Needs full history (rev-list --max-parents=0), which this CI job already
    # has via fetch-depth: 0 for verify_change.py.
    # Hermetic by construction: the model is injected, the corpus is a
    # fixture, and no network or private repo is required.
    "test_public_surface_gate",   # Sprint 14: recruiter-facing release guards
    # Sprint 15: spend protection on the public Standing Interview endpoint.
    # Hermetic -- it drives the real route with a mocked answer() and makes no
    # model call. Written after the credit balance was exhausted and every
    # grounded question on the live site returned HTTP 500.
    "test_si_budget",
    # Sprint 15: answer quality. Hermetic -- it scores an archived JSON capture
    # of real production answers and calls nothing.
    # Sprint 17: the half of this module that scored a capture of real MODEL
    # OUTPUT moved to test_si_answer_quality_monitor (see QUALITY_MONITOR_MODULES
    # below). What stays here scores a FROZEN archive with FROZEN code -- same
    # input, same output, every run -- so a failure means the measuring
    # instrument broke, which is a real release blocker.
    "test_si_quality",
    "test_standing_interview",
    "test_state_brief",
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
    "test_workflow_checkpointer": "BL-094: real Postgres checkpoint tables via EVENT_LEDGER_DATABASE_URL",
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

# ---------------------------------------------------------------------------
# QUALITY MONITORS -- RUN ON EVERY INVOCATION, REPORTED IN FULL, NOT BLOCKING.
#
# Added 2026-09-30 (Sprint 17). This is NOT a third exclusion list and it is not
# a place to park an inconvenient failure: every module here EXECUTES on every
# run and every failure's real assertion text is printed. The only thing it does
# not do is set the exit code.
#
# THE REAL PROBLEM IT SOLVES. On 2026-09-30 this runner reported 784 tests, 2
# failures. One was a genuine deterministic wiring defect (a Playwright spec
# unreachable from the TIA map) and was fixed. The other was
# test_si_quality.DoesNotOverRefuse's post-fix half, which had been red for two
# sprints because a language model declines one interview question on 2 of 3
# captured draws. Both produced the same exit code, so the exit code carried no
# information: it said red whether or not anything had regressed, and the only
# way to tell them apart was to read the log and already know which failure was
# expected. That is how a team learns to ignore red builds.
#
# THE LINE, stated so it cannot be stretched later. A module belongs here ONLY
# if its assertion is about the CONTENT OF MODEL OUTPUT. If the same code run
# twice on the same input can legitimately give different verdicts, it is a
# monitor. If it cannot, it is release health, and no amount of inconvenience
# moves it. "It fails a lot" is not a qualifying reason; "what it measures is
# not a property of this repository's code" is.
#
# COST: zero paid model calls. Both modules here score a JSON capture already on
# disk. Suites that would really call a provider are gated separately and
# fail closed -- see agent/paid_test_guard.py.
# ---------------------------------------------------------------------------
QUALITY_MONITOR_MODULES = {
    "test_si_answer_quality_monitor": (
        "scores a real captured sample of Standing Interview ANSWERS -- what a "
        "language model actually said, not what this repository's code does. "
        "KNOWN RED on question m ('describe a technical disagreement'), 2 of 3 "
        "draws not answered. Tracked as SI-19/BL-149."
    ),
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

# Real measured count on 2026-09-25 is 547 across the 40-module hermetic set
# (531 before test_state_brief was added, +16 from it -- verified by collecting
# both lists, not by trusting the delta). An earlier version of this comment
# said 553; that figure was measured before the four misclassified live-infra
# modules were moved out on 9a26512 and is corrected here rather than left to
# look like an unexplained shrink. The floor
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
        | set(QUALITY_MONITOR_MODULES)
        | set(PENDING_OWNER_DECISION)
        | set(SOURCE_MODULES_NOT_TESTS)
    )
    return sorted(on_disk - accounted)


def run_quality_monitors():
    """Execute the quality monitors and return their unittest result.

    Deliberately runs them as a SECOND, separately-reported suite rather than
    folding them into the blocking one. Two properties matter and they are in
    tension: a known stochastic miss must stay visible, and a known stochastic
    miss must not make this runner's exit code meaningless. One suite cannot do
    both -- a single exit code cannot say "the code is fine and the model
    answered one question badly".

    Never swallows a failure silently: every failing case is named in the
    summary, and its full assertion text is printed by the runner below exactly
    as the blocking suite's would be. Returns None only if the monitor bucket is
    empty, which is a legitimate state.
    """
    if not QUALITY_MONITOR_MODULES:
        return None
    print("\n" + "=" * 72)
    print(f"QUALITY MONITORS -- {len(QUALITY_MONITOR_MODULES)} module(s). These RUN and are")
    print("REPORTED IN FULL. They do NOT set the exit code, because what they")
    print("assert is the content of model output, not a property of this code:")
    for m, why in sorted(QUALITY_MONITOR_MODULES.items()):
        print(f"  - {m}: {why}")
    print("=" * 72)
    monitor_suite = unittest.defaultTestLoader.loadTestsFromNames(
        sorted(QUALITY_MONITOR_MODULES)
    )
    return unittest.TextTestRunner(verbosity=2).run(monitor_suite)


def main() -> int:
    unaccounted = check_every_module_is_accounted_for()
    if unaccounted:
        print("FAIL: test module(s) exist in agent/ but are in no bucket:")
        for m in unaccounted:
            print(f"  - {m}")
        print("Add each to HERMETIC_MODULES (preferred), LIVE_INFRA_MODULES with a real")
        print("reason, QUALITY_MONITOR_MODULES if it asserts on model output, or")
        print("PENDING_OWNER_DECISION. An unlisted module is never run.")
        return 1

    if "--list" in sys.argv:
        print(f"HERMETIC (blocking CI) -- {len(HERMETIC_MODULES)} modules:")
        for m in HERMETIC_MODULES:
            print(f"  {m}")
        print(f"\nQUALITY MONITORS (run every time, reported in full, NOT blocking) -- {len(QUALITY_MONITOR_MODULES)}:")
        for m, why in sorted(QUALITY_MONITOR_MODULES.items()):
            print(f"  {m:34s} {why}")
        print(f"\nLIVE-INFRA (not blocking CI, must still be run elsewhere) -- {len(LIVE_INFRA_MODULES)}:")
        for m, why in sorted(LIVE_INFRA_MODULES.items()):
            print(f"  {m:28s} {why}")
        return 0

    print("=" * 72)
    print(f"RELEASE HEALTH: {len(HERMETIC_MODULES)} hermetic Python test modules (BLOCKING).")
    print(f"Then {len(QUALITY_MONITOR_MODULES)} quality monitor module(s) -- run and reported,")
    print("not blocking. Zero paid model calls in either bucket.")
    print(f"NOT run here -- {len(LIVE_INFRA_MODULES)} live-infrastructure modules, real reasons:")
    for m, why in sorted(LIVE_INFRA_MODULES.items()):
        print(f"  - {m}: {why}")
    print("These are excluded for a stated environmental reason, NOT skipped or")
    print("weakened. They still need to run where the real dependency exists.")
    print("=" * 72)

    suite = unittest.defaultTestLoader.loadTestsFromNames(HERMETIC_MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    monitor = run_quality_monitors()

    print("\n" + "=" * 72)
    print("RELEASE HEALTH (blocking -- these set the exit code)")
    print(f"tests run : {result.testsRun}")
    print(f"failures  : {len(result.failures)}")
    print(f"errors    : {len(result.errors)}")
    print(f"skipped   : {len(result.skipped)}")
    if monitor is not None:
        print("\nQUALITY MONITORS (visible, NOT blocking -- see the detail above)")
        print(f"tests run : {monitor.testsRun}")
        print(f"failures  : {len(monitor.failures)}")
        print(f"errors    : {len(monitor.errors)}")
        for case, _ in list(monitor.failures) + list(monitor.errors):
            print(f"  RED: {case.id()}")

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
