"""Hermetic tests: spans exist for gateway call, retrieval, approval. No network."""
import os
import types
import unittest
from unittest import mock

import tracing


def _fake_create(**kw):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text="hello")],
        usage=types.SimpleNamespace(input_tokens=11, output_tokens=7,
                                    cache_creation_input_tokens=None, cache_read_input_tokens=None),
        stop_reason="end_turn")


def _by_name(run_id, name):
    return [s for s in tracing.spans_for_run(run_id) if s["name"] == name]


class TracingTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("OTEL_SDK_DISABLED", None)
        tracing.reset_for_tests()
        self.tok = tracing.bind_run_id("run-test-1")

    def tearDown(self):
        tracing.bind_run_id(None)

    def test_gateway_ok_and_denied_spans(self):
        import reasoning_gateway
        r = reasoning_gateway.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=_fake_create)
        self.assertEqual(r["text"], "hello")
        reasoning_gateway.call("NOT_A_PURPOSE", "s", "u", 100, create_fn=_fake_create)
        with mock.patch.dict(os.environ, {"LLM_MODE": "DISABLED"}):
            reasoning_gateway.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=_fake_create)
        spans = _by_name("run-test-1", "gateway.model_call")
        self.assertEqual([s["attributes"]["gateway.outcome"] for s in spans], ["ok", "denied", "denied"])
        ok = spans[0]["attributes"]
        self.assertEqual(ok["purpose"], "HUMAN_EXPLANATION")
        self.assertEqual((ok["llm.input_tokens"], ok["llm.output_tokens"]), (11, 7))
        self.assertNotIn("denial", " ".join(k for k in ok if k == "gateway.denial_reason"))

    def test_retrieval_span_hides_query(self):
        import backend_rag_index as rag
        secret = "my secret password question"
        with mock.patch.object(rag, "_semantic_search_impl", return_value=[{"a": 1}, {"a": 2}]):
            rag.semantic_search(secret, top_k=4)
        (sp,) = _by_name("run-test-1", "retrieval.semantic_search")
        a = sp["attributes"]
        self.assertEqual((a["top_k"], a["retrieval.hit_count"], a["query.length"]), (4, 2, len(secret)))
        self.assertNotIn("secret", repr(a))

    def test_approval_span_and_shared_trace(self):
        import execution_tools
        edit = types.SimpleNamespace(id="e1", path="x.txt", new_content="body")
        with tracing.span("parent"):
            self.assertFalse(execution_tools.traced_approval(lambda e: False, edit))
            self.assertTrue(execution_tools.traced_approval(lambda e: True, edit))
        sp = _by_name("run-test-1", "approval.gate")
        self.assertEqual([s["attributes"]["approval.decision"] for s in sp], ["rejected", "approved"])
        self.assertEqual(len(sp[0]["attributes"]["binding_hash"]), 64)
        parent = _by_name("run-test-1", "parent")[0]
        self.assertEqual(sp[0]["trace_id"], parent["trace_id"])

    def test_disabled_is_noop(self):
        tracing.reset_for_tests()
        with mock.patch.dict(os.environ, {"OTEL_SDK_DISABLED": "true"}):
            import reasoning_gateway
            r = reasoning_gateway.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=_fake_create)
        self.assertEqual(r["text"], "hello")
        self.assertEqual(tracing.spans_for_run("run-test-1"), [])


if __name__ == "__main__":
    unittest.main()
