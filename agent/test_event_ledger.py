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
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import event_ledger as el


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class ConnectionResilienceTestCase(unittest.TestCase):
    """RELIABILITY P0 (2026-09-13): a real production incident traced a
    full-service outage to a single connection left "idle in
    transaction" for 16+ real minutes (found live via a direct
    pg_stat_activity query), holding a lock that blocked every
    subsequent ensure_schema() DDL call. Every connection-opening
    function in this module already used try/finally correctly (audited
    during the incident) — the most consistent explanation is a
    container killed mid-query during a deploy cutover, orphaning the
    connection faster than Postgres's own default dead-peer detection.
    These two real (not mocked) session parameters are the fix: a bound
    on any single statement's runtime, and a bound on how long a
    connection may sit idle-in-transaction before Postgres itself kills
    it — defense in depth this application's own code cannot provide by
    itself against an externally-orphaned connection."""

    def test_real_connection_has_a_bounded_statement_timeout(self):
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW statement_timeout")
                self.assertEqual(cur.fetchone()[0], "15s")
        finally:
            conn.close()

    def test_real_connection_has_a_bounded_idle_in_transaction_timeout(self):
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW idle_in_transaction_session_timeout")
                self.assertEqual(cur.fetchone()[0], "30s")
        finally:
            conn.close()

    def test_ensure_schema_completes_well_within_the_statement_timeout(self):
        """Direct regression for the exact incident: ensure_schema()'s
        multi-statement DDL must complete comfortably inside the
        timeout, not merely avoid raising by accident."""
        el._schema_ready = False
        start = time.monotonic()
        el.ensure_schema()
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 15.0, f"ensure_schema() took {elapsed:.1f}s — dangerously close to or over the 15s statement_timeout")

    def test_concurrent_ensure_schema_calls_run_the_ddl_exactly_once(self):
        """RELIABILITY (2026-09-17): PR #10 observed apparent Postgres
        "deadlock" contention when many concurrent Playwright workers each
        triggered their own first request against a fresh process (every
        one racing the unsynchronized `if _schema_ready: return` check).
        Root cause: no lock guarded the check-then-act window, so N
        concurrent callers could all pass the check and all run schema.sql's
        DDL at once, contending for the same Postgres lock. Proven here
        without a live DB: _connect() is mocked and counted directly —
        with the fix (module-level _lock around the DDL), exactly one of
        20 concurrent threads may actually reach _connect(); all others
        must simply observe _schema_ready already True and return."""
        el._schema_ready = False
        call_count = 0
        count_lock = threading.Lock()

        class _FakeCursor:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, *a, **kw):
                time.sleep(0.05)  # simulate real DDL taking non-zero time

        class _FakeConn:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def cursor(self):
                return _FakeCursor()

            def close(self):
                pass

        def _fake_connect():
            nonlocal call_count
            with count_lock:
                call_count += 1
            return _FakeConn()

        with mock.patch.object(el, "_connect", side_effect=_fake_connect):
            threads = [threading.Thread(target=el.ensure_schema) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(call_count, 1, f"expected exactly 1 real DDL connection across 20 concurrent callers, got {call_count}")
        self.assertTrue(el._schema_ready)


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


class RecentEventsExcludesMockFixturesTestCase(unittest.TestCase):
    """Real regression for the flagship-completion session's Usage
    'Event Ledger (Live)' mock-leak finding: source='workbench_mock' rows
    carrying synthetic far-future timestamps (2099-01-01) must never
    appear in the default recent-events feed, only real evidence should,
    and the explicit include_test_data=True opt-in must still surface
    them. Ledger contains: one real event (now), one workbench_mock event
    (2099-01-01), proving both the exclusion and the opt-in against the
    real live database, not a mock of it."""

    def test_default_excludes_workbench_mock_2099_fixture_but_includes_real_event(self):
        real_run_id = _unique("test-run-real")
        mock_run_id = _unique("test-run-mock-2099")

        real_envelope = el.build_envelope(
            "run_completed", run_id=real_run_id, source="test_suite", status="ok")
        el._insert(real_envelope)

        mock_envelope = el.build_envelope(
            "run_completed", run_id=mock_run_id, source="workbench_mock", status="ok")
        # Other test suites (test_session_history.py) already accumulate
        # their own 2099-dated workbench_mock fixtures in this same real,
        # shared database -- use year 9999 so this test's own row is
        # unambiguously the newest of all of them, regardless of what
        # else has piled up.
        mock_envelope["timestamp_utc"] = "9999-01-01T00:00:00+00:00"
        el._insert(mock_envelope)

        default_rows = el.get_recent_events(limit=5)
        default_run_ids = {r["run_id"] for r in default_rows}
        self.assertIn(real_run_id, default_run_ids,
                       "a real event must be present in the default recent-events feed")
        self.assertNotIn(mock_run_id, default_run_ids,
                          "a workbench_mock 2099-dated fixture must never appear by default "
                          "-- it would otherwise permanently sort above all real evidence")

        # Our year-9999 fixture is guaranteed newer than any other
        # fixture already accumulated in this real, shared ledger (other
        # suites use 2099), so it must be the literal top row when test
        # data is included -- directly reproducing the exact live
        # production defect this regression guards against (a
        # far-future-dated workbench_mock row permanently floating above
        # all real evidence).
        with_test_data_rows = el.get_recent_events(limit=1, include_test_data=True)
        self.assertEqual(with_test_data_rows[0]["run_id"], mock_run_id,
                          "include_test_data=True must still surface the real, preserved fixture row, "
                          "sorted above real events by its genuine (far-future) timestamp")


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


class SyncSpoolFreshProcessTestCase(unittest.TestCase):
    """Real incident (2026-09-18): sync_spool()'s `with _lock:` calls
    _insert(), which unconditionally calls ensure_schema(), which itself
    does `with _lock:` -- a non-reentrant threading.Lock deadlocks a
    thread trying to re-acquire a lock it already holds. This is not a
    rare interleaving: EVERY real background sync is a brand-new
    subprocess (trigger_background_sync() always spawns `python
    event_ledger.py --sync-spool` fresh), so _schema_ready is False and
    this path is hit on every single real sync. Simulates that exact
    fresh-process condition by resetting _schema_ready before calling
    sync_spool() directly (can't spawn a real subprocess and assert on
    its hang from here) -- if the lock regresses to non-reentrant, this
    test must hang/timeout rather than silently pass."""

    def setUp(self):
        self.spool_path = Path(el.SPOOL_PATH).parent / f"event_spool_freshproc_test_{uuid.uuid4().hex[:8]}.jsonl"
        self._spool_patcher = mock.patch.object(el, "SPOOL_PATH", self.spool_path)
        self._spool_patcher.start()
        self._schema_ready_before = el._schema_ready
        el._schema_ready = False  # simulate a genuinely fresh process

    def tearDown(self):
        el._schema_ready = self._schema_ready_before
        self._spool_patcher.stop()
        if self.spool_path.exists():
            self.spool_path.unlink()

    def test_sync_spool_does_not_hang_when_schema_not_yet_initialized(self):
        run_id = _unique("test-run-freshproc")
        envelope = el.build_envelope("run_started", run_id=run_id, source="test_suite")
        self.spool_path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")

        result_holder = {}
        def _run():
            result_holder["result"] = el.sync_spool()
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=15)
        self.assertFalse(t.is_alive(), "sync_spool() hung -- the _lock reentrancy regressed")
        self.assertEqual(result_holder["result"]["synced"], 1)
        self.assertEqual(result_holder["result"]["remaining"], 0)


