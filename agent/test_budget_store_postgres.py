"""Real-Postgres tests for the budget store (runs in the ledger-postgres CI
job). Database: BUDGET_TEST_DATABASE_URL, else EVENT_LEDGER_DATABASE_URL.
With BUDGET_REQUIRE_DB=1 a missing database is a FAILURE, not a skip, so the
CI job can never go green by skipping."""
import os
import threading
import unittest
from unittest import mock

import budget_store
import gateway_budget

URL = os.environ.get("BUDGET_TEST_DATABASE_URL") or os.environ.get("EVENT_LEDGER_DATABASE_URL")
REQUIRE = os.environ.get("BUDGET_REQUIRE_DB") == "1"


def _reachable() -> bool:
    if not URL:
        return False
    try:
        import psycopg2
        psycopg2.connect(URL, connect_timeout=3).close()
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_reachable() or REQUIRE, "no Postgres for budget tests")
class PostgresBudgetStoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(_reachable(), "BUDGET_REQUIRE_DB=1 but no Postgres is reachable")
        p = mock.patch.dict(os.environ, {"BUDGET_DATABASE_URL": URL})
        p.start()
        self.addCleanup(p.stop)
        budget_store.clear_scope("gateway")
        budget_store.clear_scope("pgtest")
        self.addCleanup(budget_store.clear_scope, "gateway")
        self.addCleanup(budget_store.clear_scope, "pgtest")

    def test_backend_is_postgres(self):
        self.assertEqual(budget_store.backend(), "postgres")

    def test_insert_count_usd_settle_round_trip(self):
        with budget_store.transaction() as tx:
            rid = tx.insert("pgtest", "2026-11-26", 100.0, visitor="v", run_id="r", usd=0.5)
            tx.insert("pgtest", "2026-11-26", 101.0, visitor="w", usd=0.25)
        with budget_store.transaction() as tx:
            tx.settle(rid, 0.1)
        with budget_store.transaction() as tx:
            self.assertEqual(tx.count("pgtest", "2026-11-26"), 2)
            self.assertEqual(tx.count("pgtest", "2026-11-26", visitor="v"), 1)
            self.assertAlmostEqual(tx.usd("pgtest", "2026-11-26"), 0.35)
            self.assertAlmostEqual(tx.usd("pgtest", "2026-11-26", run_id="r"), 0.1)
            self.assertEqual(tx.last_ts("pgtest", "v"), 100.0)
            self.assertEqual(tx.distinct_visitors("pgtest", "2026-11-26"), 2)
            self.assertEqual(tx.count_since("pgtest", 100.5), 1)

    def test_exception_rolls_back(self):
        with self.assertRaises(ValueError):
            with budget_store.transaction() as tx:
                tx.insert("pgtest", "2026-11-26", 1.0)
                raise ValueError("boom")
        with budget_store.transaction() as tx:
            self.assertEqual(tx.count("pgtest", "2026-11-26"), 0)

    def test_survives_a_process_restart(self):
        """A 'redeploy' = new process with fresh module state: rows persist."""
        with budget_store.transaction() as tx:
            tx.insert("pgtest", "2026-11-26", 1.0, usd=0.3)
        budget_store._initialised.clear()  # noqa: SLF001 - as after a fresh process start
        with budget_store.transaction() as tx:
            self.assertAlmostEqual(tx.usd("pgtest", "2026-11-26"), 0.3)

    def test_concurrent_reservations_never_exceed_the_daily_cap(self):
        """20 threads race for a cap that fits exactly 5 reservations."""
        lim = {**gateway_budget.limits(), "daily_usd_cap": 0.05, "per_request_usd_cap": 1.0,
               "rate_limit_calls": 1000, "rate_window_seconds": 60}
        results = []
        with mock.patch.object(gateway_budget, "limits", return_value=lim), \
                mock.patch.object(gateway_budget, "estimate_usd", return_value={"usd": 0.01, "basis": "test"}):
            def go():
                results.append(gateway_budget.reserve("anthropic", "m", "s", "u", 10)["allowed"])
            threads = [threading.Thread(target=go) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(results.count(True), 5, results)
        self.assertEqual(gateway_budget.status()["calls_today"], 5)


if __name__ == "__main__":
    unittest.main()
