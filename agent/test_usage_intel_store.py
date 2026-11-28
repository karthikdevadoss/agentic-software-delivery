"""Store tests.

Hermetic part: ledger row -> UsageEvent mapping (billing category, provenance).
Real-Postgres part (ledger-postgres CI job, EVENT_LEDGER_DATABASE_URL): the
end-to-end path  model call usage -> event_ledger.record_event -> Postgres ->
store.load_events -> analytics.overview, with the expected cost computed by
hand; plus outcomes, learning records and the audit trail round trip.
"""
import os
import unittest
import uuid
from datetime import datetime, timezone

from usage_intel import analytics, store
from usage_intel.learning import LearningRecord
from usage_intel.outcomes import Outcome

URL = os.environ.get("EVENT_LEDGER_DATABASE_URL")
REQUIRE = os.environ.get("BUDGET_REQUIRE_DB") == "1"


class RowMappingTests(unittest.TestCase):
    def row(self, **kw):
        base = {"event_id": "r1", "timestamp_utc": datetime(2026, 11, 28, 9, tzinfo=timezone.utc),
                "event_type": "model_usage", "status": None, "source": "trainer", "session_id": None,
                "run_id": "run-1", "trace_id": None, "provider": "anthropic", "model": "claude-sonnet-5-5",
                "input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_tokens": None,
                "cache_write_tokens": None, "duration_ms": 1200.0}
        base.update(kw)
        return base

    def test_platform_call_is_metered_and_provider_reported(self):
        ev = store.row_to_event(self.row())
        self.assertEqual(ev.billing_category, "metered_api")
        self.assertEqual(ev.provenance["input_tokens"], "provider_reported")
        self.assertEqual(ev.provenance["cache_read_tokens"], "unavailable")
        self.assertAlmostEqual(ev.cost_estimated, 3.0)  # 1M x $2 + 0.1M x $10
        self.assertEqual(ev.session_id, "run-1")

    def test_claude_code_is_equivalent_value_not_spend(self):
        ev = store.row_to_event(self.row(source="claude_code", session_id="cc-1"))
        self.assertEqual(ev.billing_category, "equivalent_api_value")
        self.assertEqual(ev.provenance["input_tokens"], "imported")
        self.assertIn("not billed", ev.provenance["note"])


def _reachable():
    if not URL:
        return False
    try:
        import psycopg2
        psycopg2.connect(URL, connect_timeout=3).close()
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_reachable() or REQUIRE, "no Postgres for usage store tests")
class LiveStoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(_reachable(), "BUDGET_REQUIRE_DB=1 but no Postgres is reachable")
        self.tag = "it-" + uuid.uuid4().hex[:8]

    def test_end_to_end_model_call_to_dashboard_numbers(self):
        import event_ledger
        # Two real-shaped model calls recorded through the ledger's write path.
        for i, (inp, out) in enumerate([(200_000, 10_000), (50_000, 5_000)]):
            r = event_ledger.record_event("model_usage", source="usage-intel-test", run_id=self.tag,
                                          provider="anthropic", model="claude-sonnet-5-5",
                                          input_tokens=inp, output_tokens=out)
            self.assertTrue(r["remote_persisted"], r)
        today = datetime.now(timezone.utc).date().isoformat()
        evs = [e for e in store.load_events(start=today, end=today) if e.task_id == self.tag]
        self.assertEqual(len(evs), 2)
        o = analytics.overview(evs)
        # (200k x $2 + 10k x $10) + (50k x $2 + 5k x $10) per 1M = 0.5 + 0.15 = 0.65
        self.assertAlmostEqual(o["cost_estimated"], 0.65, places=8)
        self.assertEqual(o["input_tokens"], 250_000)
        self.assertEqual(o["cost_coverage"], "2 of 2 calls priced")

    def test_outcome_learning_and_audit_round_trip(self):
        store.save_outcome(Outcome(f"o-{self.tag}", self.tag, "dev_task_completed", "completed",
                                   evidence="objective", org_id=store.OWNER_ORG, user_id="owner"), actor="owner")
        mine = [o for o in store.load_outcomes() if o.task_id == self.tag]
        self.assertEqual(len(mine), 1)
        self.assertTrue(mine[0].verified_success)
        n = store.save_learning([LearningRecord(f"s-{self.tag}", "Retrieval", "BM25", "verification",
                                                correct=True, attempt=1, evidence="assessment", source="manual",
                                                user_id="owner")], actor="owner")
        self.assertEqual(n, 1)
        self.assertTrue(any(r.session_id == f"s-{self.tag}" and r.verifies for r in store.load_learning()))
        acts = [a for a in store.load_audit(50) if a["target"] == f"o-{self.tag}"]
        self.assertEqual(acts[0]["action"], "outcome.create")


if __name__ == "__main__":
    unittest.main()
