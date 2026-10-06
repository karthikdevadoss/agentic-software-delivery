"""
Tests for agent/publish_ask_codebase_examples.py and a staleness guard for
the committed agent/web/ask-codebase-examples.json. Hermetic: no index, no
model, no network.

Run: python agent/test_publish_ask_codebase_examples.py
"""

import json
import unittest

import publish_ask_codebase_examples as pa

REGENERATE = "regenerate: cd agent && python backend_rag_index.py && python publish_ask_codebase_examples.py"


def _answer(q, status="STRONG_EVIDENCE", n=5):
    return {"query": q, "status": status, "message": "m", "evidence": [
        {"rank": i + 1, "score": 0.8 - i / 100, "source_path": f"docs/f{i}.md", "symbol": "s",
         "start_line": 1, "end_line": 9, "source_url": "u", "excerpt": "x" * 1000}
        for i in range(n)]}


class PublisherTestCase(unittest.TestCase):
    def test_extracts_examples_from_page_buttons(self):
        html = ('<button type="button" class="ac-example-btn">Where is\n  X?</button>'
                '<button class="other">no</button><button type="button" class="ac-example-btn">Isn&#x27;t Y?</button>')
        self.assertEqual(pa.extract_examples(html), ["Where is X?", "Isn't Y?"])

    def test_trim_keeps_top_three_and_shortens_excerpts(self):
        t = pa.trim_answer(_answer("q"))
        self.assertEqual(len(t["evidence"]), 3)
        self.assertEqual(t["evidence_returned"], 5)
        self.assertLessEqual(len(t["evidence"][0]["excerpt"]), pa.EXCERPT_CHARS + 1)
        self.assertEqual(t["status"], "STRONG_EVIDENCE")

    def test_snapshot_summary_counts_feature_statuses(self):
        snap = pa.build_snapshot(["a", "b"], [_answer("a"), _answer("b", "WEAK_EVIDENCE")],
                                 commit_sha="c" * 40, generated_at="t", embedding_model="m",
                                 working_tree_dirty=False, inputs={"files": {}, "examples": "h"},
                                 min_strong_score=0.45)
        self.assertEqual(snap["summary"], {"STRONG_EVIDENCE": 1, "WEAK_EVIDENCE": 1})
        self.assertEqual(snap["llm_calls"], 0)
        self.assertTrue(snap["inputs"]["not_covered"])


class AskCodebaseExamplesFreshTestCase(unittest.TestCase):
    def setUp(self):
        self.published = json.loads(pa.OUTPUT_PATH.read_text(encoding="utf-8"))
        self.examples = pa.extract_examples(pa.PAGE.read_text(encoding="utf-8"))

    def test_snapshot_covers_exactly_the_page_examples(self):
        self.assertEqual([e["query"] for e in self.published["examples"]], self.examples,
                         f"page examples changed; {REGENERATE}")

    def test_inputs_unchanged_since_publish(self):
        current = pa.compute_input_hashes(self.examples)
        recorded = self.published["inputs"]
        self.assertEqual(recorded["files"], current["files"], f"feature/corpus list changed; {REGENERATE}")
        self.assertEqual(recorded["examples"], current["examples"], f"examples changed; {REGENERATE}")

    def test_page_is_routed_and_linked(self):
        import web_server
        routes = {r.path: r for r in web_server.routes if hasattr(r, "path")}
        self.assertIs(routes["/ask-codebase/examples"].endpoint, web_server.ask_codebase_examples_page)
        self.assertIn('href="/ask-codebase/examples"', pa.PAGE.read_text(encoding="utf-8"))
        js = (pa.AGENT_DIR / "web" / "ask-codebase-examples.js").read_text(encoding="utf-8")
        self.assertIn("/ask-codebase-examples.json", js)


if __name__ == "__main__":
    unittest.main()
