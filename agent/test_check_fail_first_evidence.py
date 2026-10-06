import json
import tempfile
import unittest
from pathlib import Path

import check_fail_first_evidence as cf


class BuildReportTestCase(unittest.TestCase):
    def test_test_id_with_class(self):
        self.assertEqual(
            cf._test_id({"file": "test_x.py", "class": "SomeCase", "test": "test_a"}),
            "test_x.py::SomeCase::test_a",
        )

    def test_test_id_without_class(self):
        self.assertEqual(
            cf._test_id({"file": "test_x.py", "class": None, "test": "test_a"}),
            "test_x.py::test_a",
        )

    def test_report_against_real_registry_and_manifest_files_is_internally_consistent(self):
        report = cf.build_report()
        self.assertEqual(
            report["has_fail_first_record"] + report["no_fail_first_record"],
            report["total_tests"],
        )
        self.assertEqual(report["stale_registry_entries"], [],
                          "a stale entry means fail_first_evidence.json and "
                          "test_oracle_manifest.json have drifted -- regenerate "
                          "the manifest (python agent/classify_test_oracles.py)")

    def test_a_test_present_in_both_registry_and_manifest_counts_as_has_record(self):
        with tempfile.TemporaryDirectory() as d:
            manifest_path = Path(d) / "manifest.json"
            registry_path = Path(d) / "registry.json"
            manifest_path.write_text(json.dumps({"tests": [
                {"file": "test_x.py", "class": "C", "test": "test_a"},
                {"file": "test_x.py", "class": "C", "test": "test_b"},
            ]}), encoding="utf-8")
            registry_path.write_text(json.dumps({"entries": {
                "test_x.py::C::test_a": {"observed_failing_at": "2026-01-01", "how": "x", "context": "y"},
            }}), encoding="utf-8")

            orig_manifest, orig_evidence = cf.MANIFEST_PATH, cf.EVIDENCE_PATH
            cf.MANIFEST_PATH, cf.EVIDENCE_PATH = manifest_path, registry_path
            try:
                report = cf.build_report()
            finally:
                cf.MANIFEST_PATH, cf.EVIDENCE_PATH = orig_manifest, orig_evidence

        self.assertEqual(report["total_tests"], 2)
        self.assertEqual(report["has_fail_first_record"], 1)
        self.assertEqual(report["no_fail_first_record"], 1)
        self.assertIn("test_x.py::C::test_b", report["no_record_ids"])

    def test_stale_entry_in_registry_not_matching_any_real_test_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            manifest_path = Path(d) / "manifest.json"
            registry_path = Path(d) / "registry.json"
            manifest_path.write_text(json.dumps({"tests": [
                {"file": "test_x.py", "class": "C", "test": "test_a"},
            ]}), encoding="utf-8")
            registry_path.write_text(json.dumps({"entries": {
                "test_x.py::C::test_renamed_away": {"observed_failing_at": "2026-01-01", "how": "x", "context": "y"},
            }}), encoding="utf-8")

            orig_manifest, orig_evidence = cf.MANIFEST_PATH, cf.EVIDENCE_PATH
            cf.MANIFEST_PATH, cf.EVIDENCE_PATH = manifest_path, registry_path
            try:
                report = cf.build_report()
            finally:
                cf.MANIFEST_PATH, cf.EVIDENCE_PATH = orig_manifest, orig_evidence

        self.assertEqual(report["stale_registry_entries"], ["test_x.py::C::test_renamed_away"])


if __name__ == "__main__":
    unittest.main()