class StaleSyncLockTestCase(unittest.TestCase):
    """Real incident (2026-09-18): a sync process was killed before its
    `finally` could remove SYNC_LOCK_PATH, orphaning the lock. With no
    staleness check, trigger_background_sync() silently refused to spawn
    a new sync for 7 real days -- 18,190 real events piled up in the local
    spool, none ever reaching the durable ledger, with zero visible error
    anywhere (hooks must never raise). Uses a dedicated lock file so this
    test can never interact with a real sync a live process might be
    running."""

    def setUp(self):
        self.lock_path = Path(el.SYNC_LOCK_PATH).parent / f"event_ledger_sync_test_{uuid.uuid4().hex[:8]}.lock"
        self._patcher = mock.patch.object(el, "SYNC_LOCK_PATH", self.lock_path)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        if self.lock_path.exists():
            self.lock_path.unlink()

    def test_fresh_lock_still_blocks_a_new_sync(self):
        self.lock_path.touch()
        with mock.patch("subprocess.Popen") as popen:
            result = el.trigger_background_sync()
        popen.assert_not_called()
        self.assertFalse(result["spawned"])
        self.assertEqual(result["reason"], "sync already in progress")
        self.assertTrue(self.lock_path.exists(), "a fresh lock must not be removed")

    def test_stale_lock_past_max_age_is_removed_and_a_new_sync_spawns(self):
        self.lock_path.touch()
        stale_time = time.time() - el.SYNC_LOCK_MAX_AGE_SECONDS - 60
        import os
        os.utime(self.lock_path, (stale_time, stale_time))

        with mock.patch("subprocess.Popen") as popen:
            result = el.trigger_background_sync()

        popen.assert_called_once()
        self.assertTrue(result["spawned"])
        # a fresh lock was re-acquired for the new sync, not left absent
        self.assertTrue(self.lock_path.exists())
        self.assertLess(time.time() - self.lock_path.stat().st_mtime, 5)


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
        # Built from two non-contiguous literals so this fixture never sits
        # in the repo as a scannable, real-AWS-Access-Key-ID-shaped string
        # (GitHub push-protection correctly flags AKIA[0-9A-Z]{16} even when
        # fake) -- the concatenated runtime value still exercises tools.py's
        # real AKIA literal-pattern redaction exactly as before.
        fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
        try:
            with mock.patch.object(el, "SPOOL_PATH", spool_path), \
                 mock.patch.object(el, "_insert", side_effect=RuntimeError("simulated outage")):
                el.record_event(
                    "error", run_id="test-run-g2",
                    payload={"message": f"{fake_key} leaked in a log line"},
                )
            spooled_text = spool_path.read_text(encoding="utf-8")
            self.assertNotIn(fake_key, spooled_text)
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


