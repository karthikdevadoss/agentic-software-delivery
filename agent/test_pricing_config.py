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


class VersionedPricingHistoryTestCase(unittest.TestCase):
    """A future price change must never silently rewrite a past run's
    cost -- each entry is dated, and as_of selects the rate that actually
    applied on a given date, never today's rate mislabeled with an old
    version string."""

    def test_as_of_none_returns_the_current_latest_entry(self):
        result = pricing_config.calculate_cost(
            "anthropic", "claude-sonnet-5", input_tokens=1_000_000,
        )
        self.assertEqual(result["pricing_version"], pricing_config.PRICING_VERSION)
        self.assertEqual(result["pricing_verified_date"], pricing_config.PRICING_VERIFIED_DATE)

    def test_as_of_a_date_before_any_known_entry_is_unavailable_not_a_wrong_guess(self):
        """A run from before this model's earliest verified pricing entry
        existed must never be silently priced using a rate that didn't
        apply yet."""
        result = pricing_config.calculate_cost(
            "anthropic", "claude-sonnet-5", input_tokens=1000, as_of="2020-01-01",
        )
        self.assertFalse(result["available"])
        self.assertIn("reason", result)

    def test_as_of_on_or_after_an_entrys_effective_date_selects_it(self):
        pricing = pricing_config.get_pricing("anthropic", "claude-sonnet-5", as_of="2026-09-10")
        self.assertIsNotNone(pricing)
        self.assertEqual(pricing["input"], 2.00 / 1_000_000)

    def test_get_pricing_for_a_real_model_still_returns_all_rate_keys(self):
        pricing = pricing_config.get_pricing("anthropic", "claude-sonnet-5")
        for key in ("input", "output", "cache_write", "cache_read"):
            self.assertIn(key, pricing)


if __name__ == "__main__":
    unittest.main()
