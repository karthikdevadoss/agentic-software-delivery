"""
Focused regression tests for agent/estimation.py — pre-run token/cost
estimation for Workbench requirements. Uses a temporary run-history file
(never the real agent/web_run_history.jsonl) so these tests never depend
on or pollute real recorded runs.

Run: python agent/test_estimation.py
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import estimation


def _history_record(complexity, total_tokens_split, is_mock=False):
    input_tokens, output_tokens = total_tokens_split
    return {
        "is_mock": is_mock,
        "risk_assessment": {"complexity": complexity, "risk": "LOW", "decision": "auto"},
        "model_usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


class EstimationTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.history_path = Path(self.tmpdir.name) / "web_run_history.jsonl"
        self.patcher = mock.patch.object(estimation, "RUN_HISTORY_PATH", self.history_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmpdir.cleanup()

    def _write_history(self, records):
        with self.history_path.open("w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    def test_no_history_falls_back_to_labeled_low_confidence_heuristic(self):
        # No file at all — must not raise, must not block, must be honest.
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        self.assertTrue(result["available"])
        self.assertEqual(result["confidence"], "LOW")
        self.assertIn("heuristic", result["basis"])

    def test_enough_history_produces_a_higher_confidence_estimate(self):
        records = [_history_record("TINY", (1000, 2000)) for _ in range(estimation.MIN_HISTORICAL_SAMPLES)]
        self._write_history(records)
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        self.assertTrue(result["available"])
        self.assertIn(result["confidence"], ("MEDIUM", "HIGH"))
        self.assertIn("historical", result["basis"])
        # All sample totals are identical (3000) -> degenerate-range guard
        # widens the high end (round(3000 * 1.2) = 3600) rather than
        # reporting a zero-width [3000, 3000] range.
        self.assertEqual(result["estimated_total_tokens_range"], [3000, 3600])

    def test_mock_runs_are_never_used_as_comparable_history(self):
        records = [_history_record("TINY", (1000, 2000), is_mock=True) for _ in range(10)]
        self._write_history(records)
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        # With only mock runs available, this must fall back to the heuristic,
        # not silently treat mock (zero-API-cost) runs as real comparables.
        self.assertEqual(result["confidence"], "LOW")

    def test_different_complexity_runs_are_not_comparable(self):
        records = [_history_record("LARGE", (50000, 60000)) for _ in range(10)]
        self._write_history(records)
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        self.assertEqual(result["confidence"], "LOW")  # LARGE history must not leak into a TINY estimate

    def test_estimate_includes_a_cost_range_when_pricing_is_available(self):
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        self.assertIsNotNone(result["estimated_cost_range_usd"])
        low, high = result["estimated_cost_range_usd"]
        self.assertLessEqual(low, high)

    def test_result_always_carries_a_method_version_for_future_accuracy_tracking(self):
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        self.assertEqual(result["method_version"], estimation.ESTIMATE_METHOD_VERSION)

    def test_unrecognized_complexity_is_honestly_unavailable(self):
        result = estimation.estimate_run({"complexity": "NOT_A_REAL_BUCKET", "risk": "LOW"})
        self.assertFalse(result["available"])
        self.assertIn("ESTIMATE NOT AVAILABLE", result["reason"])

    def test_never_raises_on_a_corrupt_history_file(self):
        self.history_path.write_text("{not valid json\nnot json either\n", encoding="utf-8")
        result = estimation.estimate_run({"complexity": "TINY", "risk": "LOW"})
        self.assertTrue(result["available"])  # falls back to heuristic, doesn't crash


if __name__ == "__main__":
    unittest.main()