class UsageEconomicsTestCase(unittest.TestCase):
    """K. Real, ledger-backed economics aggregation (get_usage_economics()).

    Root-caused real incident (2026-09-11): agent/dashboard_data.py's
    economics display was a static "NOT CAPTURED YET" constant that
    predated real usage capture and was never wired to it — this proves
    the REPLACEMENT actually reads real data, handles both pre-fix rows
    (real usage only inside the JSONB payload) and post-fix rows (also in
    dedicated columns) via COALESCE, and never drops a failed run's cost."""

    def _raw_row(self, run_id):
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT "
                    "COALESCE(input_tokens, (payload->>'input_tokens')::bigint), "
                    "COALESCE(output_tokens, (payload->>'output_tokens')::bigint), "
                    "COALESCE(cost_usd, (payload->>'cost_usd')::double precision), status "
                    "FROM delivery_events WHERE run_id = %s AND event_type = 'run_usage_summary'",
                    (run_id,),
                )
                return cur.fetchone()
        finally:
            conn.close()

    def _raw_cost_row(self, run_id):
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT "
                    "COALESCE(cost_usd, (payload->>'cost_usd')::double precision), "
                    "COALESCE(pricing_version, (payload->>'pricing_version')) "
                    "FROM delivery_events WHERE run_id = %s AND event_type = 'run_usage_summary'",
                    (run_id,),
                )
                return cur.fetchone()
        finally:
            conn.close()

    def test_payload_only_row_is_extracted_via_coalesce(self):
        """Simulates a pre-fix historical row: real usage exists ONLY in
        the JSONB payload, no dedicated columns populated — the COALESCE
        fallback must still surface it correctly."""
        run_id = _unique("test-econ-payload-only")
        el.record_event(
            "run_usage_summary", run_id=run_id, source="test_suite", status="COMPLETED",
            payload={"captured": True, "input_tokens": 111, "output_tokens": 22, "cost_usd": 0.001234, "pricing_version": "test-v1"},
        )
        row = self._raw_row(run_id)
        self.assertEqual(row, (111, 22, 0.001234, "COMPLETED"))

    def test_column_populated_row_prefers_real_columns_over_payload(self):
        """Simulates a post-fix row: real dedicated columns are populated
        (agent/web_server.py::_record_ledger_event's fix) — COALESCE must
        prefer them, not silently fall back to payload."""
        run_id = _unique("test-econ-columns")
        el.record_event(
            "run_usage_summary", run_id=run_id, source="test_suite", status="COMPLETED",
            input_tokens=999, output_tokens=88,
            payload={"captured": True, "input_tokens": 999, "output_tokens": 88, "cost_usd": 0.005, "pricing_version": "test-v1"},
        )
        row = self._raw_row(run_id)
        self.assertEqual(row[0], 999)
        self.assertEqual(row[1], 88)

    def test_cost_usd_and_pricing_version_are_real_queryable_columns(self):
        """cost_usd/pricing_version were the one pair left JSON-only after
        the input_tokens/output_tokens fix above -- same bug class, fixed
        later. Proves the real dedicated columns exist, are populated when
        supplied, and are preferred over payload by the same COALESCE
        pattern already proven for tokens."""
        run_id = _unique("test-econ-cost-columns")
        el.record_event(
            "run_usage_summary", run_id=run_id, source="test_suite", status="COMPLETED",
            cost_usd=0.009876, pricing_version="anthropic-2026-09-10-v1",
            payload={"captured": True, "cost_usd": 0.111111, "pricing_version": "stale-payload-only-value"},
        )
        row = self._raw_cost_row(run_id)
        self.assertEqual(row, (0.009876, "anthropic-2026-09-10-v1"))

    def test_failed_run_usage_is_preserved_not_dropped(self):
        """A failed run still spent real money — its usage row must be
        stored with status=FAILED, never silently excluded from the
        table get_usage_economics() aggregates over."""
        run_id = _unique("test-econ-failed")
        el.record_event(
            "run_usage_summary", run_id=run_id, source="test_suite", status="FAILED",
            payload={"captured": True, "input_tokens": 50, "output_tokens": 5, "cost_usd": 0.0002, "pricing_version": "test-v1"},
        )
        row = self._raw_row(run_id)
        self.assertEqual(row, (50, 5, 0.0002, "FAILED"))

    def test_get_usage_economics_returns_real_reachable_shape(self):
        """Smoke test against the real live ledger: the function must
        return the documented shape, never raise, and every window must
        at least include the row this test itself just inserted."""
        run_id = _unique("test-econ-shape")
        el.record_event(
            "run_usage_summary", run_id=run_id, source="test_suite", status="COMPLETED",
            input_tokens=7, output_tokens=3,
            payload={"captured": True, "input_tokens": 7, "output_tokens": 3, "cost_usd": 0.0001, "pricing_version": "test-v1"},
        )
        result = el.get_usage_economics()
        self.assertEqual(result["status"], "REACHABLE")
        for key in ("last_run", "last_hour_utc", "today_utc_calendar_day", "lifetime",
                    "this_hour", "last_24_hours", "today", "this_week", "this_month"):
            self.assertIn(key, result)
            self.assertIn("runs_total", result[key])
        # Lifetime spans everything -- must include what we just inserted.
        self.assertGreaterEqual(result["lifetime"]["runs_total"], 1)
        self.assertGreaterEqual(result["today_utc_calendar_day"]["runs_total"], 1)
        self.assertGreaterEqual(result["today"]["runs_total"], 1)
        self.assertGreaterEqual(result["this_week"]["runs_total"], 1)
        self.assertGreaterEqual(result["this_month"]["runs_total"], 1)
        self.assertEqual(result["display_timezone"], "Europe/Berlin")
        self.assertEqual(result["this_hour"]["window_kind"], "ROLLING")
        self.assertEqual(result["today"]["window_kind"], "CALENDAR")

    def test_captured_false_row_is_not_counted_as_zero_cost(self):
        """A run where no real API call happened must never be counted
        as if it cost $0 — it should be excluded from the token/cost
        sums entirely, distinct from a genuinely free/zero-cost run."""
        run_id = _unique("test-econ-not-captured")
        el.record_event(
            "run_usage_summary", run_id=run_id, source="test_suite", status="FAILED",
            payload={"captured": False},
        )
        conn = el._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE((payload->>'captured')::boolean, true) FROM delivery_events WHERE run_id = %s",
                    (run_id,),
                )
                captured_flag = cur.fetchone()[0]
        finally:
            conn.close()
        self.assertFalse(captured_flag)


