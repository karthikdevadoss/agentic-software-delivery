"""Automation Sprint 4 / S1: the owner's Claude Code prompts never leave the API.

Until this sprint the public Usage page and GET /api/sessions/history
returned the first prompt of every Claude Code session (goal / raw_capture).
These tests drive the REAL routes and the REAL session_history code against a
fake ledger connection whose prompt rows contain a sentinel string. If any
query reads prompt text, or any field carries it, the sentinel shows up in
the HTTP response and the test fails. Hermetic: no database, no network.
"""
import json
import pathlib
import re
import unittest
from datetime import datetime, timezone
from unittest import mock

from starlette.testclient import TestClient

import event_ledger as el
import session_history as sh
import web_server

SENTINEL = "SENTINEL-PRIVATE-PROMPT do not wait for my approval C:\\Users\\owner"
SID = "4f0fd490-b705-4907-a2ba-6263b291e640"
T0 = datetime(2026, 9, 30, 8, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)


class _Cursor:
    def __init__(self, log):
        self.log, self.description, self._rows = log, [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self.log.append(sql)
        low = " ".join(sql.split()).lower()
        self.description, self._rows = [("x",)], []
        if "user_prompt_submitted" in low:
            # A prompt row exists in the ledger. Whatever the query asks for,
            # anything text-like it could read is the sentinel.
            if "prompt" in low.replace("user_prompt_submitted", ""):
                self._rows = [(SID, SENTINEL)]
            elif "count(" in low:
                self._rows = [(SID, 3)]
            else:
                self._rows = [(SID, SENTINEL)]
        elif "count(*) filter" in low and "known" in low:
            self._rows = [(0, 1, 0.0)]          # _cost_coverage_summary
        elif "as kind" in low or "from (" in low and "start_ts" in low or "where id = %s" in low:
            self.description = [(c,) for c in ("id", "kind", "start_ts", "end_ts", "has_end_event", "last_status")]
            self._rows = [(SID, sh.KIND_CLAUDE_CODE, T0, T1, True, "COMPLETED")]

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    def __init__(self):
        self.log = []

    def cursor(self):
        return _Cursor(self.log)

    def close(self):
        pass


def _fake_ledger(test):
    conn = _Conn()
    for target, value in ((el, "_connect"), (el, "ensure_schema")):
        p = mock.patch.object(target, value, (lambda c=conn: c) if value == "_connect" else (lambda: None))
        p.start()
        test.addCleanup(p.stop)
    return conn


class SessionHistoryNeverPublishesPromptTextTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = _fake_ledger(self)
        self.client = TestClient(web_server.app)

    def _assert_clean(self, body_text):
        self.assertNotIn("SENTINEL", body_text)
        self.assertNotIn("approval", body_text.lower())
        self.assertNotIn("C:\\\\Users", body_text)

    def test_history_list_route_carries_no_prompt_text(self):
        resp = self.client.get("/api/sessions/history")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self._assert_clean(resp.text)
        cc = [s for s in body["sessions"] if s["kind"] == sh.KIND_CLAUDE_CODE]
        self.assertTrue(cc, "fixture session missing -- the test would pass vacuously")
        s = cc[0]
        self.assertEqual(s["goal"], sh.CLAUDE_CODE_SESSION_LABEL)
        self.assertIsNone(s["raw_capture"])
        self.assertEqual(s["prompt_count"], 3)
        self.assertEqual(s["prompt_text"], "PRIVATE")
        self.assertEqual(s["start_utc"], T0.isoformat())

    def test_session_detail_route_carries_no_prompt_text(self):
        resp = self.client.get(f"/api/sessions/history/{SID}")
        self.assertIn(resp.status_code, (200, 404), resp.text)
        self._assert_clean(resp.text)
        if resp.status_code == 200:
            d = resp.json()
            self.assertEqual(d["goal"], sh.CLAUDE_CODE_SESSION_LABEL)
            self.assertIsNone(d["raw_capture"])

    def test_no_query_reads_the_prompt_text_at_all(self):
        self.client.get("/api/sessions/history")
        self.client.get(f"/api/sessions/history/{SID}")
        prompt_queries = [q for q in self.conn.log if "user_prompt_submitted" in q]
        self.assertTrue(prompt_queries)
        for q in self.conn.log:
            self.assertNotIn("prompt_excerpt", q)


class SourceGuardTestCase(unittest.TestCase):
    """Belt and braces: the publishing modules must not name the stored
    prompt field, so a future edit cannot quietly re-introduce the read."""

    def test_publishing_modules_never_reference_the_prompt_field(self):
        here = pathlib.Path(__file__).resolve().parent
        for name in ("session_history.py", "sessions_data.py", "dashboard_data.py", "web_server.py"):
            with self.subTest(module=name):
                self.assertNotIn("prompt_excerpt", (here / name).read_text(encoding="utf-8"))

    def test_render_summary_for_claude_code_is_label_counts_and_tokens_only(self):
        r = {"id": SID, "kind": sh.KIND_CLAUDE_CODE, "start_ts": T0, "end_ts": T1,
             "has_end_event": True, "last_status": "COMPLETED"}
        s = sh._render_session_summary(r, {SID: 7}, {}, {}, {}, {}, {})
        self.assertEqual((s["goal"], s["raw_capture"], s["prompt_count"]),
                         (sh.CLAUDE_CODE_SESSION_LABEL, None, 7))
        self.assertIn("private", s["prompt_privacy_note"].lower())


if __name__ == "__main__":
    unittest.main()
