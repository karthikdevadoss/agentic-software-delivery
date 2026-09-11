"""
Acceptance Contract — Architecture V2 foundation (docs/ARCHITECTURE_V2.md §5).

A small, machine-readable definition of what "done" means for a single
changing requirement, captured BEFORE any implementation work starts.
This is deliberately the smallest useful schema, not a general workflow
engine — see docs/CONSTITUTION.md §7 (don't waste effort on unneeded
infrastructure) and §6 (don't overengineer).

STATUS: DESIGNED + standalone-tested. NOT wired into agent/web_server.py's
live trainer pipeline in this task (see docs/ARCHITECTURE_V2.md §14 — no
production cutover in this task). Intended future use: the orchestrator
constructs one of these per requirement, the implementer works toward it,
and the qa-evaluator subagent (.claude/agents/qa-evaluator.md) evaluates
real evidence against it — never the other way around.

This module deliberately does NOT duplicate any deterministic gate.
`required_gates` names gates that already exist as real code
(risk_policy.classify, _tests_applicable, _decide_deployment_outcome) —
it never re-implements their logic.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional

# The only terminal outcomes this project's runtime actually produces
# today (agent/web_server.py's TERMINAL_RUN_STATES) — an Acceptance
# Contract must never invent a terminal outcome the runtime can't emit.
ALLOWED_TERMINAL_OUTCOMES = frozenset({
    "COMPLETED", "FAILED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN",
})

# Deterministic gates already implemented as real code (see
# docs/ARCHITECTURE_V2_KNOWLEDGE_MAP.md). A contract references these by
# name; it never restates their logic.
KNOWN_DETERMINISTIC_GATES = frozenset({
    "repository_workspace_ready",   # agent/web_server.py::_check_repository_workspace_ready
    "risk_policy_auto",             # agent/risk_policy.py::classify
    "compile_succeeds",             # agent/build_tools.py / run_controlled_compile
    "test_policy_terminal",         # agent/web_server.py::_tests_applicable + test gating
    "secret_scan_clean",            # existing git-workflow secret scan discipline
    "deployment_active_and_content_verified",  # agent/web_server.py::_decide_deployment_outcome
})


@dataclass
class AcceptanceContract:
    requirement_id: str
    requirement_text: str
    target_application: str
    expected_observable_effect: str
    affected_scope: Optional[str] = None
    risk: Optional[str] = None  # mirrors risk_policy.classify()'s "risk" field when known
    required_gates: list = field(default_factory=list)
    testing_expectation: str = "run tests if app/src/test/java has any test file; otherwise TESTING — NOT APPLICABLE is the correct terminal state, not a failure"
    production_verification_expectation: str = "the exact expected_observable_effect must be found in the live production response, not merely HTTP 200"
    allowed_terminal_outcomes: list = field(default_factory=lambda: sorted(ALLOWED_TERMINAL_OUTCOMES))
    evidence_requirements: list = field(default_factory=lambda: [
        "run_id", "commit_sha_if_any", "deterministic_gate_results",
        "actual_token_and_cost_usage", "independent_production_fetch_result",
    ])

    def validate(self) -> list:
        """Returns a list of problems (empty = valid). Never raises —
        callers (the future orchestrator, or a human reviewing a contract
        before approving work) decide what to do with problems."""
        problems = []
        if not self.requirement_id.strip():
            problems.append("requirement_id is empty")
        if not self.requirement_text.strip():
            problems.append("requirement_text is empty")
        if not self.target_application.strip():
            problems.append("target_application is empty")
        if not self.expected_observable_effect.strip():
            problems.append("expected_observable_effect is empty — a contract with no way to independently verify success is not acceptable per docs/LESSONS.md's false-success incident")
        unknown_gates = set(self.required_gates) - KNOWN_DETERMINISTIC_GATES
        if unknown_gates:
            problems.append(f"required_gates references unknown gate(s) not implemented anywhere: {sorted(unknown_gates)}")
        bad_outcomes = set(self.allowed_terminal_outcomes) - ALLOWED_TERMINAL_OUTCOMES
        if bad_outcomes:
            problems.append(f"allowed_terminal_outcomes includes outcome(s) the runtime cannot actually produce: {sorted(bad_outcomes)}")
        return problems

    def to_dict(self) -> dict:
        return asdict(self)


def example_create_customer_contract() -> AcceptanceContract:
    """The exact worked example from docs/ARCHITECTURE_V2.md §5 — a real
    requirement this project already executed for real (run
    trainer-4733d1c0, commit 12dfbd8, independently confirmed live)."""
    return AcceptanceContract(
        requirement_id="create-button-label-2026-09-11",
        requirement_text='Change the Create button label from "Create" to "Create Customer"',
        target_application="https://agentic-delivery-customer-app-production.up.railway.app/",
        expected_observable_effect='the real production HTML contains <button id="create-btn">Create Customer</button>',
        affected_scope="app/src/main/resources/static/index.html",
        risk="LOW",
        required_gates=[
            "repository_workspace_ready", "risk_policy_auto", "compile_succeeds",
            "test_policy_terminal", "deployment_active_and_content_verified",
        ],
    )
