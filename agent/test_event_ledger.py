"""
Focused tests for agent/event_ledger.py — the durable, append-only event
ledger behind CLAUDE.md's P0 "no more lost engineering events" foundation.

Covers, at minimum, the scenarios required before this foundation can be
called reliable (do not trust one INSERT test):
  A. a normal event reaches the remote DB
  B. multiple events preserve real ordering (timestamp/event_id)
  C. a duplicate-event retry does not create a duplicate row
  D. remote DB unavailable -> event lands in the local spool, not dropped
  E. remote DB returns -> a spooled event syncs and is removed from the spool
  F. a run failing BEFORE reaching a terminal state still has its earlier
     events durably preserved (no batching-to-the-end)
  G. sensitive-looking fields are redacted before they ever reach storage
  H. an earlier failure event is not erased/overwritten by a later success
  I. a full run trajectory can be reconstructed from stored events alone
  J. model/token usage data is preserved when present

Tests A/B/C/I/J touch the REAL Railway Postgres instance configured via
EVENT_LEDGER_DATABASE_URL (see docs/RESOURCE_REGISTRY.md) — this is a real
network dependency, deliberately: this suite's whole purpose is proving
the actual remote ledger, not a mock of it. D/E/F/G/H patch only the
network boundary (_insert) so outage/ordering/redaction behavior can be
proven deterministically without depending on the DB being *down* on
demand.

Run: python agent/test_event_ledger.py
"""

import json
import unittest
import uuid
from pathlib import Path
from unittest import mock

