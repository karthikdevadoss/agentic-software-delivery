"""Public Workbench: the visitor's click is the human decision (2026-10-21 18:19).

Owner rule: no waiting-for-approval step and no approval queue for visitors.
One click runs the change at once on a SANDBOX copy of the Customer App page
and returns the result. The real pipeline (clone, commit, deploy) stays
owner-only.

Hermetic: TestClient against the real app. threading.Thread is replaced, so
even a bug could not start a real clone, commit, push or deploy; the tests
also assert it was never called on the visitor path.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from starlette.testclient import TestClient

import demo_catalogue
import web_server as ws
import workbench_budget

OWNER = "owner-token-for-tests"
IN_SCOPE = demo_catalogue.SUGGESTED_EXAMPLES[0]
FOOTER = 'Change the footer text to "One click test"'


class WorkbenchOneClickTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)
        self.env = mock.patch.dict(os.environ, {"OWNER_API_TOKEN": OWNER})
        self.env.start()
        self.thread = mock.patch.object(ws.threading, "Thread")
        self.Thread = self.thread.start()
        self.slot = mock.patch.object(ws, "_reserve_run_slot", return_value=True)
        self.slot.start()
        self.deploy = mock.patch.object(ws.demo_execution, "trigger_deploy",
                                        side_effect=AssertionError("must not deploy"))
        self.deploy.start()
        ws._LAST_TRAINER_RUN_FINISHED_AT = 0.0
        workbench_budget._reset_for_tests()

    def tearDown(self):
        self.deploy.stop()
        self.slot.stop()
        self.thread.stop()
        self.env.stop()
        workbench_budget._reset_for_tests()

    def _click(self, requirement=FOOTER, ip="203.0.113.7", **kw):
        return self.client.post("/api/trainer/runs", json={"requirement": requirement},
                                headers={"X-Forwarded-For": ip, **kw.pop("headers", {})})

    def test_visitor_click_runs_at_once_on_the_sandbox(self):
        r = self._click()
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["blocked"])
        self.assertEqual(body["mode"], "sandbox")
        self.assertEqual(body["decided_by"], "visitor click")
        self.assertEqual(body["result"]["status"], "COMPLETED")
        self.assertEqual(body["result"]["checked_value"], "One click test")
        self.assertEqual(body["cost"], {"model_calls": 0, "tokens": 0, "usd": 0.0, "model_key_needed": False})
        self.assertNotIn("_normalized", body["assessment"])
        self.Thread.assert_not_called()          # no real pipeline thread

    def test_no_waiting_for_approval_state_anywhere(self):
        for path in ("/api/trainer/assess", "/api/trainer/runs"):
            text = self.client.post(path, json={"requirement": IN_SCOPE},
                                    headers={"X-Forwarded-For": "198.51.100.1"}).text
            with self.subTest(path=path):
                self.assertNotIn("approval_required", text)
                self.assertNotIn("once the owner approves", text)

    def test_assess_says_the_visitor_decides(self):
        body = self.client.post("/api/trainer/assess", json={"requirement": IN_SCOPE}).json()
        self.assertEqual(body["decision"], "auto")
        self.assertEqual(body["mode"], "sandbox")
        self.assertIn("A person decides before any action", body["message"])

    def test_sandbox_never_touches_the_baseline_file(self):
        before = ws.DEMO_BASELINE_FILE.read_text(encoding="utf-8")
        self._click()
        self.assertEqual(ws.DEMO_BASELINE_FILE.read_text(encoding="utf-8"), before)

    def test_sandbox_preview_is_served_with_scripts_blocked(self):
        pid = self._click().json()["result"]["preview_id"]
        r = self.client.get(f"/api/trainer/sandbox/{pid}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("One click test", r.text)
        self.assertIn("sandbox", r.headers["content-security-policy"])
        self.assertEqual(self.client.get("/api/trainer/sandbox/sandbox-nope").status_code, 404)

    def test_works_without_a_model_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            self.assertEqual(self._click().json()["result"]["status"], "COMPLETED")

    def test_out_of_scope_request_is_refused_and_nothing_runs(self):
        body = self._click("Delete the database").json()
        self.assertTrue(body["blocked"])
        self.assertEqual(body["assessment"]["decision"], "blocked")
        self.assertNotIn("owner approval", body["assessment"]["message"])
        self.Thread.assert_not_called()

    def test_per_ip_gap_is_enforced(self):
        self.assertEqual(self._click().status_code, 200)
        r = self._click()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()["status"], "COOLDOWN")
        self.assertEqual(self._click(ip="203.0.113.8").status_code, 200)   # another visitor

    def test_per_ip_daily_ceiling(self):
        with mock.patch.object(workbench_budget, "WORKBENCH_PER_VISITOR_MIN_SECONDS", 0):
            for _ in range(workbench_budget.WORKBENCH_PER_VISITOR_DAILY_MAX):
                self.assertEqual(self._click().status_code, 200)
            self.assertEqual(self._click().json()["status"], "VISITOR_CAP")

    def test_daily_click_cap(self):
        with mock.patch.object(workbench_budget, "WORKBENCH_DAILY_MAX_CLICKS", 2):
            self._click(ip="10.0.0.1"); self._click(ip="10.0.0.2")
            r = self._click(ip="10.0.0.3")
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()["status"], "DAILY_CAP")

    def test_daily_usd_budget_is_enforced(self):
        workbench_budget.record_click("x", cost_usd=workbench_budget.WORKBENCH_DAILY_USD_BUDGET + 0.01)
        r = self._click()
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()["status"], "DAILY_CAP")

    def test_owner_still_gets_the_real_pipeline(self):
        r = self._click(headers={"X-Owner-Token": OWNER})
        body = r.json()
        self.assertFalse(body["blocked"], body)
        self.assertNotIn("mode", body)
        self.Thread.assert_called_once()

    def test_wrong_token_gets_the_sandbox_not_the_real_pipeline(self):
        body = self._click(headers={"X-Owner-Token": "not-the-owner"}).json()
        self.assertEqual(body["mode"], "sandbox")
        self.Thread.assert_not_called()

    def test_reset_needs_the_owner(self):
        r = self.client.post("/api/trainer/reset")
        self.assertEqual(r.status_code, 401)
        self.Thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
