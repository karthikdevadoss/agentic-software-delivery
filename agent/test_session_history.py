"""
Focused tests for agent/session_history.py — the complete historical
session system (P0-B). Runs against the REAL live event ledger, per this
project's convention (see agent/test_event_ledger.py's own docstring) of
proving actual data behavior rather than mocking the ledger away.

Run: python agent/test_session_history.py
"""

import unittest
import uuid
from datetime import datetime, timezone

import event_ledger as el
import session_history as sh


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class ListSessionsTestCase(unittest.TestCase):
    def test_list_sessions_reachable_shape(self):
        data = sh.list_sessions(limit=5)
        self.assertEqual(data["status"], "REACHABLE")
        self.assertIn("sessions", data)
        self.assertIn("next_cursor", data)
        self.assertIn("has_more", data)

    def test_malformed_before_cursor_returns_truthful_error_not_a_crash(self):
        """Real incident (2026-09-11, live production verification): a
        `before` cursor with an unencoded '+' decoded to a space by
        standard query-string parsing raised an unhandled ValueError from
        datetime.fromisoformat(), surfacing as a raw 500. Must now return
        a clean, honest INVALID_CURSOR result instead of raising."""
        space_for_plus = "2026-09-10T02:17:07.628697 00:00"  # exactly what an unencoded '+' becomes
        data = sh.list_sessions(before_cursor=space_for_plus, limit=5)
        self.assertEqual(data["status"], "INVALID_CURSOR")
        self.assertIn("error", data)
        self.assertEqual(data["sessions"], [])

    def test_properly_encoded_cursor_with_plus_still_works(self):
        """The real ISO cursor this API itself returns (next_cursor)
        always contains a '+' UTC offset -- confirm a genuinely valid
        cursor is never rejected by the fix above."""
        first_page = sh.list_sessions(limit=3)
        if not first_page.get("next_cursor"):
            self.skipTest("not enough real history for a second page right now")
        second_page = sh.list_sessions(before_cursor=first_page["next_cursor"], limit=3)
        self.assertEqual(second_page["status"], "REACHABLE")

    def test_sessions_span_multiple_real_dates(self):
        """Real historical evidence in this project's ledger spans more
        than one calendar day -- prove the listing surfaces more than
        just 'today', not merely that the function runs."""
        seen_dates = set()
        cursor = None
        for _ in range(10):
            data = sh.list_sessions(before_cursor=cursor, limit=25)
            for s in data["sessions"]:
                if s["start_utc"]:
                    seen_dates.add(s["start_utc"][:10])
            if not data["has_more"]:
                break
            cursor = data["next_cursor"]
        self.assertGreaterEqual(len(seen_dates), 2, f"expected multiple real dates, got {seen_dates}")

    def test_pagination_reaches_earliest_session_without_duplicates(self):
        seen_ids = []
        cursor = None
        for _ in range(15):
            data = sh.list_sessions(before_cursor=cursor, limit=10)
            seen_ids.extend(s["session_id"] + "|" + s["kind"] for s in data["sessions"])
            if not data["has_more"]:
                break
            cursor = data["next_cursor"]
        self.assertEqual(len(seen_ids), len(set(seen_ids)), "pagination produced duplicate sessions")
        self.assertGreater(len(seen_ids), 10, "expected more than one page of real sessions")

    def test_test_fixture_session_ids_are_excluded(self):
        """Unit-test fixture session_ids (this project's OWN test suite
        writes directly to the real ledger -- see test_claude_code_hook.py)
        must never appear as fabricated 'sessions' in the real history."""
        cursor = None
        all_ids = []
        for _ in range(15):
            data = sh.list_sessions(before_cursor=cursor, limit=25)
            all_ids.extend(s["session_id"] for s in data["sessions"] if s["kind"] == "claude_code_dev_session")
            if not data["has_more"]:
                break
            cursor = data["next_cursor"]
        for sid in all_ids:
            self.assertFalse(sid.startswith("sess-distinct-"), sid)
            self.assertFalse(sid.startswith("sess-spoolonly-sync-"), sid)
            self.assertNotEqual(sid, "sess-speed-test")

    def test_workbench_run_has_exact_tokens_and_actual_cost_when_captured(self):
        data = sh.list_sessions(limit=50)
        workbench_with_usage = [s for s in data["sessions"] if s["kind"] == "workbench_run" and s["tokens"]["status"] == "EXACT"]
        self.assertGreater(len(workbench_with_usage), 0, "expected at least one workbench run with real captured usage")
        s = workbench_with_usage[0]
        self.assertIn("input_tokens", s["tokens"])
        self.assertIn(s["cost"]["status"], ("ACTUAL", "COST_UNAVAILABLE"))

    def test_v2_trial_tokens_are_aggregate_only_never_fake_exact(self):
        data = sh.list_sessions(limit=50)
        v2_sessions = [s for s in data["sessions"] if s["kind"] == "v2_trial_benchmark"]
        self.assertGreater(len(v2_sessions), 0)
        for s in v2_sessions:
            self.assertIn(s["tokens"]["status"], ("AGGREGATE_ONLY", "NOT_CAPTURED"))
            self.assertNotEqual(s["cost"]["status"], "ACTUAL")


