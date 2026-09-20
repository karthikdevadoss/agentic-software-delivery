import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backlog


def _fake_backlog(items):
    return {"items": items}


def _item(id_, size="SMALL", confidence="HIGH", pattern_type="apply_known_pattern",
          actual_ratio=0.3, contaminated=False, estimate_range="10-15 min"):
    it = {
        "id": id_, "size": size, "confidence": confidence, "pattern_type": pattern_type,
        "actual_ratio": actual_ratio, "contaminated": contaminated,
        "estimate_range": estimate_range,
    }
    return it


class ParseMidpointTestCase(unittest.TestCase):
    def test_real_convention_parses_correctly(self):
        self.assertEqual(backlog._parse_midpoint("30-50 min"), 40.0)
        self.assertEqual(backlog._parse_midpoint("10-15 min"), 12.5)

    def test_missing_field_returns_none(self):
        self.assertIsNone(backlog._parse_midpoint(None))
        self.assertIsNone(backlog._parse_midpoint(""))

    def test_non_matching_format_returns_none_not_a_guess(self):
        self.assertIsNone(backlog._parse_midpoint("about an hour"))
        self.assertIsNone(backlog._parse_midpoint("2-3 hours"))


class SuggestEstimateTestCase(unittest.TestCase):
    """Real regression coverage for a real fix: four sprints of retro
    narrative were never mechanically fed back into the next estimate.
    This is the tool built to close that gap -- it must be proven honest
    about thin samples and correct about excluding contaminated data,
    not just proven to run without raising."""

    def _with_items(self, items):
        return patch.object(backlog, "load_backlog", return_value=_fake_backlog(items))

    def test_zero_matches_is_insufficient_history_not_a_fabricated_number(self):
        with self._with_items([]):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern")
        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result["n"], 0)
        self.assertNotIn("median_ratio", result)

    def test_fewer_than_three_matches_is_flagged_insufficient_even_with_real_data(self):
        items = [
            _item("BL-001", actual_ratio=0.2),
            _item("BL-002", actual_ratio=0.4),
        ]
        with self._with_items(items):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern")
        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")
        self.assertEqual(result["n"], 2)
        self.assertIn("median_ratio", result)  # still computed, just flagged low-confidence
        self.assertIn("reason", result)

    def test_three_or_more_matches_is_computed(self):
        items = [
            _item("BL-001", actual_ratio=0.2),
            _item("BL-002", actual_ratio=0.3),
            _item("BL-003", actual_ratio=0.4),
        ]
        with self._with_items(items):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern")
        self.assertEqual(result["status"], "COMPUTED")
        self.assertEqual(result["n"], 3)
        self.assertAlmostEqual(result["median_ratio"], 0.3)

    def test_contaminated_items_are_excluded_from_the_reference_class(self):
        items = [
            _item("BL-001", actual_ratio=0.2, contaminated=False),
            _item("BL-002", actual_ratio=0.3, contaminated=False),
            _item("BL-003", actual_ratio=0.4, contaminated=False),
            _item("BL-004", actual_ratio=99.0, contaminated=True),  # a real stall/takeover outlier
        ]
        with self._with_items(items):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern")
        self.assertEqual(result["n"], 3)
        self.assertNotIn("BL-004", result["matched_items"])
        self.assertAlmostEqual(result["median_ratio"], 0.3)

    def test_null_ratio_items_are_excluded_not_treated_as_zero(self):
        items = [
            _item("BL-001", actual_ratio=0.2),
            _item("BL-002", actual_ratio=0.3),
            _item("BL-003", actual_ratio=None),  # e.g. BL-032, a real item with no clean ratio
        ]
        with self._with_items(items):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern")
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["status"], "INSUFFICIENT_HISTORY")

    def test_mismatched_size_confidence_or_pattern_type_is_excluded(self):
        items = [
            _item("BL-001", size="MEDIUM", actual_ratio=0.2),
            _item("BL-002", size="MEDIUM", actual_ratio=0.3),
            _item("BL-003", confidence="LOW", actual_ratio=0.4),
            _item("BL-004", pattern_type="first_of_kind", actual_ratio=0.8),
            _item("BL-005", size="SMALL", confidence="HIGH", pattern_type="apply_known_pattern", actual_ratio=0.25),
        ]
        with self._with_items(items):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern")
        self.assertEqual(result["n"], 1)
        self.assertEqual(result["matched_items"], ["BL-005"])

    def test_computed_suggestion_scales_the_real_raw_midpoint(self):
        items = [
            _item("BL-001", actual_ratio=0.2),
            _item("BL-002", actual_ratio=0.3),
            _item("BL-003", actual_ratio=0.4),
        ]
        with self._with_items(items):
            result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern", "10-15 min")
        self.assertEqual(result["raw_midpoint_min"], 12.5)
        # source rounds to 1 decimal place; round(3.75, 1) == 3.8 in real
        # Python float/banker's-rounding behavior, confirmed directly
        self.assertEqual(result["suggested_midpoint_min"], round(12.5 * 0.3, 1))

    def test_this_project_s_own_real_backfilled_data_is_readable_end_to_end(self):
        """Not mocked -- exercises the actual docs/BACKLOG.json on disk to
        confirm the real backfill (Sprint 4 Scrum cleanup) is genuinely
        well-formed and queryable, not just valid JSON."""
        result = backlog.suggest_estimate("SMALL", "HIGH", "apply_known_pattern", "10-15 min")
        self.assertIn(result["status"], ("COMPUTED", "INSUFFICIENT_HISTORY"))
        self.assertIsInstance(result["n"], int)
        self.assertGreaterEqual(result["n"], 0)


if __name__ == "__main__":
    unittest.main()
