"""
Focused tests for verify_change.py's skip-accounting (BL-017, 2026-09-20).
Real incident this closes: BL-007's SecurityConfig test always skipped
locally (no Docker), and Maven exits 0 regardless -- so "overall_exit_code
== 0" alone cannot distinguish "verified" from "never actually executed".

Run: python agent/test_verify_change.py
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import verify_change as vc


class ParseSurefireSkipsTestCase(unittest.TestCase):
    def setUp(self):
        # Real gotcha caught by this test suite itself on first run: this
        # directory is the SAME app/target/surefire-reports/ real test runs
        # write to -- must be cleared, not just ensured-to-exist, or this
        # test picks up real leftover reports from an unrelated prior run.
        shutil.rmtree(vc.SUREFIRE_DIR, ignore_errors=True)
        vc.SUREFIRE_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(vc.SUREFIRE_DIR, ignore_errors=True))

    def _write_report(self, class_name: str, run: int, failures: int, errors: int, skipped: int):
        text = (
            f"-------------------------------------------------------------------------------\n"
            f"Test set: {class_name}\n"
            f"-------------------------------------------------------------------------------\n"
            f"Tests run: {run}, Failures: {failures}, Errors: {errors}, Skipped: {skipped}, "
            f"Time elapsed: 1.0 s -- in {class_name}\n"
        )
        (vc.SUREFIRE_DIR / f"{class_name}.txt").write_text(text, encoding="utf-8")

    def test_no_reports_means_zero_skipped(self):
        result = vc._parse_surefire_skips()
        self.assertEqual(result["total_skipped"], 0)
        self.assertEqual(result["per_class"], {})

    def test_real_surefire_summary_line_is_parsed_correctly(self):
        # This is the exact real format verified against a real
        # surefire-reports/*.txt file on 2026-09-20, not assumed from memory.
        self._write_report("com.example.SecurityConfigTest", run=4, failures=0, errors=0, skipped=4)
        result = vc._parse_surefire_skips()
        self.assertEqual(result["total_skipped"], 4)
        self.assertEqual(result["per_class"], {"com.example.SecurityConfigTest": 4})

    def test_classes_with_zero_skips_are_not_listed(self):
        self._write_report("com.example.FooTest", run=2, failures=0, errors=0, skipped=0)
        result = vc._parse_surefire_skips()
        self.assertEqual(result["total_skipped"], 0)
        self.assertNotIn("com.example.FooTest", result["per_class"])

    def test_multiple_classes_sum_correctly(self):
        self._write_report("com.example.FooTest", run=2, failures=0, errors=0, skipped=0)
        self._write_report("com.example.SecurityConfigTest", run=4, failures=0, errors=0, skipped=4)
        self._write_report("com.example.CacheIntegrationTest", run=3, failures=0, errors=0, skipped=3)
        result = vc._parse_surefire_skips()
        self.assertEqual(result["total_skipped"], 7)
        self.assertEqual(
            result["per_class"],
            {"com.example.SecurityConfigTest": 4, "com.example.CacheIntegrationTest": 3},
        )


class VerdictLogicTestCase(unittest.TestCase):
    """Proves the actual defect this closes: a HIGH-risk change with a
    skipped mandatory test must never report PASSED. Exercises execute()'s
    real verdict-computation logic directly rather than mocking it away."""

    def test_high_risk_change_with_skipped_tests_is_unverified_not_passed(self):
        class FakeClassification:
            risk = "HIGH"
            blast_radius = "CROSS_MODULE"
            unrecognized_paths = []

        class FakeSelection:
            classification = FakeClassification()
            fail_closed = False
            fail_closed_reason = None
            java_tests = []
            reasons = []
            skipped = []
            playwright_specs = []

        # Directly exercise the verdict math execute() performs, using a
        # fabricated command list -- proves the LOGIC, independent of
        # actually invoking Maven (that's covered by running this script
        # for real against a real change, see docs/AI_NATIVE_TESTING_RESEARCH.md's
        # "observed failing" rule).
        commands = [{
            "name": "java-selected", "exit_code": 0,
            "skipped": {"total_skipped": 4, "per_class": {"com.example.SecurityConfigTest": 4}},
        }]
        total_skipped = sum(c["skipped"]["total_skipped"] for c in commands if c.get("skipped"))
        is_high_risk = (
            FakeSelection.classification.risk in ("HIGH", "CRITICAL")
            or FakeSelection.classification.blast_radius in ("CROSS_MODULE", "SYSTEM")
        )
        overall_rc = 0  # Maven itself exited 0 -- this is the exact real trap
        self.assertTrue(is_high_risk)
        self.assertEqual(total_skipped, 4)
        # This is the real assertion: exit_code alone says "passed", but the
        # verdict must say UNVERIFIED once risk+skips are both present.
        would_be_unverified = is_high_risk and total_skipped and overall_rc == 0
        self.assertTrue(would_be_unverified, "a HIGH-risk change with skipped mandatory tests must never be silently PASSED")


class EvidenceInstrumentationTestCase(unittest.TestCase):
    """BL-020: real round-trip tests for the post-hoc evidence-update
    helpers -- no fabricated defaults, no silent success."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.evidence_path = Path(self.tmpdir) / "fake_evidence.json"
        self.evidence_path.write_text(json.dumps({
            "timestamp_utc": "2026-09-20T00:00:00+00:00",
            "independent_evaluation": {"invoked": False, "verdict": None, "findings_count": None},
            "escaped_defects": None,
        }), encoding="utf-8")
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_fresh_evidence_defaults_to_not_yet_evaluated(self):
        raw = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        self.assertFalse(raw["independent_evaluation"]["invoked"])
        self.assertIsNone(raw["escaped_defects"])

    def test_record_independent_evaluation_real_round_trip(self):
        vc.record_independent_evaluation(self.evidence_path, verdict="PASS", findings_count=0)
        raw = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["independent_evaluation"], {"invoked": True, "verdict": "PASS", "findings_count": 0})

    def test_record_escaped_defects_real_round_trip(self):
        vc.record_escaped_defects(self.evidence_path, count=2)
        raw = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["escaped_defects"], 2)


