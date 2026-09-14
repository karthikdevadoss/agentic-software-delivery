"""
Focused tests for agent/acceptance_contract.py (Architecture V2 §5) —
a standalone, not-yet-wired-in design. These tests prove the schema is
internally consistent with the real runtime it describes (allowed
terminal outcomes, known deterministic gates), not that it drives any
live run yet.

Run: python agent/test_acceptance_contract.py
"""

import unittest

import acceptance_contract as ac
import web_server as ws


class AcceptanceContractTestCase(unittest.TestCase):
    def test_valid_contract_has_no_problems(self):
        contract = ac.example_create_customer_contract()
        self.assertEqual(contract.validate(), [])

    def test_empty_requirement_text_is_invalid(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="", target_application="y",
            expected_observable_effect="z",
        )
        self.assertIn("requirement_text is empty", contract.validate())

    def test_empty_expected_effect_is_invalid(self):
        """The exact lesson from the false-success incident: a contract
        with no independently-checkable effect is not acceptable."""
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="",
        )
        problems = contract.validate()
        self.assertTrue(any("expected_observable_effect" in p for p in problems))

    def test_unknown_gate_is_rejected(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            required_gates=["made_up_gate_that_does_not_exist"],
        )
        problems = contract.validate()
        self.assertTrue(any("unknown gate" in p for p in problems))

    def test_disallowed_terminal_outcome_is_rejected(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            allowed_terminal_outcomes=["SUCCESS_MAYBE"],
        )
        problems = contract.validate()
        self.assertTrue(any("cannot actually produce" in p for p in problems))

    def test_allowed_terminal_outcomes_match_the_real_runtime(self):
        """The contract's own allowed outcomes must never drift from the
        actual runtime's terminal states (agent/web_server.py's
        TERMINAL_RUN_STATES) — this test fails loudly if either changes
        without the other."""
        self.assertEqual(ac.ALLOWED_TERMINAL_OUTCOMES, ws.TERMINAL_RUN_STATES)

    def test_example_contract_serializes_to_a_plain_dict(self):
        contract = ac.example_create_customer_contract()
        d = contract.to_dict()
        self.assertEqual(d["requirement_id"], "create-button-label-2026-09-11")
        self.assertIn("Create Customer", d["expected_observable_effect"])


class TestingArchitectureV1CategoryFieldsTestCase(unittest.TestCase):
    """Testing Architecture V1 §A: the categorized verification-contract
    fields added on top of the existing V2 schema."""

    def test_contract_with_no_category_fields_is_still_valid(self):
        """Most small changes legitimately don't need every category —
        omitting them must never itself be a validation error."""
        contract = ac.example_create_customer_contract()
        self.assertEqual(contract.validate(), [])

    def test_unknown_verification_category_is_rejected(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            verification_categories=["NOT_A_REAL_CATEGORY"],
        )
        problems = contract.validate()
        self.assertTrue(any("unknown category" in p for p in problems))

    def test_security_category_requires_security_expectations(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            verification_categories=["SECURITY"],
        )
        problems = contract.validate()
        self.assertTrue(any("security_expectations is empty" in p for p in problems))

    def test_security_category_with_expectations_filled_in_is_valid(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            verification_categories=["SECURITY"],
            security_expectations="no token -> 401; wrong scope -> 403",
        )
        self.assertEqual(contract.validate(), [])

    def test_database_category_requires_persistence_expectations(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            verification_categories=["DATABASE"],
        )
        problems = contract.validate()
        self.assertTrue(any("persistence_expectations is empty" in p for p in problems))

    def test_bad_risk_level_is_rejected(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            risk="SUPER_HIGH",
        )
        problems = contract.validate()
        self.assertTrue(any("risk=" in p for p in problems))

    def test_bad_blast_radius_is_rejected(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            blast_radius="EVERYWHERE",
        )
        problems = contract.validate()
        self.assertTrue(any("blast_radius=" in p for p in problems))

    def test_valid_risk_and_blast_radius_pass(self):
        contract = ac.AcceptanceContract(
            requirement_id="x", requirement_text="do something",
            target_application="y", expected_observable_effect="z",
            risk="HIGH", blast_radius="CROSS_MODULE",
        )
        self.assertEqual(contract.validate(), [])


if __name__ == "__main__":
    unittest.main()
