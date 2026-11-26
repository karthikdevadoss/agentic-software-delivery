"""Hermetic: when BUDGET_DATABASE_URL points at a Postgres that cannot be
reached, every budget caller REFUSES (fail closed) and nothing crashes.
Uses a closed local port, so it needs no database and no network."""
import os
import unittest
from unittest import mock

import budget_store
import gateway_budget
import si_budget
import triage_budget

UNREACHABLE = "postgresql://nobody@127.0.0.1:1/none?connect_timeout=1"


class FailClosedTests(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"BUDGET_DATABASE_URL": UNREACHABLE})
        p.start()
        self.addCleanup(p.stop)

    def test_backend_reports_postgres(self):
        self.assertEqual(budget_store.backend(), "postgres")

    def test_transaction_raises_store_unavailable(self):
        with self.assertRaises(budget_store.StoreUnavailable):
            with budget_store.transaction():
                pass

    def test_gateway_refuses_the_billed_call(self):
        v = gateway_budget.reserve("anthropic", "claude-sonnet-5", "s", "u", 100)
        self.assertFalse(v["allowed"])
        self.assertEqual(v["status"], "BUDGET_STORE_UNAVAILABLE")

    def test_settle_does_not_raise_after_a_paid_call(self):
        gateway_budget.settle(1, 0.01)  # reservation stays at worst case; no crash

    def test_status_reports_unavailable_instead_of_crashing(self):
        s = gateway_budget.status()
        self.assertFalse(s["store_available"])
        self.assertIn("daily_usd_cap", s)

    def test_standing_interview_refuses(self):
        v = si_budget.check("visitor-1")
        self.assertFalse(v["allowed"])
        self.assertEqual(v["status"], "STORE_UNAVAILABLE")
        si_budget.record_answer("visitor-1")  # no crash
        self.assertFalse(si_budget.status()["store_available"])

    def test_triage_refuses(self):
        v = triage_budget.check_and_reserve("visitor-1")
        self.assertFalse(v["allowed"])
        self.assertEqual(v["status"], "STORE_UNAVAILABLE")
        self.assertFalse(triage_budget.status()["store_available"])


if __name__ == "__main__":
    unittest.main()
