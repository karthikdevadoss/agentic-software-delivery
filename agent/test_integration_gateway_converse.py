"""Integration (PR52 converse + PR53 budgets + PR55 tracing): converse() and the
callers built on it (agent_loop, backend_planning) are budget-gated BEFORE being
billed and emit the same `gateway.model_call` span family as call().

Hermetic: temp SQLite budget file, injected create_fn or a patched SDK client
class standing in for the real client (so the budget path for REAL client calls
is exercised with zero network). No billed API call is ever made.

Run: python agent/test_integration_gateway_converse.py
"""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_loop
import backend_planning
import gateway_budget
import reasoning_gateway as rg
import tracing

PURPOSE = "HUMAN_EXPLANATION"


def _resp(text="ok", out=300):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)],
        usage=types.SimpleNamespace(input_tokens=0, output_tokens=out,
                                    cache_creation_input_tokens=None, cache_read_input_tokens=None),
        stop_reason="end_turn")


class _Base(unittest.TestCase):
    ENV = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = {"BUDGET_DB_PATH": os.path.join(self.tmp.name, "b.sqlite3"),
               "GATEWAY_RATE_LIMIT_CALLS": "1000"}
        env.update(self.ENV)
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("LITELLM_PROXY_URL", None)
        os.environ.pop("OTEL_SDK_DISABLED", None)

    def converse(self, fn=None, **kw):
        fn = fn or mock.Mock(return_value=_resp())
        kw.setdefault("max_tokens", 100)
        r = rg.converse(PURPOSE, "sys", [{"role": "user", "content": "hello"}],
                        create_fn=fn, enforce_budget=True, **kw)
        return r, fn


class ConverseBudgetTestCase(_Base):
    ENV = {"GATEWAY_DAILY_USD_CAP": "0.01"}

    def test_daily_cap_refuses_converse_before_the_provider_is_called(self):
        results = [self.converse(max_tokens=300) for _ in range(4)]   # 300 out tokens = $0.003 each
        self.assertEqual([r["model_called"] for r, _ in results], [True, True, True, False])
        refused, fn = results[3]
        self.assertTrue(refused["denial_reason"].startswith("BUDGET_DAILY_CAP_REACHED"))
        self.assertIsNone(refused["response"])
        fn.assert_not_called()

    def test_converse_and_call_share_one_daily_budget(self):
        for _ in range(3):
            rg.call(PURPOSE, "s", "u", 300, create_fn=mock.Mock(return_value=_resp()), enforce_budget=True)
        r, fn = self.converse(max_tokens=300)
        self.assertFalse(r["model_called"])
        fn.assert_not_called()

    def test_conversation_length_counts_toward_the_estimate(self):
        with mock.patch.dict(os.environ, {"GATEWAY_PER_REQUEST_USD_CAP": "0.01"}):
            big = [{"role": "user", "content": "x" * 30000}]      # ~10k input tokens ~ $0.03
            fn = mock.Mock(return_value=_resp())
            r = rg.converse(PURPOSE, "sys", big, 10, create_fn=fn, enforce_budget=True)
        self.assertIn("BUDGET_REQUEST_CAP_REACHED", r["denial_reason"])
        fn.assert_not_called()

    def test_injected_double_is_not_metered_by_default(self):
        rg.converse(PURPOSE, "s", [{"role": "user", "content": "u"}], 100,
                    create_fn=mock.Mock(return_value=_resp()))
        self.assertEqual(gateway_budget.status()["calls_today"], 0)

    def test_rate_limit_applies_to_converse(self):
        with mock.patch.dict(os.environ, {"GATEWAY_RATE_LIMIT_CALLS": "2"}):
            out = [self.converse()[0]["model_called"] for _ in range(3)]
        self.assertEqual(out, [True, True, False])


class ConverseSettlementTestCase(_Base):
    ENV = {"GATEWAY_DAILY_USD_CAP": "5"}

    def test_converse_settles_to_measured_cost(self):
        self.converse(max_tokens=1000)
        self.assertAlmostEqual(gateway_budget.status()["spent_or_reserved_usd"], 0.003, places=6)

    def test_a_failed_converse_keeps_its_reservation(self):
        boom = mock.Mock(side_effect=RuntimeError("provider failed"))
        with self.assertRaises(RuntimeError):
            self.converse(fn=boom, max_tokens=1000)
        self.assertGreater(gateway_budget.status()["spent_or_reserved_usd"], 0.009)


class _FakeAnthropic:
    """Stands in for the SDK class so the REAL-client path (which is the one
    that meters by default) runs with no network."""
    calls = 0

    def __init__(self, **kw):
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kw):
        type(self).calls += 1
        return _resp('{"affected_components": [], "expected_files": []}')


