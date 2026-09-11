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


if __name__ == "__main__":
    unittest.main()
