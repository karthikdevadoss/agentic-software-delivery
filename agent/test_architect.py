"""
Deterministic Test Architect (Base Architecture V3 Section 9): the
deterministic-first portion of "what must be proven?" Given a real
changed-file set and its already-computed TIA selection (both from
existing deterministic sources -- agent/change_risk.py,
agent/test_impact_analysis.py -- never guessed), cross-checks it against
a small, real, structured mirror of docs/INVARIANT_REGISTRY.md's
highest-value invariants: does this change touch code a known invariant
governs, and if so, is that invariant's real proving test actually in
the selected set?

This is deliberately NOT a general LLM-authored Test Contract generator.
Everything here is derivable deterministically (file path -> known
invariant -> known proving test -> selected-or-not), so it IS generated
deterministically, per the directive's own instruction. An optional LLM
test-idea advisor for genuinely novel/ambiguous cases is real future work
(not built this session -- see docs/ARCHITECTURE_V3_DECISIONS.md) and
could only ever ADD suggestions here, never remove or weaken a matched
invariant's requirement.
"""

from dataclasses import dataclass, field

# A small, real, curated mirror of docs/INVARIANT_REGISTRY.md's
# highest-value rows -- (invariant_id, path keywords that indicate this
# invariant is relevant, the real test class that proves it, the real
# business meaning). Keeping this a short, explicit, human-reviewed list
# (not auto-derived from the markdown table) is a deliberate choice: an
# invariant only belongs here once its proving test has actually been
# verified to catch a real violation (see docs/TESTING_ARCHITECTURE_V2.md's
# mutation-testing section for BIZ-01's proof).
INVARIANTS = (
    {
        "id": "BIZ-01",
        "meaning": "N identical enrollment requests always result in exactly 1 active plan, for any N",
        "path_keywords": ("ContractPlan",),
        "proving_test": "TriageScenarioAIntegrationTest",
    },
    {
        "id": "SEC-01",
        "meaning": "A USER can never read/write another customer's data",
        "path_keywords": ("WorkspaceAccessGuard",),
        "proving_test": "SecurityIntegrationTest",
    },
    {
        "id": "SEC-02",
        "meaning": "A USER can never perform ADMIN-only actions",
        "path_keywords": ("SecurityConfig",),
        "proving_test": "SecurityIntegrationTest",
    },
    {
        "id": "APR-01",
        "meaning": "AI output never directly advances a Run's workflow state (approve_edit/reject_edit never model-dispatchable)",
        "path_keywords": ("execution_tools.py",),
        "proving_test": "test_execution_tools",
    },
    {
        "id": "APR-02",
        "meaning": "A run's status can only ever be one of the known states",
        "path_keywords": ("web_server.py",),
        "proving_test": "test_web_server",
    },
)


@dataclass
class TestContract:
    changed_paths: list
    risk: str
    blast_radius: str
    matched_invariants: list = field(default_factory=list)
    uncovered_invariants: list = field(default_factory=list)

    @property
    def fully_covered(self) -> bool:
        return not self.uncovered_invariants


def build_test_contract(paths: list, classification, selected_java_tests: list) -> TestContract:
    """paths: real changed file paths (e.g. from git diff). classification:
    a change_risk.ChangeClassification (or anything with .risk/.blast_radius).
    selected_java_tests: the real list TIA selected (agent/test_impact_analysis.py),
    or the special ALL_JAVA_MODULE_TESTS sentinel meaning "everything,"
    which trivially covers every invariant."""
    selected = set(selected_java_tests or [])
    all_java_selected = "__ALL_JAVA_MODULE_TESTS__" in selected or selected_java_tests == "ALL"

    matched = []
    uncovered = []
    for inv in INVARIANTS:
        touches = any(
            keyword in path
            for path in paths
            for keyword in inv["path_keywords"]
        )
        if not touches:
            continue
        covered = all_java_selected or inv["proving_test"] in selected
        entry = {**inv, "covered": covered}
        matched.append(entry)
        if not covered:
            uncovered.append(entry)

    return TestContract(
        changed_paths=list(paths),
        risk=getattr(classification, "risk", None),
        blast_radius=getattr(classification, "blast_radius", None),
        matched_invariants=matched,
        uncovered_invariants=uncovered,
    )