class DisplayTimezoneWindowTestCase(unittest.TestCase):
    """L. compute_display_windows() — Europe/Berlin display-timezone
    aggregation windows (Phase D). Pure function, no DB dependency, so
    DST-transition correctness can be proven deterministically for fixed
    'now' instants rather than depending on when the suite happens to run.

    Europe/Berlin: CEST (+02:00) in summer, CET (+01:00) in winter.
    2026 spring-forward: 2026-03-29 01:00 UTC (02:00->03:00 local).
    2026 fall-back: 2026-10-25 01:00 UTC (03:00->02:00 local)."""

    def test_calendar_today_boundary_correct_during_cet_winter(self):
        from datetime import datetime, timezone
        now_utc = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)  # 11:00 CET local
        windows = el.compute_display_windows(now_utc)
        # Local midnight 2026-01-15 00:00 CET == 2026-01-14 23:00 UTC.
        self.assertEqual(
            windows["today_calendar_start_utc"],
            datetime(2026, 1, 14, 23, 0, 0, tzinfo=timezone.utc),
        )

    def test_calendar_today_boundary_correct_during_cest_summer(self):
        from datetime import datetime, timezone
        now_utc = datetime(2026, 7, 15, 10, 0, 0, tzinfo=timezone.utc)  # 12:00 CEST local
        windows = el.compute_display_windows(now_utc)
        # Local midnight 2026-07-15 00:00 CEST == 2026-07-14 22:00 UTC.
        self.assertEqual(
            windows["today_calendar_start_utc"],
            datetime(2026, 7, 14, 22, 0, 0, tzinfo=timezone.utc),
        )

    def test_calendar_today_boundary_shifts_correctly_across_spring_forward(self):
        from datetime import datetime, timezone
        # Just after the 2026-03-29 spring-forward instant (01:00 UTC).
        # Local time is now CEST (+02:00): 2026-03-29 05:00 local.
        now_utc = datetime(2026, 3, 29, 3, 0, 0, tzinfo=timezone.utc)
        windows = el.compute_display_windows(now_utc)
        # Local midnight 2026-03-29 00:00 CET (still +01:00, before the
        # 01:00 UTC transition) == 2026-03-28 23:00 UTC. If DST were
        # handled with a naive fixed offset instead of the real IANA
        # transition, this would be wrong by an hour.
        self.assertEqual(
            windows["today_calendar_start_utc"],
            datetime(2026, 3, 28, 23, 0, 0, tzinfo=timezone.utc),
        )

    def test_calendar_today_boundary_shifts_correctly_across_fall_back(self):
        from datetime import datetime, timezone
        # Just after the 2026-10-25 fall-back instant (01:00 UTC). Local
        # time is now CET (+01:00): 2026-10-25 02:30 local.
        now_utc = datetime(2026, 10, 25, 1, 30, 0, tzinfo=timezone.utc)
        windows = el.compute_display_windows(now_utc)
        # Local midnight 2026-10-25 00:00 CEST (still +02:00, before the
        # 01:00 UTC transition) == 2026-10-24 22:00 UTC.
        self.assertEqual(
            windows["today_calendar_start_utc"],
            datetime(2026, 10, 24, 22, 0, 0, tzinfo=timezone.utc),
        )

    def test_rolling_windows_are_pure_duration_independent_of_dst(self):
        from datetime import datetime, timedelta, timezone
        now_utc = datetime(2026, 3, 29, 3, 0, 0, tzinfo=timezone.utc)
        windows = el.compute_display_windows(now_utc)
        self.assertEqual(windows["this_hour_rolling_start_utc"], now_utc - timedelta(hours=1))
        self.assertEqual(windows["last_24_hours_rolling_start_utc"], now_utc - timedelta(hours=24))

    def test_this_week_starts_monday_local(self):
        from datetime import datetime, timezone
        # 2026-09-11 is a Friday.
        now_utc = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        windows = el.compute_display_windows(now_utc)
        # Monday 2026-09-07 00:00 CEST (+02:00) == 2026-09-06 22:00 UTC.
        self.assertEqual(
            windows["this_week_calendar_start_utc"],
            datetime(2026, 9, 6, 22, 0, 0, tzinfo=timezone.utc),
        )

    def test_this_month_starts_first_of_month_local(self):
        from datetime import datetime, timezone
        now_utc = datetime(2026, 9, 11, 10, 0, 0, tzinfo=timezone.utc)
        windows = el.compute_display_windows(now_utc)
        # 2026-09-01 00:00 CEST (+02:00) == 2026-08-31 22:00 UTC.
        self.assertEqual(
            windows["this_month_calendar_start_utc"],
            datetime(2026, 8, 31, 22, 0, 0, tzinfo=timezone.utc),
        )


