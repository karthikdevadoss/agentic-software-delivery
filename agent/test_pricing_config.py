"""
Focused regression tests for agent/pricing_config.py — the versioned
pricing table backing Workbench's "ACTUAL AI USAGE" cost calculation.

Run: python agent/test_pricing_config.py
"""

import unittest

import pricing_config


class PricingTableTestCase(unittest.TestCase):
    def test_known_model_returns_a_pricing_entry(self):
        pricing = pricing_config.get_pricing("anthropic", "claude-sonnet-5")
        self.assertIsNotNone(pricing)
        for key in ("input", "output", "cache_write", "cache_read"):
            self.assertIn(key, pricing)

    def test_unknown_model_returns_none_not_a_fabricated_price(self):
        self.assertIsNone(pricing_config.get_pricing("anthropic", "claude-nonexistent-9"))

    def test_pricing_version_and_verified_date_are_present(self):
        self.assertTrue(pricing_config.PRICING_VERSION)
        self.assertTrue(pricing_config.PRICING_VERIFIED_DATE)
        self.assertTrue(pricing_config.PRICING_SOURCE)


class CalculateCostTestCase(unittest.TestCase):
    def test_known_model_cost_is_calculated_from_the_versioned_table(self):
        # 1,000,000 input tokens at $2.00/MTok = exactly $2.00 for a known
        # model — pins the calculation to the real verified table, not an
        # arbitrary constant duplicated in this test.
        result = pricing_config.calculate_cost("anthropic", "claude-sonnet-5", input_tokens=1_000_000)
        self.assertTrue(result["available"])
        self.assertAlmostEqual(result["total_usd"], 2.00, places=6)
        self.assertEqual(result["pricing_version"], pricing_config.PRICING_VERSION)

    def test_output_and_cache_tokens_are_all_included(self):
        result = pricing_config.calculate_cost(
            "anthropic", "claude-sonnet-5",
            input_tokens=1_000_000, output_tokens=1_000_000,
            cache_read_tokens=1_000_000, cache_write_tokens=1_000_000,
        )
        pricing = pricing_config.get_pricing("anthropic", "claude-sonnet-5")
        expected = pricing["input"] * 1_000_000 + pricing["output"] * 1_000_000 \
            + pricing["cache_read"] * 1_000_000 + pricing["cache_write"] * 1_000_000
        self.assertAlmostEqual(result["total_usd"], expected, places=6)

    def test_zero_usage_costs_zero(self):
        result = pricing_config.calculate_cost("anthropic", "claude-sonnet-5")
        self.assertTrue(result["available"])
        self.assertEqual(result["total_usd"], 0.0)

    def test_unknown_model_is_unavailable_not_zero(self):
        """An unpriceable model must show as genuinely unpriceable — never
        silently reported as costing $0.00, which would look like a real,
        confirmed free run."""
        result = pricing_config.calculate_cost("anthropic", "claude-nonexistent-9", input_tokens=1000)
        self.assertFalse(result["available"])
        self.assertIn("reason", result)
        self.assertNotIn("total_usd", result)


if __name__ == "__main__":
    unittest.main()
