"""
BL-104 (Sprint 27): regression test for a real mojibake bug found live in
production while verifying this task (run trainer-4e68fe81,
/api/sessions/history/trainer-4e68fe81 returned
"TESTING â€” NOT APPLICABLE" instead of "TESTING — NOT
APPLICABLE"). session_history.py::_workbench_engineering_evidence already
calls repair_mojibake() on `requirement` and `final_result_text`, but the
testing_state/testing_reason/requested_value/diff_old_line/diff_new_line
fields skipped it -- the same corruption class, just not repaired for
these five fields.

Hermetic: a fake Postgres connection/cursor, no real database. The live
production evidence (before/after) lives in this task's commit message,
since live Postgres isn't reachable from this dev environment -- this
test is the locally-runnable, CI-enforceable half of that verification.
"""

import unittest

import session_history as sh

# The exact real corruption pattern (see sh.repair_mojibake's own
# docstring): a real em-dash, double-mis-encoded cp1252-as-UTF-8.
_CORRUPTED_EM_DASH_STAGE = "TESTING " + "—".encode("utf-8").decode("cp1252") + " NOT APPLICABLE"


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **kw):
        pass

    def fetchall(self):
        return self._rows


class FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return FakeCursor(self._rows)


class WorkbenchEngineeringEvidenceMojibakeTestCase(unittest.TestCase):
    def test_testing_state_and_reason_are_repaired(self):
        rows = [
            ("stage_started", {"stage": _CORRUPTED_EM_DASH_STAGE, "reason": "a reason with " + _CORRUPTED_EM_DASH_STAGE}),
        ]
        ev = sh._workbench_engineering_evidence(FakeConn(rows), "fake-run-id")
        self.assertEqual(ev["testing_state"], "TESTING — NOT APPLICABLE")
        self.assertIn("—", ev["testing_reason"])
        self.assertNotIn("â€”", ev["testing_reason"])

    def test_requested_value_and_diff_lines_are_repaired(self):
        rows = [
            ("risk_assessment", {"new_value": "build " + _CORRUPTED_EM_DASH_STAGE}),
            ("diff", {"file": "f.html", "old_line": "old " + _CORRUPTED_EM_DASH_STAGE, "new_line": "new " + _CORRUPTED_EM_DASH_STAGE}),
        ]
        ev = sh._workbench_engineering_evidence(FakeConn(rows), "fake-run-id")
        self.assertNotIn("â€”", ev["requested_value"])
        self.assertNotIn("â€”", ev["diff_old_line"])
        self.assertNotIn("â€”", ev["diff_new_line"])

    def test_clean_ascii_testing_state_is_unaffected(self):
        rows = [("stage_started", {"stage": "TESTING - NOT APPLICABLE", "reason": "plain ascii"})]
        ev = sh._workbench_engineering_evidence(FakeConn(rows), "fake-run-id")
        self.assertEqual(ev["testing_state"], "TESTING - NOT APPLICABLE")
        self.assertEqual(ev["testing_reason"], "plain ascii")


if __name__ == "__main__":
    unittest.main()