class CallersAreMeteredTestCase(_Base):
    """agent_loop and backend_planning pass no create_fn in production, so the
    gateway meters them by default. Prove that, and that a refusal reaches the
    caller as an honest message with zero provider calls."""
    ENV = {"GATEWAY_DAILY_USD_CAP": "0"}      # 0 refuses everything

    def setUp(self):
        super().setUp()
        _FakeAnthropic.calls = 0
        p = mock.patch("anthropic.Anthropic", _FakeAnthropic)
        p.start(); self.addCleanup(p.stop)
        m = mock.patch("metrics.record_model_usage")
        m.start(); self.addCleanup(m.stop)

    def test_agent_loop_over_budget_is_refused_before_billing(self):
        out = agent_loop.run_agent_loop("ticket", api_key="test-key-not-real")
        self.assertIn("model call not made", out)
        self.assertIn("BUDGET_DAILY_CAP_REACHED", out)
        self.assertEqual(_FakeAnthropic.calls, 0)

    def test_backend_planning_over_budget_is_refused_before_billing(self):
        ctx = types.SimpleNamespace(status="USED", context_text="ctx")
        out = backend_planning.analyze_with_llm("req", ctx, api_key="test-key-not-real")
        self.assertFalse(out["model_called"])
        self.assertIn("BUDGET_DAILY_CAP_REACHED", out["explanation"])
        self.assertEqual(_FakeAnthropic.calls, 0)

    def test_under_budget_the_same_callers_reach_the_provider_and_are_recorded(self):
        with mock.patch.dict(os.environ, {"GATEWAY_DAILY_USD_CAP": "5"}):
            ctx = types.SimpleNamespace(status="USED", context_text="ctx")
            out = backend_planning.analyze_with_llm("req", ctx, api_key="test-key-not-real")
            self.assertTrue(out["model_called"])
            self.assertEqual(_FakeAnthropic.calls, 1)
            self.assertEqual(gateway_budget.status()["calls_today"], 1)


class ConverseSpanTestCase(_Base):
    def setUp(self):
        super().setUp()
        tracing.reset_for_tests()
        self.rid = "run-converse-span"
        tracing.bind_run_id(self.rid)
        self.addCleanup(tracing.bind_run_id, None)

    def spans(self):
        return [s for s in tracing.spans_for_run(self.rid) if s["name"] == "gateway.model_call"]

    def test_ok_converse_has_model_tokens_cost_outcome(self):
        rg.converse(PURPOSE, "s", [{"role": "user", "content": "u"}], 100,
                    create_fn=lambda **kw: _resp(out=7), model="claude-sonnet-5")
        (sp,) = self.spans()
        a = sp["attributes"]
        self.assertEqual(a["entry"], "converse")
        self.assertEqual(a["model"], "claude-sonnet-5")
        self.assertEqual(a["gateway.outcome"], "ok")
        self.assertEqual(a["llm.output_tokens"], 7)
        self.assertIn("llm.input_tokens", a)
        self.assertIn("llm.cost_usd", a)       # sonnet-5 has a verified price in pricing_config

    def test_denied_converse_is_a_denied_span(self):
        rg.converse("NOT_A_PURPOSE", "s", [{"role": "user", "content": "u"}], 100,
                    create_fn=lambda **kw: _resp())
        (sp,) = self.spans()
        self.assertEqual(sp["attributes"]["gateway.outcome"], "denied")

    def test_budget_refusal_is_visible_in_the_trace(self):
        with mock.patch.dict(os.environ, {"GATEWAY_DAILY_USD_CAP": "0"}):
            fn = mock.Mock(return_value=_resp())
            rg.converse(PURPOSE, "s", [{"role": "user", "content": "u"}], 100,
                        create_fn=fn, enforce_budget=True)
        (sp,) = self.spans()
        self.assertEqual(sp["attributes"]["gateway.outcome"], "denied")
        self.assertIn("BUDGET_DAILY_CAP_REACHED", sp["attributes"]["gateway.denial_reason"])
        fn.assert_not_called()

    def test_provider_exception_is_an_error_span_and_reraised(self):
        with self.assertRaises(RuntimeError):
            rg.converse(PURPOSE, "s", [{"role": "user", "content": "u"}], 100,
                        create_fn=mock.Mock(side_effect=RuntimeError("x")))
        (sp,) = self.spans()
        self.assertEqual(sp["attributes"]["gateway.outcome"], "error")
        self.assertEqual(sp["attributes"]["error.type"], "RuntimeError")

    def test_call_and_converse_are_the_same_span_family(self):
        rg.call(PURPOSE, "s", "u", 100, create_fn=lambda **kw: _resp())
        rg.converse(PURPOSE, "s", [{"role": "user", "content": "u"}], 100, create_fn=lambda **kw: _resp())
        self.assertEqual([s["attributes"]["entry"] for s in self.spans()], ["call", "converse"])


if __name__ == "__main__":
    unittest.main()