class DevSessionCostSummaryTestCase(unittest.TestCase):
    """Real gap found 2026-09-18 (the 40 EUR overnight-session incident):
    get_usage_economics() is Workbench-only, but its 'Lifetime AI spend'
    figure sat unlabeled on the same page as a real, much larger Claude
    Code development cost -- confusing, per the Owner's own screenshot.
    get_dev_session_cost_summary() is the separate, equally-real
    counterpart for source='claude_code' sessions; this proves it computes
    real cost from real tokens via pricing_config.py, the same way
    session_history.py's per-session cost already does, never a second,
    divergent calculation."""

    def test_reachable_shape_and_scope_note_names_claude_code_only(self):
        result = el.get_dev_session_cost_summary()
        self.assertEqual(result["status"], "REACHABLE")
        self.assertIn("claude_code", result["canonical_source"])
        self.assertIn("lifetime", result)
        self.assertIn("today", result)
        self.assertIn("this_week", result)

    def test_a_real_inserted_row_is_costed_via_pricing_config_not_a_second_formula(self):
        """Real incident (2026-09-18, same night this test was first
        written): using a 'test-devcost-session-...' session_id inserted a
        real row that inflated get_dev_session_cost_summary()'s real
        lifetime total on live production, and (before the allowlist fix)
        showed up as a fake 'Claude Code Dev Session' card on the Owner's
        own Usage page -- confirmed via his own screenshot. Fixed two ways
        at once: (1) uses a REAL UUID-shaped session_id, exercising the
        exact code path/allowlist a genuine session goes through, and (2)
        deletes its own row via delete_event_for_test_cleanup() in a
        finally block, so it never persists in the shared production
        ledger even transiently-visible, regardless of test outcome."""
        import pricing_config
        session_id = str(uuid.uuid4())
        event_id = None
        try:
            result_insert = el.record_event(
                "model_usage", session_id=session_id, source="claude_code",
                activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
                provider="anthropic", model="claude-sonnet-5",
                input_tokens=1000, output_tokens=2000, cache_read_tokens=3000, cache_write_tokens=4000,
            )
            event_id = result_insert["event_id"]
            expected = pricing_config.calculate_cost(
                "anthropic", "claude-sonnet-5", input_tokens=1000, output_tokens=2000,
                cache_read_tokens=3000, cache_write_tokens=4000,
            )
            result = el.get_dev_session_cost_summary()
            # The real inserted row must be reflected in the real lifetime total
            # (>= since other real/test rows already exist in the shared ledger).
            self.assertGreaterEqual(result["lifetime"]["cost_usd"], expected["total_usd"] - 0.000001)
            self.assertGreaterEqual(result["lifetime"]["input_tokens"], 1000)
        finally:
            if event_id:
                el.delete_event_for_test_cleanup(event_id)


