"""
BL-105 (Sprint 27): Ask the Codebase shows its own retrieval quality in
plain English, read live from the same published eval-results.json the
/eval page uses -- never a hardcoded or separately-maintained number.
"""

import json
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"


class AskCodebaseQualityWiringTestCase(unittest.TestCase):
    def setUp(self):
        self.html = (WEB / "ask-codebase.html").read_text(encoding="utf-8")
        self.js = (WEB / "ask-codebase.js").read_text(encoding="utf-8")

    def test_page_has_a_quality_panel(self):
        self.assertIn('id="ac-quality"', self.html)

    def test_script_fetches_the_real_published_eval_results_file(self):
        # Must read the SAME file /eval reads -- not a second, divergent copy.
        self.assertIn('"/eval-results.json"', self.js)

    def test_script_does_not_hardcode_a_retrieval_score(self):
        # A literal like "83%" or "0.868" baked into the JS would silently
        # go stale the next time eval_runner.py re-measures. The only
        # numeric work allowed here is formatting (Math.round, toFixed,
        # pct()), never a bare score/threshold constant.
        suspicious = re.findall(r"0\.\d{2,3}", self.js)
        self.assertEqual(
            suspicious, [],
            f"found what looks like a hardcoded score literal in ask-codebase.js: {suspicious}",
        )

    def test_script_reads_the_real_schema_keys_present_in_published_results(self):
        results_path = WEB / "eval-results.json"
        if not results_path.exists():
            self.skipTest("eval-results.json not published in this checkout")
        data = json.loads(results_path.read_text(encoding="utf-8"))
        metric_keys = {m["key"] for m in data.get("metrics", [])}
        self.assertIn("recall_at_3", metric_keys)
        self.assertIn("mrr", metric_keys)
        self.assertIn("recall_at_5", data.get("informational", {}))
        # The JS must reference the exact same keys, not a renamed guess.
        self.assertIn("recall_at_3", self.js)
        self.assertIn("mrr", self.js)
        self.assertIn("recall_at_5", self.js)

    def test_quality_copy_explains_recall_and_mrr_without_assuming_jargon(self):
        # Plain-English requirement: the reader should not need to already
        # know what "recall" or "MRR" means to understand the sentence.
        self.assertIn("appears somewhere in the top 3 results", self.js)
        self.assertIn("mean reciprocal rank", self.js)

    def test_quality_panel_links_to_the_full_eval_breakdown(self):
        self.assertIn('href="/eval"', self.js)


if __name__ == "__main__":
    unittest.main()
