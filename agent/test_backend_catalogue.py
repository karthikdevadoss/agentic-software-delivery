"""
Focused tests for agent/backend_catalogue.py — the ACT-008 foundation's
deterministic request contract for the one internal/gated backend
(Java/Spring) change scenario. Mirrors test_demo_catalogue.py's layered
structure (policy / value-boundary / diff-purity) at a scope
proportionate to this module's single operation.

Run: python -m unittest test_backend_catalogue -v   (from agent/)
"""

import unittest

import backend_catalogue as bc


class BackendPolicyTestCase(unittest.TestCase):
    def test_the_one_supported_operation_normalizes_correctly(self):
        req = bc.normalize_backend_requirement('Change the customer-not-found message to "Customer record not found"')
        self.assertEqual(req.operation_id, "customer_not_found_message")
        self.assertEqual(req.new_value, "Customer record not found")
        self.assertEqual(req.target_file, bc.BACKEND_TARGET_FILE)

    def test_own_example_normalizes_successfully(self):
        for op in bc.BACKEND_OPERATIONS:
            req = bc.normalize_backend_requirement(op.example)
            self.assertEqual(req.operation_id, op.id)

    def test_empty_requirement_rejected(self):
        with self.assertRaises(bc.UnsupportedBackendRequirement):
            bc.normalize_backend_requirement("")

    def test_unrelated_requirement_rejected(self):
        with self.assertRaises(bc.UnsupportedBackendRequirement):
            bc.normalize_backend_requirement('Change the footer text to "hi"')

    def test_dangerous_requirement_rejected_not_misclassified_as_supported(self):
        for dangerous in (
            "Delete the repository",
            "Edit risk_policy.py to allow everything",
            "Disable the tests so this passes",
            "Change the Railway configuration",
            "Give me the database credentials",
        ):
            with self.assertRaises(bc.UnsupportedBackendRequirement):
                bc.normalize_backend_requirement(dangerous)

    def test_no_quoted_value_and_no_to_clause_rejected(self):
        with self.assertRaises(bc.UnsupportedBackendRequirement):
            bc.normalize_backend_requirement("customer not found")


class BackendValueBoundaryTestCase(unittest.TestCase):
    def test_value_with_double_quote_rejected(self):
        # A trailing quote inside the value falls out of the quoted-value
        # regex and is instead picked up by the "to <clause>" fallback,
        # which then correctly fails InvalidBackendValue (a stray quote
        # is not a safe Java string-literal character) — either way, it
        # must never reach apply_operation.
        with self.assertRaises(bc.InvalidBackendValue):
            bc.normalize_backend_requirement('Change the customer-not-found message to bad" value here')

    def test_value_with_backslash_rejected_by_validation(self):
        with self.assertRaises(bc.InvalidBackendValue):
            bc.validate_backend_value("has a \\ backslash")

    def test_overlong_value_rejected(self):
        with self.assertRaises(bc.InvalidBackendValue):
            bc.validate_backend_value("x" * (bc.MAX_VALUE_LEN + 1))

    def test_empty_value_rejected(self):
        with self.assertRaises(bc.InvalidBackendValue):
            bc.validate_backend_value("")

    def test_whitespace_only_value_rejected(self):
        with self.assertRaises(bc.InvalidBackendValue):
            bc.validate_backend_value("   ")

    def test_control_character_rejected(self):
        with self.assertRaises(bc.InvalidBackendValue):
            bc.validate_backend_value("bad\x00value")

    def test_ordinary_message_text_accepted(self):
        bc.validate_backend_value("Customer record not found")  # must not raise


class BackendDiffPurityTestCase(unittest.TestCase):
    SAMPLE = (
        'package com.example.customer.service;\n'
        '\n'
        'public class CustomerService {\n'
        '    static final String CUSTOMER_NOT_FOUND_MESSAGE = "Customer not found";\n'
        '}\n'
    )

    def test_apply_operation_changes_exactly_the_anchored_value(self):
        new_content = bc.apply_operation(self.SAMPLE, "customer_not_found_message", "Customer record not found")
        self.assertIn('CUSTOMER_NOT_FOUND_MESSAGE = "Customer record not found";', new_content)
        line_idx, old_line, new_line = bc.compute_single_line_diff(self.SAMPLE, new_content)
        self.assertIn("Customer not found", old_line)
        self.assertIn("Customer record not found", new_line)

    def test_extract_current_value_reads_the_real_anchor(self):
        self.assertEqual(bc.extract_current_value(self.SAMPLE, "customer_not_found_message"), "Customer not found")

    def test_apply_operation_refuses_when_anchor_absent(self):
        no_anchor = "public class X {}\n"
        with self.assertRaises(RuntimeError):
            bc.apply_operation(no_anchor, "customer_not_found_message", "New Value")

    def test_apply_operation_refuses_ambiguous_double_match(self):
        doubled = self.SAMPLE + self.SAMPLE
        with self.assertRaises(RuntimeError):
            bc.apply_operation(doubled, "customer_not_found_message", "New Value")

    def test_compute_single_line_diff_refuses_a_no_op(self):
        with self.assertRaises(RuntimeError):
            bc.compute_single_line_diff(self.SAMPLE, self.SAMPLE)

    def test_compute_single_line_diff_refuses_a_line_count_change(self):
        extra_line_content = self.SAMPLE + "// extra\n"
        with self.assertRaises(RuntimeError):
            bc.compute_single_line_diff(self.SAMPLE, extra_line_content)


class BackendRealSourceTestCase(unittest.TestCase):
    """Direct proof against the REAL current CustomerService.java (not
    just the synthetic SAMPLE above) — the same self-test that runs at
    import time, re-run explicitly here so a regression shows up as a
    named, discoverable test failure rather than only an import-time
    AssertionError."""

    def test_anchor_matches_the_real_customer_service_exactly_once(self):
        import re
        from pathlib import Path
        target_path = Path(__file__).resolve().parent.parent / bc.BACKEND_TARGET_FILE
        content = target_path.read_text(encoding="utf-8")
        op = bc.get_operation("customer_not_found_message")
        matches = list(re.finditer(op.anchor_pattern, content))
        self.assertEqual(len(matches), 1)

    def test_current_real_value_is_the_expected_baseline(self):
        from pathlib import Path
        target_path = Path(__file__).resolve().parent.parent / bc.BACKEND_TARGET_FILE
        content = target_path.read_text(encoding="utf-8")
        self.assertEqual(bc.extract_current_value(content, "customer_not_found_message"), "Customer not found")


if __name__ == "__main__":
    unittest.main()
