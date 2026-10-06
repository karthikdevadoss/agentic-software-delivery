"""Automation Sprint 4 / S2: owner-only control plane and a capped Triage Lab.

Hermetic: TestClient against the real app; model calls, threads and the
dev-session store are replaced with recorders so a refused request can be
shown to do NO work. No network, no model, no database.
"""
import inspect
import os
import re
import unittest
from unittest import mock

from starlette.testclient import TestClient

import owner_auth
import triage_budget
import triage_execution
import web_server as ws

TOKEN = "test-owner-token-0123456789"
OWNER_POSTS = ["/api/runs", "/api/runs/mock", "/api/runs/{run_id}/decide",
               "/api/dev-sessions/start", "/api/dev-sessions/stop"]


def _env(**values):
    return mock.patch.dict(os.environ, values, clear=False)


class OwnerTokenUnitTestCase(unittest.TestCase):
    def test_fails_closed_when_the_token_is_not_configured(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OWNER_API_TOKEN", None)
            self.assertFalse(owner_auth.is_configured())
            self.assertFalse(owner_auth.is_owner({"authorization": "Bearer "}))
            self.assertFalse(owner_auth.is_owner({"x-owner-token": ""}))
            self.assertFalse(owner_auth.is_owner({"x-owner-token": "anything"}))

    def test_blank_configured_token_is_treated_as_unset(self):
        with _env(OWNER_API_TOKEN="   "):
            self.assertFalse(owner_auth.is_owner({"x-owner-token": "   "}))

    def test_accepts_bearer_or_header_and_rejects_anything_else(self):
        with _env(OWNER_API_TOKEN=TOKEN):
            self.assertTrue(owner_auth.is_owner({"authorization": f"Bearer {TOKEN}"}))
            self.assertTrue(owner_auth.is_owner({"x-owner-token": TOKEN}))
            for bad in ({}, {"x-owner-token": TOKEN[:-1]}, {"authorization": TOKEN},
                        {"authorization": f"Basic {TOKEN}"}, {"x-owner-token": TOKEN + "x"}):
                with self.subTest(headers=bad):
                    self.assertFalse(owner_auth.is_owner(bad))


class OwnerOnlyRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)
        self.started_threads = []
        # Replace web_server's reference to the threading module only: the
        # TestClient itself needs real threads.
        fake_threading = mock.Mock()
        fake_threading.Thread.side_effect = lambda *a, **k: self.started_threads.append(k) or mock.Mock()
        p = mock.patch.object(ws, "threading", fake_threading)
        p.start(); self.addCleanup(p.stop)
        self.dev_calls = []
        for name in ("start_dev_session", "stop_dev_session"):
            p = mock.patch.object(ws.sessions_data, name,
                                  side_effect=lambda *a, _n=name, **k: self.dev_calls.append(_n) or {"id": "dev-x"})
            p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(ws, "_reserve_run_slot", return_value=True)
        p.start(); self.addCleanup(p.stop)

    def _posts(self, headers):
        bodies = {"/api/runs": {"requirement": "x"}, "/api/dev-sessions/start": {"goal": "g"},
                  "/api/dev-sessions/stop": {"session_id": "dev-x"}}
        out = {}
        for path in OWNER_POSTS:
            url = path.replace("{run_id}", "nope")
            out[path] = self.client.post(url, json=bodies.get(path, {"edit_id": "e", "decision": "approve"}),
                                         headers=headers)
        return out

    def test_every_route_on_the_list_is_registered_as_owner_only(self):
        routes = {(r.path, tuple(sorted(r.methods or ()))): r for r in ws.app.routes if hasattr(r, "methods")}
        for path in OWNER_POSTS:
            with self.subTest(path=path):
                match = [r for (p, m), r in routes.items() if p == path and "POST" in m]
                self.assertEqual(len(match), 1)
                self.assertTrue(getattr(match[0].endpoint, "owner_only", False))

    def test_anonymous_wrong_token_and_unconfigured_server_all_get_401_and_do_no_work(self):
        cases = [("no token configured", {}, None), ("anonymous", {}, TOKEN),
                 ("wrong token", {"x-owner-token": "guess"}, TOKEN),
                 ("token sent but server unconfigured", {"x-owner-token": TOKEN}, None)]
        for label, headers, configured in cases:
            with self.subTest(case=label):
                env = {"OWNER_API_TOKEN": configured} if configured else {}
                with mock.patch.dict(os.environ, env, clear=False):
                    if not configured:
                        os.environ.pop("OWNER_API_TOKEN", None)
                    for path, resp in self._posts(headers).items():
                        self.assertEqual(resp.status_code, 401, f"{path}: {resp.text}")
                        self.assertIn("Bearer", resp.headers.get("www-authenticate", ""))
        self.assertEqual(self.started_threads, [], "a refused request started a run")
        self.assertEqual(self.dev_calls, [], "a refused request wrote a dev session")

    def test_owner_token_reaches_the_handlers(self):
        with _env(OWNER_API_TOKEN=TOKEN):
            out = self._posts({"authorization": f"Bearer {TOKEN}"})
        self.assertEqual(out["/api/runs"].status_code, 200, out["/api/runs"].text)
        self.assertEqual(out["/api/runs/mock"].status_code, 200)
        self.assertEqual(out["/api/runs/{run_id}/decide"].status_code, 404)   # past auth: no such run
        self.assertEqual(out["/api/dev-sessions/start"].status_code, 200)
        self.assertEqual(len(self.started_threads), 2)
        self.assertEqual(self.dev_calls, ["start_dev_session", "stop_dev_session"])
        for rid in list(ws.RUNS):
            if any(t.get("args") and t["args"][0] is ws.RUNS[rid] for t in self.started_threads):
                ws.RUNS.pop(rid, None)

    def test_control_plane_page_is_hidden_unless_owner_or_private_surfaces(self):
        with mock.patch.object(ws, "PRIVATE_SURFACES_ENABLED", False), _env(OWNER_API_TOKEN=TOKEN):
            self.assertEqual(self.client.get("/control-plane").status_code, 404)
            self.assertEqual(self.client.get("/control-plane", headers={"x-owner-token": "nope"}).status_code, 404)
            self.assertEqual(self.client.get("/control-plane", headers={"x-owner-token": TOKEN}).status_code, 200)
        with mock.patch.object(ws, "PRIVATE_SURFACES_ENABLED", True):
            self.assertEqual(self.client.get("/control-plane").status_code, 200)

    def test_read_only_run_views_used_by_the_workbench_stay_public(self):
        routes = {r.path: r for r in ws.app.routes if hasattr(r, "methods") and "GET" in (r.methods or ())}
        for path in ("/api/runs/{run_id}", "/api/runs/{run_id}/events", "/api/workbench/verified-run"):
            self.assertFalse(getattr(routes[path].endpoint, "owner_only", False), path)


