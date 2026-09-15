"""
Tests for agent/test_architect.py -- proves the deterministic Test
Contract cross-check is real, using this session's own actual TIA gap
(Section 8) as ground truth: before that fix, a ContractPlanService.java
change's selected tests did NOT include TriageScenarioAIntegrationTest,
which this module should have flagged as an uncovered BIZ-01 invariant;
after the fix, it's covered.

Run: python agent/test_test_architect.py
"""

import unittest
from dataclasses import dataclass

import test_architect as ta


@dataclass
class _FakeClassification:
    risk: str = "MEDIUM"
    blast_radius: str = "MODULE"


class TestContractTestCase(unittest.TestCase):
    def test_a_change_touching_no_known_invariant_has_nothing_matched_or_uncovered(self):
        contract = ta.build_test_contract(
            ["app/src/main/java/com/example/customer/dto/SomeUnrelatedDto.java"],
            _FakeClassification(), ["SomeUnrelatedDtoTest"],
        )
        self.assertEqual(contract.matched_invariants, [])
        self.assertEqual(contract.uncovered_invariants, [])
        self.assertTrue(contract.fully_covered)

    def test_the_real_pre_section_8_selection_would_have_been_flagged_uncovered(self):
        # The exact real selection verify_change.build_plan() returned for
        # ContractPlanService.java BEFORE this session's Section 8 fix.
        pre_fix_selection = ["ContractPlanServiceTest", "ContractPlanControllerIntegrationTest"]
        contract = ta.build_test_contract(
            ["app/src/main/java/com/example/customer/service/ContractPlanService.java"],
            _FakeClassification(), pre_fix_selection,
        )
        uncovered_ids = {inv["id"] for inv in contract.uncovered_invariants}
        self.assertIn("BIZ-01", uncovered_ids, (
            "This is the real gap Section 8 found and fixed -- if this ever "
            "regresses (BIZ-01's proving test dropped from a real selection "
            "again), this contract must flag it as uncovered."
        ))
        self.assertFalse(contract.fully_covered)

    def test_the_real_post_section_8_selection_is_fully_covered(self):
        post_fix_selection = ["ContractPlanServiceTest", "ContractPlanControllerIntegrationTest", "TriageScenarioAIntegrationTest"]
        contract = ta.build_test_contract(
            ["app/src/main/java/com/example/customer/service/ContractPlanService.java"],
            _FakeClassification(), post_fix_selection,
        )
        self.assertTrue(contract.fully_covered, contract.uncovered_invariants)
        matched_ids = {inv["id"] for inv in contract.matched_invariants}
        self.assertIn("BIZ-01", matched_ids)

    def test_a_change_touching_two_invariant_governed_files_matches_both(self):
        contract = ta.build_test_contract(
            [
                "app/src/main/java/com/example/customer/security/SecurityConfig.java",
                "app/src/main/java/com/example/customer/security/WorkspaceAccessGuard.java",
            ],
            _FakeClassification(), ["SecurityIntegrationTest"],
        )
        matched_ids = {inv["id"] for inv in contract.matched_invariants}
        self.assertEqual(matched_ids, {"SEC-01", "SEC-02"})
        self.assertTrue(contract.fully_covered)

    def test_risk_and_blast_radius_are_carried_through_from_the_real_classification(self):
        contract = ta.build_test_contract([], _FakeClassification(risk="HIGH", blast_radius="CROSS_MODULE"), [])
        self.assertEqual(contract.risk, "HIGH")
        self.assertEqual(contract.blast_radius, "CROSS_MODULE")


if __name__ == "__main__":
    unittest.main()
