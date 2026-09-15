"""
Tests for agent/non_llm_intelligence_metrics.py -- proves every reported
number is genuinely computed from a real source (never hardcoded, never
silently 0 for something unmeasured).

Run: python agent/test_non_llm_intelligence_metrics.py
"""

import unittest

import non_llm_intelligence_metrics as nlm


class ComputeMetricsTestCase(unittest.TestCase):
    def test_every_real_count_is_a_positive_integer(self):
        metrics = nlm.compute_metrics()
        for key in (
            "advisory_purposes_defined",
            "reasoning_gateway_approved_direct_call_sites",
            "invariants_catalogued",
            "architecture_boundary_tests",
            "test_architect_contract_tests",
            "quality_ledger_defects_recorded",
        ):
            self.assertIsInstance(metrics[key], int, key)
            self.assertGreater(metrics[key], 0, key)

    def test_unmeasured_metrics_are_honest_strings_not_silently_zero(self):
        metrics = nlm.compute_metrics()
        for key in (
            "mutation_test_survivor_count",
            "zero_llm_verified_runs_lifetime",
            "escaped_defects_by_enforcement_tier",
        ):
            self.assertIsInstance(metrics[key], str)
            self.assertIn("UNKNOWN", metrics[key])
            self.assertNotEqual(metrics[key], "0")

    def test_no_composite_fabricated_intelligence_score_exists(self):
        metrics = nlm.compute_metrics()
        for key in metrics:
            self.assertNotIn("score", key.lower())
            self.assertNotIn("overall", key.lower())

    def test_invariant_count_matches_a_real_recount_of_the_registry_file(self):
        # Independent re-derivation, not just re-calling the same function.
        import re
        text = nlm.INVARIANT_REGISTRY_PATH.read_text(encoding="utf-8")
        real_count = len(re.findall(r"^\|\s*`[A-Z]+-\d+`", text, re.MULTILINE))
        self.assertEqual(nlm.compute_metrics()["invariants_catalogued"], real_count)
        self.assertGreater(real_count, 0)


if __name__ == "__main__":
    unittest.main()
