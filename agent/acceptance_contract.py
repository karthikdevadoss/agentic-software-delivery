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


# Deliberately compact category set (Testing Architecture V1 §A) — a
# contract states WHICH of these categories apply and what a passing case
# looks like in each, rather than a rigid schema forcing every category to
# be filled in for every requirement (most small changes only touch 1-2).
VERIFICATION_CATEGORIES = frozenset({
    "FUNCTIONAL", "SECURITY", "DATABASE", "UI", "INTEGRATION",
    "OBSERVABILITY", "PRODUCTION",
})

KNOWN_RISK_LEVELS = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
KNOWN_BLAST_RADII = frozenset({"LOCAL", "MODULE", "CROSS_MODULE", "SYSTEM"})


@dataclass
class AcceptanceContract:
    requirement_id: str
    requirement_text: str
    target_application: str
    expected_observable_effect: str
    affected_scope: Optional[str] = None
    risk: Optional[str] = None  # mirrors risk_policy.classify()'s "risk" field when known
    blast_radius: Optional[str] = None  # mirrors agent/change_risk.py's blast_radius once real files are known (post-implementation) — None before implementation starts, which is expected
    required_gates: list = field(default_factory=list)
    testing_expectation: str = "run tests if app/src/test/java has any test file; otherwise TESTING — NOT APPLICABLE is the correct terminal state, not a failure"
    production_verification_expectation: str = "the exact expected_observable_effect must be found in the live production response, not merely HTTP 200"
    allowed_terminal_outcomes: list = field(default_factory=lambda: sorted(ALLOWED_TERMINAL_OUTCOMES))
    evidence_requirements: list = field(default_factory=lambda: [
        "run_id", "commit_sha_if_any", "deterministic_gate_results",
        "actual_token_and_cost_usage", "independent_production_fetch_result",
    ])
    # Testing Architecture V1 §A additions — captured BEFORE implementation
    # starts, per this task's own instruction ("critical acceptance
    # criteria must be established before implementation... builders must
    # not silently weaken them just to make code pass"). All optional at
    # the dataclass level (a TINY UI-text change legitimately has no
    # negative_cases or security_expectations worth writing down) but
    # validate() checks internal consistency of whatever IS provided.
    verification_categories: list = field(default_factory=list)  # subset of VERIFICATION_CATEGORIES that actually apply
    acceptance_criteria: list = field(default_factory=list)  # plain-language pass conditions, written before implementation
    negative_cases: list = field(default_factory=list)  # what must NOT happen / must be rejected
    security_expectations: Optional[str] = None
    persistence_expectations: Optional[str] = None
    ui_expectations: Optional[str] = None
    integration_expectations: Optional[str] = None
    nfrs: Optional[str] = None  # non-functional requirements (latency/throughput/etc.) where relevant; None when not relevant, never a fabricated number
    required_test_categories: list = field(default_factory=list)  # e.g. ["UNIT", "SPRING_SLICE", "SECURITY", "BROWSER_E2E"] — see docs/TESTING_ARCHITECTURE_V1.md §G for the full level taxonomy

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
        if self.risk is not None and self.risk not in KNOWN_RISK_LEVELS:
            problems.append(f"risk={self.risk!r} is not one of {sorted(KNOWN_RISK_LEVELS)}")
        if self.blast_radius is not None and self.blast_radius not in KNOWN_BLAST_RADII:
            problems.append(f"blast_radius={self.blast_radius!r} is not one of {sorted(KNOWN_BLAST_RADII)}")
        bad_categories = set(self.verification_categories) - VERIFICATION_CATEGORIES
        if bad_categories:
            problems.append(f"verification_categories includes unknown category(ies): {sorted(bad_categories)}")
        if "SECURITY" in self.verification_categories and not self.security_expectations:
            problems.append("verification_categories includes SECURITY but security_expectations is empty")
        if "DATABASE" in self.verification_categories and not self.persistence_expectations:
            problems.append("verification_categories includes DATABASE but persistence_expectations is empty")
        if "UI" in self.verification_categories and not self.ui_expectations:
            problems.append("verification_categories includes UI but ui_expectations is empty")
        if "INTEGRATION" in self.verification_categories and not self.integration_expectations:
            problems.append("verification_categories includes INTEGRATION but integration_expectations is empty")
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