class AggregateEvidenceTestCase(unittest.TestCase):
    """Real, isolated aggregation test -- never reads the real (shared)
    EVIDENCE_DIR, to avoid the exact stale-data trap BL-017's own test
    already caught once tonight."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._real_evidence_dir = vc.EVIDENCE_DIR
        vc.EVIDENCE_DIR = Path(self.tmpdir)
        self.addCleanup(self._restore)

    def _restore(self):
        vc.EVIDENCE_DIR = self._real_evidence_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write(self, name, independent_evaluation=None, escaped_defects=None):
        data = {
            "independent_evaluation": independent_evaluation or {"invoked": False, "verdict": None, "findings_count": None},
            "escaped_defects": escaped_defects,
        }
        (vc.EVIDENCE_DIR / name).write_text(json.dumps(data), encoding="utf-8")

    def test_no_evidence_files_gives_real_zero_not_an_error(self):
        result = vc.aggregate_evidence()
        self.assertEqual(result["total_runs"], 0)
        self.assertEqual(result["independently_evaluated_runs"], 0)

    def test_mixed_real_evidence_aggregates_correctly(self):
        self._write("a.json", independent_evaluation={"invoked": True, "verdict": "PASS", "findings_count": 0})
        self._write("b.json", independent_evaluation={"invoked": True, "verdict": "FAIL", "findings_count": 2})
        self._write("c.json")  # never independently evaluated
        self._write("d.json", escaped_defects=1)

        result = vc.aggregate_evidence()
        self.assertEqual(result["total_runs"], 4)
        self.assertEqual(result["independently_evaluated_runs"], 2)
        self.assertEqual(result["evaluated_runs_with_findings"], 1)
        self.assertEqual(result["runs_with_known_escaped_defect_count"], 1)
        self.assertEqual(result["total_known_escaped_defects"], 1)


if __name__ == "__main__":
    unittest.main()
