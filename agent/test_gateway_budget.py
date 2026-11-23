"""Durable budgets, rate limits and LiteLLM routing in reasoning_gateway.

Hermetic: temp SQLite file, injected create_fn, and a loopback HTTP server
standing in for the LiteLLM proxy. No billed call is ever made. The restart
tests use a REAL second interpreter (subprocess) against the same file -- an
in-process "reset" would prove nothing about durability.

Run: python agent/test_gateway_budget.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import budget_store
import gateway_budget
import litellm_route
import reasoning_gateway as rg
import si_budget
import triage_budget


class _Usage:
    def __init__(self, i=0, o=300):
        self.input_tokens, self.output_tokens = i, o
        self.cache_creation_input_tokens = self.cache_read_input_tokens = None


class _Block:
    type = "text"
    def __init__(self, t): self.text = t


class _Resp:
    def __init__(self, text="ok", i=0, o=300):
        self.content, self.usage, self.stop_reason = [_Block(text)], _Usage(i, o), "end_turn"


class _Base(unittest.TestCase):
    ENV = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "b.sqlite3")
        env = {"BUDGET_DB_PATH": self.db}
        env.update(self.ENV)
        p = mock.patch.dict(os.environ, env)
        p.start()
        self.addCleanup(p.stop)
        os.environ.pop("LITELLM_PROXY_URL", None)

    def call(self, fn=None, **kw):
        fn = fn or mock.Mock(return_value=_Resp())
        kw.setdefault("max_tokens", 100)
        r = rg.call("HUMAN_EXPLANATION", "sys", "hello", create_fn=fn,
                    enforce_budget=True, **kw)
        return r, fn


class DailyCapTestCase(_Base):
    ENV = {"GATEWAY_DAILY_USD_CAP": "0.01", "GATEWAY_RATE_LIMIT_CALLS": "1000"}

    def test_cap_reached_refuses_before_the_provider_is_called(self):
        # each call measures 300 output tokens = $0.003 -> 3 fit under $0.01, the 4th must not
        results = [self.call(max_tokens=300) for _ in range(4)]
        self.assertEqual([r["model_called"] for r, _ in results], [True, True, True, False])
        refused, fn = results[3]
        self.assertTrue(refused["denial_reason"].startswith("BUDGET_DAILY_CAP_REACHED"))
        fn.assert_not_called()


class PerRunAndRequestCapTestCase(_Base):
    ENV = {"GATEWAY_PER_RUN_USD_CAP": "0.004", "GATEWAY_RATE_LIMIT_CALLS": "1000",
           "GATEWAY_PER_REQUEST_USD_CAP": "0.05"}

    def test_per_run_cap_is_per_run_id(self):
        self.assertTrue(self.call(run_id="r1", max_tokens=300)[0]["model_called"])
        r, fn = self.call(run_id="r1", max_tokens=300)
        self.assertFalse(r["model_called"])
        self.assertIn("BUDGET_RUN_CAP_REACHED", r["denial_reason"])
        fn.assert_not_called()
        self.assertTrue(self.call(run_id="r2", max_tokens=300)[0]["model_called"])

    def test_per_request_cap_refuses_an_oversized_call(self):
        r, fn = self.call(max_tokens=20000)       # worst case ~ $0.20 > $0.05
        self.assertIn("BUDGET_REQUEST_CAP_REACHED", r["denial_reason"])
        fn.assert_not_called()


class RateLimitTestCase(_Base):
    ENV = {"GATEWAY_RATE_LIMIT_CALLS": "3", "GATEWAY_RATE_WINDOW_SECONDS": "60"}

    def test_a_too_fast_burst_is_refused_then_allowed_after_the_window(self):
        out = [self.call()[0]["model_called"] for _ in range(5)]
        self.assertEqual(out, [True, True, True, False, False])
        later = budget_store.now() + 61
        with mock.patch.object(budget_store, "now", return_value=later):
            self.assertTrue(self.call()[0]["model_called"])

    def test_refusal_names_the_rate_limit(self):
        for _ in range(3):
            self.call()
        r, _ = self.call()
        self.assertIn("BUDGET_RATE_LIMITED", r["denial_reason"])


class SettlementTestCase(_Base):
    ENV = {"GATEWAY_RATE_LIMIT_CALLS": "1000"}

    def test_success_settles_the_estimate_to_the_measured_cost(self):
        self.call(max_tokens=1000)
        st = gateway_budget.status()
        # measured: 300 out * $10/MTok = $0.003, not the ~$0.01 worst-case reservation
        self.assertAlmostEqual(st["spent_or_reserved_usd"], 0.003, places=6)

    def test_a_failed_call_keeps_its_reservation(self):
        boom = mock.Mock(side_effect=RuntimeError("provider failed mid-call"))
        with self.assertRaises(RuntimeError):
            self.call(fn=boom, max_tokens=1000)
        self.assertGreater(gateway_budget.status()["spent_or_reserved_usd"], 0.009)

    def test_injected_double_is_not_metered_by_default(self):
        rg.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=mock.Mock(return_value=_Resp()))
        self.assertEqual(gateway_budget.status()["calls_today"], 0)

    def test_malformed_env_never_lifts_a_cap(self):
        with mock.patch.dict(os.environ, {"GATEWAY_DAILY_USD_CAP": "lots", "GATEWAY_RATE_LIMIT_CALLS": "-3"}):
            lim = gateway_budget.limits()
        self.assertEqual(lim["daily_usd_cap"], gateway_budget.DEFAULT_DAILY_USD_CAP)
        self.assertEqual(lim["rate_limit_calls"], gateway_budget.DEFAULT_RATE_CALLS)


def _run_py(db, code, **env):
    e = dict(os.environ, BUDGET_DB_PATH=db, PYTHONPATH=str(HERE), **env)
    e.pop("LITELLM_PROXY_URL", None)
    return subprocess.run([sys.executable, "-c", code], env=e, capture_output=True,
                          text=True, timeout=60)


class RestartTestCase(_Base):
    """A real second interpreter sees the first one's spend."""
    ENV = {"GATEWAY_DAILY_USD_CAP": "0.01", "GATEWAY_RATE_LIMIT_CALLS": "1000"}

    # one call: worst case ~$0.000052 reserved, settles to the same measured cost
    SPEND = (
        "import reasoning_gateway as rg\n"
        "class U: input_tokens=1;output_tokens=5;cache_creation_input_tokens=None;cache_read_input_tokens=None\n"
        "class B: type='text'; text='x'\n"
        "class R: content=[B()]; usage=U(); stop_reason='end_turn'\n"
        "r = rg.call('HUMAN_EXPLANATION','s','u',5,create_fn=lambda **k: R(),enforce_budget=True)\n"
        "assert r['model_called'], r\n")

    def test_gateway_spend_and_cap_survive_a_process_restart(self):
        # process 1 spends until the estimate-settled total is just under the cap
        env = {"GATEWAY_DAILY_USD_CAP": "0.0001", "GATEWAY_PER_REQUEST_USD_CAP": "0.01"}
        first = _run_py(self.db, self.SPEND, **env)
        self.assertEqual(first.returncode, 0, first.stderr)
        # process 2 (fresh interpreter): recorded spend is still there ...
        probe = _run_py(self.db, "import gateway_budget as g, json; print(json.dumps(g.status()))", **env)
        self.assertEqual(probe.returncode, 0, probe.stderr)
        st = json.loads(probe.stdout)
        self.assertEqual(st["calls_today"], 1)
        self.assertGreater(st["spent_or_reserved_usd"], 0)
        # ... and the cap still holds: the next call is refused, provider untouched
        second = _run_py(self.db, (
            "import reasoning_gateway as rg\n"
            "def boom(**k): raise SystemExit('PROVIDER CALLED')\n"
            "r = rg.call('HUMAN_EXPLANATION','s','u',5,create_fn=boom,enforce_budget=True)\n"
            "print(r['model_called'], r['denial_reason'])"), **env)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertTrue(second.stdout.startswith("False BUDGET_DAILY_CAP_REACHED"), second.stdout)

    def test_in_process_module_state_is_not_what_holds_the_count(self):
        self.call()
        budget_store._initialised.clear()          # forget everything held in memory
        self.assertEqual(gateway_budget.status()["calls_today"], 1)

    def test_triage_counters_survive_a_restart(self):
        env = {"TRIAGE_DAILY_MAX_MODEL_CALLS": "2", "TRIAGE_PER_VISITOR_DAILY_MAX": "9"}
        r = _run_py(self.db, "import triage_budget as t\n"
                    "assert t.check_and_reserve('a')['allowed'] and t.check_and_reserve('b')['allowed']", **env)
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _run_py(self.db, "import triage_budget as t\n"
                    "v=t.check_and_reserve('c'); print(v['allowed'], v.get('status'))", **env)
        self.assertEqual(r.stdout.strip(), "False DAILY_CAP_REACHED", r.stdout + r.stderr)

    def test_si_counters_survive_a_restart(self):
        r = _run_py(self.db, "import si_budget as s\n"
                    "[s.record_answer(f'v{i}') for i in range(s.SI_DAILY_MAX_ANSWERS)]")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = _run_py(self.db, "import si_budget as s; print(s.check('new')['status'])")
        self.assertEqual(r.stdout.strip(), "DAILY_CAP", r.stdout + r.stderr)


