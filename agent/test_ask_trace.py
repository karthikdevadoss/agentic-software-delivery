"""Hermetic: Ask the Codebase produces a per-request OpenTelemetry trace with
the real steps as child spans, start offsets for a waterfall, and never the
raw question text. No index, no model: candidates and embedder are fakes."""
import os
import unittest
from unittest import mock

import ask_codebase
import permission_retrieval
import tracing

QUESTION = "where is the secret approval token checked"

FAKE_CANDS = [{"chunk_id": f"c{i}", "vector": [1.0, float(i), 0.5], "source_path": f"a{i}.py",
               "source_type": "code", "symbol": None, "start_line": 1, "end_line": 2,
               "content": "x", "source": "github-public", "access_level": "public"} for i in range(6)]


class AskTraceTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"OTEL_SDK_DISABLED": "false"})
        env.start()
        self.addCleanup(env.stop)
        tracing.reset_for_tests()
        self.addCleanup(tracing.reset_for_tests)
        for target, value in ((permission_retrieval, "_candidates"), (permission_retrieval, "embed_query")):
            fake = (lambda levels: FAKE_CANDS) if value == "_candidates" else (lambda q: [1.0, 1.0, 0.5])
            p = mock.patch.object(target, value, fake)
            p.start()
            self.addCleanup(p.stop)

    def _run(self, run_id):
        token = tracing.bind_run_id(run_id)
        try:
            result = ask_codebase.ask(QUESTION)
        finally:
            tracing.unbind_run_id(token)
        return result, tracing.spans_for_run(run_id)

    def test_four_steps_nested_under_the_request(self):
        result, spans = self._run("t-nest")
        names = {s["name"]: s for s in spans}
        self.assertEqual(set(names), {"ask_codebase.request", "permission.filter", "embedding.query", "retrieval.rank"})
        root = names["ask_codebase.request"]
        self.assertIsNone(root["parent_span_id"])
        for child in ("permission.filter", "embedding.query", "retrieval.rank"):
            self.assertEqual(names[child]["parent_span_id"], root["span_id"])
            self.assertEqual(names[child]["trace_id"], root["trace_id"])
        self.assertEqual(root["attributes"]["ask.status"], result["status"])
        self.assertEqual(names["retrieval.rank"]["attributes"]["retrieval.hit_count"], 5)

    def test_offsets_make_a_valid_waterfall(self):
        _, spans = self._run("t-offsets")
        by = {s["name"]: s for s in spans}
        self.assertEqual(by["ask_codebase.request"]["start_offset_ms"], 0.0)
        self.assertLessEqual(by["permission.filter"]["start_offset_ms"], by["embedding.query"]["start_offset_ms"])
        self.assertLessEqual(by["embedding.query"]["start_offset_ms"], by["retrieval.rank"]["start_offset_ms"])
        for s in spans:
            self.assertGreaterEqual(s["duration_ms"], 0)

    def test_question_text_is_never_recorded(self):
        _, spans = self._run("t-privacy")
        blob = repr([s["attributes"] for s in spans]).lower()
        for word in ("secret", "approval", "token", QUESTION.lower()):
            self.assertNotIn(word, blob)
        root = [s for s in spans if s["name"] == "ask_codebase.request"][0]
        self.assertEqual(root["attributes"]["query.length"], len(QUESTION))

    def test_runs_are_isolated(self):
        self._run("t-a")
        self._run("t-b")
        self.assertEqual(len(tracing.spans_for_run("t-a")), 4)
        self.assertEqual(len(tracing.spans_for_run("t-b")), 4)


if __name__ == "__main__":
    unittest.main()
