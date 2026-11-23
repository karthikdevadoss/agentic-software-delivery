"""Tests for the Kubernetes probe endpoints /healthz and /readyz.

Run: python agent/test_health_endpoints.py
"""
import os
import unittest
from unittest import mock

from starlette.testclient import TestClient

import web_server as ws


class HealthEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)

    def test_healthz_ok(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    def test_healthz_does_not_touch_ledger(self):
        with mock.patch.dict(os.environ, {"EVENT_LEDGER_DATABASE_URL": "postgres://unreachable.invalid/x"}):
            with mock.patch.object(ws.event_ledger, "_connect", side_effect=AssertionError("db touched")):
                self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_readyz_ledger_not_configured(self):
        env = {k: v for k, v in os.environ.items() if k != "EVENT_LEDGER_DATABASE_URL"}
        with mock.patch.dict(os.environ, env, clear=True):
            r = self.client.get("/readyz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ready")
        self.assertEqual(r.json()["ledger"], "not_configured")

    def test_readyz_ledger_configured_no_network(self):
        with mock.patch.dict(os.environ, {"EVENT_LEDGER_DATABASE_URL": "postgres://unreachable.invalid/x"}):
            with mock.patch.object(ws.event_ledger, "_connect", side_effect=AssertionError("db touched")):
                r = self.client.get("/readyz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["ledger"], "configured")
        self.assertFalse(r.json()["ledger_affects_readiness"])

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post("/healthz").status_code, 405)
        self.assertEqual(self.client.post("/readyz").status_code, 405)


if __name__ == "__main__":
    unittest.main()