class _FakeProxy(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        _FakeProxy.seen.append({"path": self.path,
                                "auth": self.headers.get("authorization") or self.headers.get("x-api-key"),
                                "body": json.loads(body)})
        payload = json.dumps({
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5",
            "content": [{"type": "text", "text": "answer via proxy"}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 5, "output_tokens": 7}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


class LiteLLMRoutingTestCase(_Base):
    def setUp(self):
        super().setUp()
        _FakeProxy.seen = []
        self.server = HTTPServer(("127.0.0.1", 0), _FakeProxy)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _real_call(self):
        return rg.call("HUMAN_EXPLANATION", "sys", "hello", 100)

    def test_enabled_sends_the_request_to_the_proxy_not_anthropic(self):
        env = {"LITELLM_PROXY_URL": self.url, "LITELLM_API_KEY": "sk-proxy-test",
               "ANTHROPIC_API_KEY": "sk-ant-must-not-be-sent"}
        with mock.patch.dict(os.environ, env), \
                mock.patch("metrics.record_model_usage"):
            r = self._real_call()
        self.assertEqual(r["text"], "answer via proxy")
        self.assertEqual(len(_FakeProxy.seen), 1)
        seen = _FakeProxy.seen[0]
        self.assertEqual(seen["path"], "/v1/messages")
        # Anthropic SDK 2.12 sends the key as a Bearer token when base_url is
        # overridden; LiteLLM accepts Bearer and x-api-key alike.
        self.assertIn("sk-proxy-test", seen["auth"])
        self.assertNotIn("sk-ant", seen["auth"])         # the proxy key, never the Anthropic key
        self.assertEqual(seen["body"]["model"], "claude-sonnet-5")

    def test_enabled_without_a_proxy_key_refuses_and_does_not_fall_back_direct(self):
        env = {"LITELLM_PROXY_URL": self.url, "ANTHROPIC_API_KEY": "sk-ant-real-looking"}
        with mock.patch.dict(os.environ, env), mock.patch("anthropic.Anthropic") as ctor:
            os.environ.pop("LITELLM_API_KEY", None)
            r = self._real_call()
        self.assertFalse(r["model_called"])
        self.assertIn("LITELLM_API_KEY", r["denial_reason"])
        ctor.assert_not_called()

    def test_a_non_http_proxy_url_is_refused(self):
        with mock.patch.dict(os.environ, {"LITELLM_PROXY_URL": "ftp://x", "LITELLM_API_KEY": "k"}):
            r = self._real_call()
        self.assertFalse(r["model_called"])
        self.assertIn("not an http(s) URL", r["denial_reason"])

    def test_disabled_keeps_the_direct_anthropic_path(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-x"}), \
                mock.patch("anthropic.Anthropic") as ctor:
            ctor.return_value.messages.create.return_value = _Resp("direct")
            with mock.patch("metrics.record_model_usage"):
                r = self._real_call()
        ctor.assert_called_once_with(api_key="sk-ant-x")      # no base_url override
        self.assertEqual(r["text"], "direct")
        self.assertEqual(_FakeProxy.seen, [])

    def test_the_budget_gate_runs_before_the_proxy_is_contacted(self):
        env = {"LITELLM_PROXY_URL": self.url, "LITELLM_API_KEY": "k", "GATEWAY_DAILY_USD_CAP": "0"}
        with mock.patch.dict(os.environ, env):
            r = self._real_call()
        self.assertIn("BUDGET_DAILY_CAP_REACHED", r["denial_reason"])
        self.assertEqual(_FakeProxy.seen, [])


class LiteLLMConfigFilesTestCase(unittest.TestCase):
    DIR = HERE.parent / "infra" / "litellm"

    def _cfg(self):
        import yaml
        return yaml.safe_load((self.DIR / "config.yaml").read_text())

    def test_config_routes_the_real_model_to_anthropic_via_env_key(self):
        models = {m["model_name"]: m["litellm_params"] for m in self._cfg()["model_list"]}
        self.assertEqual(models["claude-sonnet-5"]["model"], "anthropic/claude-sonnet-5")
        self.assertEqual(models["claude-sonnet-5"]["api_key"], "os.environ/ANTHROPIC_API_KEY")

    def test_the_second_provider_is_a_stub_with_no_real_key(self):
        stub = {m["model_name"]: m["litellm_params"] for m in self._cfg()["model_list"]}["stub-echo"]
        self.assertIn("mock_response", stub)
        self.assertNotIn("api_key", stub)

    def test_master_key_comes_from_the_environment_not_the_file(self):
        self.assertEqual(self._cfg()["general_settings"]["master_key"], "os.environ/LITELLM_MASTER_KEY")

    def test_compose_binds_loopback_only_and_has_no_secret_literals(self):
        text = (self.DIR / "docker-compose.yml").read_text()
        self.assertIn("127.0.0.1:4000:4000", text)
        self.assertNotIn("sk-ant", text)


class BudgetEndpointTestCase(_Base):
    def test_budget_endpoint_reports_remaining_for_all_three_scopes(self):
        from starlette.testclient import TestClient
        import web_server
        self.call()
        body = TestClient(web_server.app).get("/api/budget").json()
        self.assertEqual(body["gateway"]["calls_today"], 1)
        self.assertIn("remaining_usd", body["gateway"])
        self.assertIn("calls_remaining", body["triage"])
        self.assertIn("answers_remaining", body["standing_interview"])
        self.assertIn("proxy_mode", body)


if __name__ == "__main__":
    unittest.main()