MODEL_FNS = ["diagnose", "generate_candidate_patch", "diagnose_b", "generate_candidate_patch_b",
             "diagnose_c", "generate_candidate_patch_c"]


class TriageBudgetTestCase(unittest.TestCase):
    def setUp(self):
        triage_budget._reset_for_tests()
        self.addCleanup(triage_budget._reset_for_tests)
        self.client = TestClient(ws.app)
        self.model_calls = []
        p = mock.patch.object(triage_execution, "diagnose",
                              side_effect=lambda *a, **k: self.model_calls.append("diagnose") or {"ok": True})
        p.start(); self.addCleanup(p.stop)

    def _diagnose(self, ip, headers=None):
        h = {"x-forwarded-for": ip}
        h.update(headers or {})
        return self.client.post("/api/triage/scenario-a/diagnose", json={"reproduction_result": {}}, headers=h)

    def test_every_handler_that_calls_the_model_is_budgeted(self):
        found = []
        for name, fn in inspect.getmembers(ws, inspect.isfunction):
            src = inspect.getsource(inspect.unwrap(fn))
            if any(re.search(rf"triage_execution\.{m}\b", src) for m in MODEL_FNS):
                found.append(name)
                with self.subTest(handler=name):
                    self.assertTrue(getattr(fn, "model_budgeted", False), f"{name} calls the model without the cap")
        self.assertEqual(len(found), 6, found)

    def test_per_visitor_daily_cap_then_global_daily_cap(self):
        with _env(TRIAGE_DAILY_MAX_MODEL_CALLS="3", TRIAGE_PER_VISITOR_DAILY_MAX="2",
                  TRIAGE_PER_VISITOR_MIN_SECONDS="0"):
            self.assertEqual([self._diagnose("1.1.1.1").status_code for _ in range(3)], [200, 200, 429])
            self.assertEqual(self._diagnose("2.2.2.2").status_code, 200)
            refused = self._diagnose("3.3.3.3")
        self.assertEqual(refused.status_code, 429)
        self.assertEqual(refused.json()["outcome"], "daily_cap_reached")
        self.assertGreater(int(refused.headers["retry-after"]), 0)
        self.assertEqual(len(self.model_calls), 3, "a refused request reached the model")

    def test_cooldown_between_calls_from_one_visitor(self):
        with _env(TRIAGE_PER_VISITOR_MIN_SECONDS="60", TRIAGE_DAILY_MAX_MODEL_CALLS="50"):
            self.assertEqual(self._diagnose("4.4.4.4").status_code, 200)
            second = self._diagnose("4.4.4.4")
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["outcome"], "cooldown")
        self.assertEqual(len(self.model_calls), 1)

    def test_zero_switches_the_model_steps_off_and_owner_cannot_bypass_the_daily_cap(self):
        with _env(TRIAGE_DAILY_MAX_MODEL_CALLS="0", OWNER_API_TOKEN=TOKEN):
            self.assertEqual(self._diagnose("5.5.5.5").status_code, 429)
            self.assertEqual(self._diagnose("5.5.5.5", {"x-owner-token": TOKEN}).status_code, 429)
        self.assertEqual(self.model_calls, [])

    def test_owner_is_exempt_from_visitor_limits_only(self):
        with _env(TRIAGE_DAILY_MAX_MODEL_CALLS="10", TRIAGE_PER_VISITOR_MIN_SECONDS="600", OWNER_API_TOKEN=TOKEN):
            codes = [self._diagnose("6.6.6.6", {"x-owner-token": TOKEN}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 200])

    def test_garbage_or_negative_env_values_never_remove_the_cap(self):
        with _env(TRIAGE_DAILY_MAX_MODEL_CALLS="lots", TRIAGE_PER_VISITOR_DAILY_MAX="-5"):
            lim = triage_budget.limits()
        self.assertEqual(lim["daily_max"], triage_budget.DEFAULT_DAILY_MAX)
        self.assertEqual(lim["per_visitor_daily_max"], 0)


if __name__ == "__main__":
    unittest.main()