class SessionDetailTestCase(unittest.TestCase):
    def test_unknown_session_returns_none(self):
        self.assertIsNone(sh.get_session_detail(_unique("no-such-session")))

    def test_known_workbench_run_detail_has_full_shape(self):
        d = sh.get_session_detail("trainer-4733d1c0")
        self.assertIsNotNone(d)
        for key in ("timeline", "human_interventions", "value", "quality", "comparison",
                    "ai_active_ms", "human_active_note", "tokens", "cost"):
            self.assertIn(key, d)
        self.assertGreater(len(d["timeline"]), 0)

    def test_ai_active_time_is_derived_from_real_tool_call_durations(self):
        d = sh.get_session_detail("trainer-4733d1c0")
        self.assertIsNotNone(d["ai_active_ms"])
        self.assertIn("DERIVED", d["ai_active_ms_note"])

    def test_human_active_time_is_honestly_unknown_never_guessed(self):
        d = sh.get_session_detail("trainer-4733d1c0")
        self.assertIsNone(d["human_active_ms"])
        self.assertIn("UNKNOWN", d["human_active_note"])

    def test_quality_never_reports_100_percent_without_full_evidence(self):
        """Real incident (2026-09-11, live production verification):
        evidence_coverage_pct previously counted 'was this dimension
        evaluated' (always true by construction), so it -- and
        overall_confidence -- were silently 100%/HIGH_CONFIDENCE for
        EVERY session, including ones with zero captured tokens/cost/
        timing. Prove a thin-evidence real session (trainer-c830f5a6:
        NO_CHANGE_NEEDED, no tokens/cost/ai_active_time captured) scores
        strictly lower than a rich-evidence real session
        (trainer-4733d1c0: real tokens, cost, AI active time) -- coverage
        must actually distinguish them, not be a fixed constant."""
        rich = sh.get_session_detail("trainer-4733d1c0")
        thin = sh.get_session_detail("trainer-c830f5a6")
        self.assertLess(thin["quality"]["evidence_coverage_pct"], rich["quality"]["evidence_coverage_pct"])
        self.assertEqual(thin["quality"]["evidence_coverage_pct"], 0)
        self.assertNotEqual(thin["quality"]["overall_confidence"], "HIGH_CONFIDENCE")
        self.assertEqual(rich["quality"]["overall_confidence"], "HIGH_CONFIDENCE")
        for v in thin["quality"]["evidence_availability"].values():
            self.assertFalse(v)

    def test_comparison_requires_at_least_three_comparable_sessions(self):
        d = sh.get_session_detail("trainer-4733d1c0")
        comp = d["comparison"]
        self.assertIn(comp["status"], ("COMPARABLE", "INSUFFICIENT_COMPARABLE_HISTORY"))
        if comp["status"] == "COMPARABLE":
            self.assertGreaterEqual(comp["cohort_size"], 3)

    def test_v2_trial_detail_cost_honestly_unavailable(self):
        d = sh.get_session_detail("v2-shadow-trial-3-uncertainty-2026-09-11")
        self.assertIsNotNone(d)
        self.assertEqual(d["cost"]["status"], "COST_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
