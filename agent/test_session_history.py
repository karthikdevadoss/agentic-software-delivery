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


class MojibakeRepairTestCase(unittest.TestCase):
    """Real incident (2026-09-11, Owner-observed on live production): a
    reconstructed session's prompt text displayed as 'â†’' instead of
    the real arrow character '→'. Root-caused to a genuine double
    mis-encoding already present in the stored ledger data (confirmed via
    raw byte inspection), not a rendering-only artifact."""

    def test_repairs_the_exact_real_corrupted_arrow_sequence(self):
        # Build the exact real mojibake independently of typing the
        # corrupted form directly in this source file (avoids this
        # environment's own console-encoding issues corrupting the test
        # itself): take a real arrow, mis-decode its UTF-8 bytes as
        # cp1252 -- that IS the real corrupted string this incident found.
        real_arrow = "→"
        corrupted = real_arrow.encode("utf-8").decode("cp1252")
        repaired = sh.repair_mojibake(corrupted)
        self.assertEqual(repaired, real_arrow)

    def test_correct_ascii_text_is_never_altered(self):
        text = "Change the Create button label from Create to Create Customer"
        self.assertEqual(sh.repair_mojibake(text), text)

    def test_correct_text_containing_a_real_arrow_is_never_altered(self):
        text = "System Design → Databases"
        self.assertEqual(sh.repair_mojibake(text), text)

    def test_none_and_empty_string_pass_through_safely(self):
        self.assertIsNone(sh.repair_mojibake(None))
        self.assertEqual(sh.repair_mojibake(""), "")


class ConciseTitleTestCase(unittest.TestCase):
    """Real incident (2026-09-11, Owner-observed on live production): a
    several-hundred-character raw Claude Code prompt was displayed
    verbatim as a session's visible title, dominating the page."""

    def test_long_multiline_prompt_becomes_a_short_title(self):
        long_prompt = "Do the thing\n" + ("more detail " * 100)
        title = sh.concise_title(long_prompt)
        self.assertLess(len(title), 200)
        self.assertTrue(title.startswith("Do the thing"))

    def test_short_single_line_text_is_unchanged(self):
        text = "Change the Create button label"
        self.assertEqual(sh.concise_title(text), text)

    def test_none_passes_through_safely(self):
        self.assertIsNone(sh.concise_title(None))


class ListSessionsTestCase(unittest.TestCase):
    def test_list_sessions_reachable_shape(self):
        data = sh.list_sessions(limit=5)
        self.assertEqual(data["status"], "REACHABLE")
        self.assertIn("sessions", data)
        self.assertIn("next_cursor", data)
        self.assertIn("has_more", data)

    def test_cost_coverage_summary_present_and_never_shows_unknown_as_zero(self):
        data = sh.list_sessions(limit=5)
        summary = data["cost_coverage_summary"]
        for key in ("known_cost_total_usd", "sessions_with_known_cost",
                    "sessions_with_unknown_cost", "cost_coverage_pct"):
            self.assertIn(key, summary)
        self.assertGreaterEqual(summary["sessions_with_known_cost"], 1)
        self.assertGreaterEqual(summary["known_cost_total_usd"], 0)
        total = summary["sessions_with_known_cost"] + summary["sessions_with_unknown_cost"]
        if total:
            self.assertEqual(summary["cost_coverage_pct"], round(100 * summary["sessions_with_known_cost"] / total))

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

    def test_quality_score_is_distinct_from_evidence_coverage(self):
        """Real incident (2026-09-11, Owner-observed on live production):
        the top summary showed 'QUALITY / 100% coverage', conflating a
        quality score with evidence coverage. This project has no
        legitimate composite quality-scoring algorithm -- quality_score
        must be honestly None/NOT SCORED, structurally separate from
        evidence_coverage_pct, never renamed or merged."""
        d = sh.get_session_detail("trainer-4733d1c0")
        q = d["quality"]
        self.assertIn("quality_score", q)
        self.assertIn("quality_score_label", q)
        self.assertIsNone(q["quality_score"])
        self.assertEqual(q["quality_score_label"], "NOT SCORED")
        self.assertIn("evidence_coverage_pct", q)
        self.assertNotEqual(q["quality_score_label"], q.get("overall_confidence"))

    def test_reconstructed_window_is_never_labeled_a_captured_duration(self):
        """Real incident (2026-09-11): a reconstructed Claude Code session
        showed '12.1 hr' with AI active time UNKNOWN, visually implying
        12.1 hours of continuous work. A session with no genuine
        dev_session_ended event must be labeled OBSERVED_EVENT_WINDOW, not
        CAPTURED_SESSION_DURATION, and must carry an explicit caveat."""
        d = sh.get_session_detail("claude-code-session-73e068c1-p0-eventledger-task")
        self.assertIsNotNone(d)
        if d["provenance"] == "PARTIAL_RECONSTRUCTION":
            self.assertEqual(d["window_kind"], "OBSERVED_EVENT_WINDOW")
            self.assertIn("does not prove continuous activity", d["window_note"])

    def test_zero_duration_is_never_shown_as_a_proven_0ms(self):
        wall_ms, window_kind, note = sh._window_semantics(
            datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc), True,
        )
        self.assertEqual(wall_ms, 0)
        self.assertEqual(window_kind, "UNKNOWN")
        self.assertIn("DURATION NOT CAPTURED", note)

    def test_cost_display_label_covers_all_four_canonical_states(self):
        actual = sh._cost_display_label({"status": "EXACT"}, {"status": "ACTUAL"})
        agg_only = sh._cost_display_label({"status": "AGGREGATE_ONLY"}, {"status": "COST_UNAVAILABLE"})
        not_captured = sh._cost_display_label({"status": "NOT_CAPTURED"}, {"status": "COST_UNAVAILABLE"})
        self.assertIn("ACTUAL", actual)
        self.assertIn("AGGREGATE_ONLY", agg_only)
        self.assertIn("NOT CAPTURED", not_captured)
        self.assertNotIn("$0", actual + agg_only + not_captured)

    def test_long_raw_prompt_goal_has_concise_title_and_preserved_raw_capture(self):
        d = sh.get_session_detail("4f0fd490-b705-4907-a2ba-6263b291e640")
        self.assertIsNotNone(d)
        self.assertLess(len(d["goal"]), 200)
        self.assertIsNotNone(d["raw_capture"])
        self.assertGreater(len(d["raw_capture"]), len(d["goal"]))
        self.assertIn("→", d["raw_capture"])  # mojibake repaired in the full capture, not just truncated away

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