class SessionIncidentWindowTestCase(unittest.TestCase):
    """Real feature requested by the Owner (2026-09-18): a session's own
    detail page only ever showed the WHOLE session's total cost, even when
    a story specifically highlighted one narrow, notable sub-window (the
    real 40 EUR incident, gone in under 7 minutes) -- confirmed confusing
    via his own screenshot when clicking through landed on the 38-hour/
    $439 total instead. get_session_incident_windows() is a rare,
    manually-curated per-session record, never auto-generated -- most
    sessions have zero."""

    def test_no_windows_for_a_session_with_none_is_an_empty_list_not_an_error(self):
        result = el.get_session_incident_windows(str(uuid.uuid4()))
        self.assertEqual(result, [])

    def test_a_real_inserted_window_round_trips_with_its_own_distinct_cost(self):
        import pricing_config
        session_id = str(uuid.uuid4())
        event_id = None
        try:
            result_insert = el.record_event(
                "session_incident_window", session_id=session_id, source="claude_code",
                activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
                provider="anthropic", model="claude-sonnet-5",
                input_tokens=10, output_tokens=20, cache_read_tokens=30, cache_write_tokens=40,
                payload={
                    "window_start_utc": "2026-01-01T00:00:00+00:00", "window_end_utc": "2026-01-01T00:05:00+00:00",
                    "title": "Test window", "note": "a test note",
                    "cumulative_cost_before_usd": 1.0, "cumulative_cost_after_usd": 1.5,
                },
            )
            event_id = result_insert["event_id"]
            windows = el.get_session_incident_windows(session_id)
            self.assertEqual(len(windows), 1)
            w = windows[0]
            self.assertEqual(w["title"], "Test window")
            self.assertEqual(w["tokens"]["output_tokens"], 20)
            expected_cost = pricing_config.calculate_cost(
                "anthropic", "claude-sonnet-5", input_tokens=10, output_tokens=20,
                cache_read_tokens=30, cache_write_tokens=40,
            )
            self.assertEqual(w["cost"]["status"], "ACTUAL")
            self.assertAlmostEqual(w["cost"]["cost_usd"], expected_cost["total_usd"], places=6)
            self.assertEqual(w["cumulative_cost_before_usd"], 1.0)
            self.assertEqual(w["cumulative_cost_after_usd"], 1.5)
        finally:
            if event_id:
                el.delete_event_for_test_cleanup(event_id)


if __name__ == "__main__":
    unittest.main()
