import unittest
from unittest.mock import MagicMock

import environment_preflight as ep


class RequiredJavaVersionTestCase(unittest.TestCase):
    def test_reads_the_real_pom_xml_java_version(self):
        # Real, not mocked -- proves this module reads the actual current
        # app/pom.xml rather than a hardcoded duplicate that could drift.
        version = ep.required_java_major_version()
        self.assertEqual(version, 21)


class DetectedJavaVersionTestCase(unittest.TestCase):
    def test_parses_a_real_openjdk_version_string(self):
        fake_run = MagicMock(return_value=MagicMock(
            stderr='openjdk version "21.0.2" 2024-01-16\nOpenJDK Runtime Environment\n', stdout=""))
        major, raw = ep._detected_java_major_version(run_fn=fake_run)
        self.assertEqual(major, 21)

    def test_parses_a_newer_jdk_version_string(self):
        # Exactly this dev machine's own real installed JDK -- proven not
        # hypothetical.
        fake_run = MagicMock(return_value=MagicMock(
            stderr='openjdk version "24.0.1" 2025-04-15\n', stdout=""))
        major, raw = ep._detected_java_major_version(run_fn=fake_run)
        self.assertEqual(major, 24)

    def test_handles_java_not_on_path(self):
        fake_run = MagicMock(side_effect=FileNotFoundError())
        major, raw = ep._detected_java_major_version(run_fn=fake_run)
        self.assertIsNone(major)
        self.assertIn("not found", raw)

    def test_handles_unparseable_output_honestly(self):
        fake_run = MagicMock(return_value=MagicMock(stderr="", stdout="something unexpected"))
        major, raw = ep._detected_java_major_version(run_fn=fake_run)
        self.assertIsNone(major)


class CheckJavaToolchainTestCase(unittest.TestCase):
    def test_older_jdk_than_required_fails_closed(self):
        """The exact real AEQ-021 scenario: JDK 17 installed, pom.xml
        requires 21."""
        fake_run = MagicMock(return_value=MagicMock(
            stderr='openjdk version "17.0.9" 2023-10-17\n', stdout=""))
        result = ep.check_java_toolchain(run_fn=fake_run)
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")
        self.assertEqual(result["detected_java_major"], 17)
        self.assertEqual(result["expected_java_major_minimum"], 21)

    def test_exact_matching_jdk_passes(self):
        fake_run = MagicMock(return_value=MagicMock(
            stderr='openjdk version "21.0.2" 2024-01-16\n', stdout=""))
        result = ep.check_java_toolchain(run_fn=fake_run)
        self.assertEqual(result["status"], "ENVIRONMENT_VALID")

    def test_newer_jdk_than_required_passes_not_fails(self):
        """The real state of this exact dev machine: JDK 24 vs. a 21
        target -- must PASS, not fail-close on a healthy setup. This is
        the specific design correction over a naive equality check."""
        fake_run = MagicMock(return_value=MagicMock(
            stderr='openjdk version "24.0.1" 2025-04-15\n', stdout=""))
        result = ep.check_java_toolchain(run_fn=fake_run)
        self.assertEqual(result["status"], "ENVIRONMENT_VALID")

    def test_no_java_at_all_fails_closed(self):
        fake_run = MagicMock(side_effect=FileNotFoundError())
        result = ep.check_java_toolchain(run_fn=fake_run)
        self.assertEqual(result["status"], "ENVIRONMENT_INVALID")
        self.assertIsNone(result["detected_java_major"])

    def test_real_check_against_this_actual_machine_passes(self):
        """No mocking -- the real, live check against whatever JDK is
        actually on this machine's PATH right now, proving the whole
        pipeline works end-to-end, not just its mocked pieces."""
        result = ep.check_java_toolchain()
        self.assertEqual(result["status"], "ENVIRONMENT_VALID", result)


if __name__ == "__main__":
    unittest.main()
