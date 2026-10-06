"""
Staleness guard for agent/web/eval-results.json (retro action 2026-10-06,
item 3). The public /eval page shows numbers measured against specific eval
inputs; if the labelled datasets, agent/eval_runner.py or its THRESHOLDS
change, the published numbers no longer describe the repo. This test fails
until the JSON is regenerated:

    cd agent && python backend_rag_index.py && python publish_eval_results.py

Hermetic: hashes files on disk, no index, no model, no network. What it does
NOT cover is listed in the JSON's eval_inputs.not_covered.

Run: python agent/test_eval_results_fresh.py
"""

import json
import unittest

import publish_eval_results as pub

REGENERATE = "regenerate it: cd agent && python backend_rag_index.py && python publish_eval_results.py"


class EvalResultsFreshTestCase(unittest.TestCase):
    def setUp(self):
        self.published = json.loads(pub.OUTPUT_PATH.read_text(encoding="utf-8"))
        self.recorded = self.published.get("eval_inputs")
        self.current = pub.compute_eval_input_hashes()

    def test_results_file_records_eval_input_hashes(self):
        self.assertIsNotNone(self.recorded, f"eval-results.json has no eval_inputs; {REGENERATE}")
        self.assertEqual(sorted(self.recorded["files"]), sorted(pub.EVAL_INPUT_FILES))

    def test_labelled_sets_and_eval_code_unchanged_since_publish(self):
        stale = [rel for rel, h in self.current["files"].items()
                 if self.recorded["files"].get(rel) != h]
        self.assertEqual(stale, [], f"eval inputs changed since eval-results.json was published "
                                    f"(at {self.published['commit_sha'][:7]}): {stale}; {REGENERATE}")

    def test_thresholds_unchanged_since_publish(self):
        self.assertEqual(self.recorded["thresholds"], self.current["thresholds"],
                         f"eval_runner.THRESHOLDS changed since publish; {REGENERATE}")
        for m in self.published["metrics"]:
            self.assertEqual(m["threshold"], pub.eval_runner.THRESHOLDS[m["key"]])


if __name__ == "__main__":
    unittest.main()