import event_ledger as el


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class RealRemoteInsertTestCase(unittest.TestCase):
    """A. Normal event -> real remote DB."""

    def test_a_record_event_persists_remotely_and_is_queryable(self):
        run_id = _unique("test-run-a")
        result = el.record_event("run_started", run_id=run_id, source="test_suite",
                                  status="ok", payload={"note": "scenario A"})
        self.assertTrue(result["remote_persisted"], msg=result)

        rows = el.get_run_events(run_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_type"], "run_started")


class OrderingTestCase(unittest.TestCase):
    """B. Multiple events preserve real ordering via timestamp/event_id."""

    def test_b_events_are_returned_in_the_order_they_were_recorded(self):
        run_id = _unique("test-run-b")
        expected_types = ["run_started", "stage_started", "tool_call_started",
                           "tool_call_completed", "run_completed"]
        for event_type in expected_types:
            result = el.record_event(event_type, run_id=run_id, source="test_suite")
            self.assertTrue(result["remote_persisted"], msg=result)

        rows = el.get_run_events(run_id)
        self.assertEqual([r["event_type"] for r in rows], expected_types)
        # event_id is a real, distinct UUID per event, not reused/derived.
        self.assertEqual(len({r["event_id"] for r in rows}), len(expected_types))


class IdempotentRetryTestCase(unittest.TestCase):
    """C. A retried insert of the SAME event_id is a no-op, never a
    duplicate row — the exact guarantee sync_spool() depends on."""

    def test_c_duplicate_insert_of_the_same_event_id_does_not_duplicate(self):
        run_id = _unique("test-run-c")
        envelope = el.build_envelope("run_started", run_id=run_id, source="test_suite")

        el._insert(envelope)
        el._insert(envelope)  # deliberate retry of the identical envelope/event_id
        el._insert(envelope)  # and again

        rows = el.get_run_events(run_id)
        self.assertEqual(len(rows), 1, "duplicate retries must not create duplicate rows")
        self.assertEqual(rows[0]["event_id"], envelope["event_id"])


class RunReconstructionTestCase(unittest.TestCase):
    """I. A full run trajectory can be reconstructed from stored events
    alone — proves run_id correlation actually works end-to-end, not just
    for a single event type."""

    def test_i_full_trajectory_reconstructable_from_run_id_alone(self):
        run_id = _unique("test-run-i")
        trajectory = [
            ("run_started", {"payload": {"requirement": "add a health endpoint"}}),
            ("stage_started", {"stage": "PLANNING"}),
            ("tool_call_started", {"tool_name": "read_file"}),
            ("tool_call_completed", {"tool_name": "read_file", "duration_ms": 4.2}),
            ("change_proposed", {"stage": "PROPOSING CHANGE"}),
            ("authorization_decision", {"payload": {"decision": "approve"}}),
            ("build_completed", {"duration_ms": 15327.0}),
            ("test_completed", {"duration_ms": 18972.0}),
            ("run_completed", {"payload": {"text": "done"}}),
        ]
        for event_type, fields in trajectory:
            result = el.record_event(event_type, run_id=run_id, source="test_suite", **fields)
            self.assertTrue(result["remote_persisted"], msg=result)

        rows = el.get_run_events(run_id)
        self.assertEqual([r["event_type"] for r in rows], [t for t, _ in trajectory])
        # The trajectory is reconstructable end-to-end: first event is the
        # real start, last is the real completion, nothing missing between.
        self.assertEqual(rows[0]["event_type"], "run_started")
        self.assertEqual(rows[-1]["event_type"], "run_completed")


class TokenUsageTestCase(unittest.TestCase):
    """J. Model/token usage data is preserved where the provider exposes
    it — and honestly absent (None), never invented, where it doesn't."""

    def test_j_token_fields_round_trip_through_the_real_ledger(self):
        run_id = _unique("test-run-j")
        el.record_event(
            "model_usage", run_id=run_id, source="test_suite",
            provider="anthropic", model="claude-sonnet-5",
            input_tokens=1234, output_tokens=567,
            cache_read_tokens=89, cache_write_tokens=None,
        )
        rows = el.get_run_events(run_id)
        self.assertEqual(len(rows), 1)
        # get_run_events() is a minimal projection (Section 13) that does
        # not select token columns — verify the real stored row directly.
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT provider, model, input_tokens, output_tokens, "
                    "cache_read_tokens, cache_write_tokens FROM delivery_events WHERE run_id = %s",
                    (run_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        self.assertEqual(row, ("anthropic", "claude-sonnet-5", 1234, 567, 89, None))


class OutageSpoolTestCase(unittest.TestCase):
    """D/E. Remote unavailable -> spooled, not dropped. Remote returns ->
    spooled event syncs and is removed from the spool. Uses a dedicated
    spool file so this test can never interact with the real spool a live
    server process might be using."""

    def setUp(self):
        self.spool_path = Path(el.SPOOL_PATH).parent / f"event_spool_test_{uuid.uuid4().hex[:8]}.jsonl"
        self._patcher = mock.patch.object(el, "SPOOL_PATH", self.spool_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if self.spool_path.exists():
            self.spool_path.unlink()

    def test_d_remote_failure_spools_the_event_instead_of_dropping_it(self):
        run_id = _unique("test-run-d")
        with mock.patch.object(el, "_insert", side_effect=RuntimeError("simulated remote outage")):
            result = el.record_event("run_started", run_id=run_id, source="test_suite")

        self.assertFalse(result["remote_persisted"])
        self.assertTrue(result["spooled"])
        self.assertEqual(el.spool_pending_count(), 1)

        spooled = json.loads(self.spool_path.read_text(encoding="utf-8").strip())
        self.assertEqual(spooled["run_id"], run_id)
        self.assertEqual(spooled["event_id"], result["event_id"])

    def test_e_spooled_event_syncs_once_the_remote_ledger_is_reachable_again(self):
        run_id = _unique("test-run-e")
        with mock.patch.object(el, "_insert", side_effect=RuntimeError("simulated remote outage")):
            result = el.record_event("run_started", run_id=run_id, source="test_suite")
        self.assertEqual(el.spool_pending_count(), 1)

        sync_result = el.sync_spool()  # real _insert this time — genuine remote recovery
        self.assertEqual(sync_result["synced"], 1)
        self.assertEqual(sync_result["remaining"], 0)
        self.assertEqual(el.spool_pending_count(), 0)
        self.assertFalse(self.spool_path.exists(), "spool file should be removed once fully drained")

        rows = el.get_run_events(run_id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_id"], result["event_id"])

    def test_sync_spool_retry_is_idempotent_no_duplicate_after_partial_success(self):
        """A spool entry that IS already in the remote DB (e.g. a prior
        sync partially succeeded before a crash) must sync as a safe
        no-op, never a duplicate row — the same ON CONFLICT guarantee as
        scenario C, exercised through the spool path specifically."""
        run_id = _unique("test-run-e2")
        envelope = el.build_envelope("run_started", run_id=run_id, source="test_suite")
        el._insert(envelope)  # already present remotely
        with self.spool_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope) + "\n")  # but ALSO still sitting in the spool

        sync_result = el.sync_spool()
        self.assertEqual(sync_result["synced"], 1)
        rows = el.get_run_events(run_id)
        self.assertEqual(len(rows), 1, "spool retry of an already-inserted event must not duplicate")


class PreTerminalCrashDurabilityTestCase(unittest.TestCase):
    """F. A run that fails/crashes BEFORE reaching a terminal state must
    not lose events emitted earlier — write-through means each event is
    already durable the moment it happened, independent of how the run
    ultimately ends."""

    def test_f_earlier_events_survive_even_if_no_terminal_event_ever_arrives(self):
        run_id = _unique("test-run-f")
        el.record_event("run_started", run_id=run_id, source="test_suite")
        el.record_event("stage_started", run_id=run_id, source="test_suite", stage="PLANNING")
        el.record_event("tool_call_started", run_id=run_id, source="test_suite", tool_name="read_file")
        # Simulated hard crash here — no run_completed/run_failed event ever recorded.

        rows = el.get_run_events(run_id)
        self.assertEqual(len(rows), 3, "all pre-crash events must already be durable")
        self.assertEqual(rows[-1]["event_type"], "tool_call_started")


class HistoricalFailureNotOverwrittenTestCase(unittest.TestCase):
    """H. An append-only ledger never overwrites an earlier failure event
    just because a later run/attempt succeeded — both rows must coexist."""

    def test_h_earlier_failure_event_remains_after_a_later_success(self):
        run_id_failed = _unique("test-run-h-fail")
        run_id_ok = _unique("test-run-h-ok")
        el.record_event("run_failed", run_id=run_id_failed, source="test_suite",
                         status="FAILED", payload={"message": "compile failed"})
        el.record_event("run_completed", run_id=run_id_ok, source="test_suite",
                         status="COMPLETED")

        failed_rows = el.get_run_events(run_id_failed)
        self.assertEqual(len(failed_rows), 1)
        self.assertEqual(failed_rows[0]["event_type"], "run_failed")
        self.assertEqual(failed_rows[0]["status"], "FAILED")


class SecretRedactionTestCase(unittest.TestCase):
    """G. Sensitive-looking fields are redacted before ever reaching
    storage (remote OR spool) — tested against the payload-construction
    boundary directly so it needs no network."""

    def test_g_api_key_shaped_value_in_payload_is_redacted_before_storage(self):
        envelope = el.build_envelope(
            "error", run_id="test-run-g",
            payload={"message": "call failed", "api_key": "sk-ant-realsecretvalue1234567890"},
        )
        self.assertNotIn("sk-ant-realsecretvalue1234567890", json.dumps(envelope["payload"]))
        self.assertIn("REDACTED", json.dumps(envelope["payload"]))

    def test_g_secret_shaped_value_never_reaches_the_local_spool_either(self):
        spool_path = Path(el.SPOOL_PATH).parent / f"event_spool_test_{uuid.uuid4().hex[:8]}.jsonl"
        try:
            with mock.patch.object(el, "SPOOL_PATH", spool_path), \
                 mock.patch.object(el, "_insert", side_effect=RuntimeError("simulated outage")):
                el.record_event(
                    "error", run_id="test-run-g2",
                    payload={"message": "AKIAABCDEFGHIJKLMNOP leaked in a log line"},
                )
            spooled_text = spool_path.read_text(encoding="utf-8")
            self.assertNotIn("AKIAABCDEFGHIJKLMNOP", spooled_text)
            self.assertIn("REDACTED", spooled_text)
        finally:
            if spool_path.exists():
                spool_path.unlink()


class EnvelopeConstructionTestCase(unittest.TestCase):
    """Section 2: absent fields are honestly None, never invented, and
    unknown kwargs fail fast rather than being silently swallowed."""

    def test_unsupplied_fields_are_none_not_fabricated(self):
        envelope = el.build_envelope("run_started", run_id="r1")
        self.assertIsNone(envelope["model"])
        self.assertIsNone(envelope["input_tokens"])
        self.assertIsNone(envelope["deployment_version"])

    def test_unknown_field_raises_instead_of_being_silently_dropped(self):
        with self.assertRaises(TypeError):
            el.build_envelope("run_started", run_id="r1", not_a_real_field="x")


if __name__ == "__main__":
    unittest.main()
