"""
Unit tests for the eval SCORING MATH (agent/eval_runner.py) using
synthetic inputs — independent of the real curated corpus/embedding
model, so these stay fast and deterministic. The real eval numbers
against the real corpus come from running `python agent/eval_runner.py`
directly (see docs/PROJECT_STATE.json for the recorded baseline).

Run: python agent/test_eval_runner.py
"""

import unittest

import eval_runner as er


class RecallAtKTestCase(unittest.TestCase):
    def test_hit_within_k_is_true(self):
        self.assertTrue(er.recall_at_k(["x", "y", "z"], {"y"}, 3))

    def test_hit_outside_k_is_false(self):
        self.assertFalse(er.recall_at_k(["x", "y", "z"], {"z"}, 2))

    def test_no_hit_is_false(self):
        self.assertFalse(er.recall_at_k(["x", "y"], {"nope"}, 5))

    def test_empty_retrieved_list_is_false(self):
        self.assertFalse(er.recall_at_k([], {"anything"}, 5))


class ReciprocalRankTestCase(unittest.TestCase):
    def test_first_result_is_rank_one(self):
        self.assertEqual(er.reciprocal_rank(["x", "y"], {"x"}), 1.0)

    def test_second_result_is_one_half(self):
        self.assertEqual(er.reciprocal_rank(["x", "y"], {"y"}), 0.5)

    def test_no_match_is_zero(self):
        self.assertEqual(er.reciprocal_rank(["x", "y"], {"z"}), 0.0)


class DatasetLoadingTestCase(unittest.TestCase):
    def test_retrieval_dataset_loads_and_has_required_fields(self):
        dataset = er._load_dataset("retrieval_dataset.json")
        self.assertGreaterEqual(len(dataset["cases"]), 10)
        for case in dataset["cases"]:
            self.assertIn("id", case)
            self.assertIn("query", case)
            self.assertTrue(case["expected_sources"])

    def test_routing_dataset_loads_and_has_required_fields(self):
        dataset = er._load_dataset("routing_dataset.json")
        self.assertGreaterEqual(len(dataset["cases"]), 10)
        valid_routes = set(dataset["_routes"])
        for case in dataset["cases"]:
            self.assertIn("requirement", case)
            self.assertIn(case["expected_route"], valid_routes)

    def test_routing_dataset_includes_zero_tolerance_security_cases(self):
        dataset = er._load_dataset("routing_dataset.json")
        security_cases = [c for c in dataset["cases"] if c["expected_route"] == "REJECT_UNAUTHORIZED"]
        self.assertGreaterEqual(len(security_cases), 5)


class RunRetrievalEvalIntegrationTestCase(unittest.TestCase):
    """Runs against the REAL curated index — requires it to have been
    built (python agent/backend_rag_index.py). Skips gracefully rather
    than failing the whole suite if it hasn't."""

    def test_retrieval_eval_meets_recorded_baseline_thresholds(self):
        try:
            result = er.run_retrieval_eval()
        except RuntimeError as exc:
            self.skipTest(f"backend RAG index not built: {exc}")
        self.assertGreaterEqual(result["summary"]["recall_at_3"], er.THRESHOLDS["recall_at_3"])
        self.assertGreaterEqual(result["summary"]["mrr"], er.THRESHOLDS["mrr"])

    def test_routing_eval_meets_recorded_baseline_thresholds(self):
        result = er.run_routing_eval()
        self.assertGreaterEqual(result["summary"]["routing_accuracy"], er.THRESHOLDS["routing_accuracy"])
        self.assertEqual(result["summary"]["security_case_accuracy"], er.THRESHOLDS["security_case_accuracy"])


if __name__ == "__main__":
    unittest.main()
