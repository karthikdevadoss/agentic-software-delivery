"""A person approves before anything changes on the Workbench (2026-10-21).

Hermetic: TestClient against the real app, the run thread is replaced so no
clone, commit, push or deploy can happen. Before this, an in-scope catalogue
request started a real deploy with no human step.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from starlette.testclient import TestClient

import demo_catalogue
import web_server as ws

OWNER = "owner-token-for-tests"
IN_SCOPE = demo_catalogue.SUGGESTED_EXAMPLES[0]


class WorkbenchApprovalGateTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)
        self.env = mock.patch.dict(os.environ, {"OWNER_API_TOKEN": OWNER})
        self.env.start()
        self.thread = mock.patch.object(ws.threading, "Thread")
        self.Thread = self.thread.start()
        self.slot = mock.patch.object(ws, "_reserve_run_slot", return_value=True)
        self.slot.start()
        ws._LAST_TRAINER_RUN_FINISHED_AT = 0.0

    def tearDown(self):
        self.slot.stop()
        self.thread.stop()
        self.env.stop()

    def test_in_scope_request_without_approval_starts_nothing(self):
        r = self.client.post("/api/trainer/runs", json={"requirement": IN_SCOPE})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["blocked"])
        self.assertEqual(body["assessment"]["decision"], "approval_required")
        self.assertIn("A person approves", body["assessment"]["message"])
        self.assertNotIn("_normalized", body["assessment"])
        self.Thread.assert_not_called()

    def test_assess_preview_reports_waiting_for_approval(self):
        r = self.client.post("/api/trainer/assess", json={"requirement": IN_SCOPE})
        self.assertEqual(r.json()["decision"], "approval_required")

    def test_owner_approval_starts_the_run(self):
        r = self.client.post("/api/trainer/runs", json={"requirement": IN_SCOPE},
                             headers={"X-Owner-Token": OWNER})
        body = r.json()
        self.assertFalse(body["blocked"], body)
        self.Thread.assert_called_once()

    def test_wrong_token_is_not_an_approval(self):
        r = self.client.post("/api/trainer/runs", json={"requirement": IN_SCOPE},
                             headers={"X-Owner-Token": "not-the-owner"})
        self.assertTrue(r.json()["blocked"])
        self.Thread.assert_not_called()

    def test_unset_owner_token_fails_closed(self):
        with mock.patch.dict(os.environ, {"OWNER_API_TOKEN": ""}):
            r = self.client.post("/api/trainer/runs", json={"requirement": IN_SCOPE},
                                 headers={"X-Owner-Token": ""})
        self.assertTrue(r.json()["blocked"])
        self.Thread.assert_not_called()

    def test_reset_needs_the_owner(self):
        r = self.client.post("/api/trainer/reset")
        self.assertEqual(r.status_code, 401)
        self.Thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()
