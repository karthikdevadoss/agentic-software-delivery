"""
Real, end-to-end tests for agent/backend_execution.py's Maven mechanics
-- ACT-008 foundation. A real, disposable local git repository (seeded
with a real COPY of this project's actual app/ Maven module, not a
fake/minimal fixture) stands in for "the real public GitHub repo",
exactly mirroring test_demo_execution.py's RealLocalGitWorkflowTestCase
convention -- run_maven_compile/run_maven_targeted_tests are exercised
against a genuine `mvnw` subprocess in a genuine isolated clone, not
mocked.

These tests are real Maven builds and take real wall-clock time
(observed ~15-30s each this session) -- deliberately not mocked, since
the entire point of this module is proving a real compile/test actually
runs before anything is ever deployed.

Run: python -m unittest test_backend_execution -v   (from agent/)
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import backend_catalogue as bc
import backend_execution as be
import demo_execution as de

REAL_APP_DIR = Path(__file__).resolve().parent.parent / "app"


def _git(args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return result.stdout + result.stderr


def _copy_real_app_module(dest_app_dir: Path):
    """Copies the REAL app/ Maven module (pom.xml, mvnw*, .mvn, src) into
    dest_app_dir, excluding target/ (build output, not source) and any
    .git directory -- a real, current, buildable module, not a synthetic
    fixture that could silently drift from the actual project."""
    shutil.copytree(
        REAL_APP_DIR, dest_app_dir,
        ignore=shutil.ignore_patterns("target", ".git"),
    )


@unittest.skipUnless(REAL_APP_DIR.is_dir(), "real app/ module not found in this checkout")
class RealMavenInIsolatedWorkspaceTestCase(unittest.TestCase):
    """Proves backend_execution's Maven mechanics work against a genuine
    isolated clone of a real Maven module -- the exact same
    demo_execution.create_isolated_workspace() mechanism the live
    ACT-008 pipeline uses, seeded with a real copy of this project's own
    app/ module rather than a synthetic fixture."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_root = tempfile.mkdtemp(prefix="test-backend-origin-")
        cls.origin = Path(cls.tmp_root) / "origin"
        cls.origin.mkdir()
        _git(["init", "-q", "-b", "master"], cls.origin)
        _git(["config", "user.email", "test@example.com"], cls.origin)
        _git(["config", "user.name", "Test"], cls.origin)
        _copy_real_app_module(cls.origin / "app")
        _git(["add", "-A"], cls.origin)
        _git(["commit", "-q", "-m", "initial (real app/ module copy)"], cls.origin)

        cls.workspace, ok, out = de.create_isolated_workspace("backend-test", repo_url=str(cls.origin))
        if not ok:
            raise RuntimeError(f"isolated workspace clone failed: {out}")

    @classmethod
    def tearDownClass(cls):
        de.cleanup_workspace(cls.workspace)
        shutil.rmtree(cls.tmp_root, ignore_errors=True)

    def test_isolated_clone_contains_the_real_backend_target_file(self):
        target_path = self.workspace / bc.BACKEND_TARGET_FILE
        self.assertTrue(target_path.is_file())
        content = target_path.read_text(encoding="utf-8")
        self.assertEqual(bc.extract_current_value(content, "customer_not_found_message"), "Customer not found")

    def test_a_real_mvnw_compile_succeeds_in_the_isolated_workspace(self):
        ok, out = be.run_maven_compile(self.workspace / "app")
        self.assertTrue(ok, out[-2000:])

    def test_real_targeted_tests_pass_before_any_source_change(self):
        ok, out = be.run_maven_targeted_tests(self.workspace / "app")
        self.assertTrue(ok, out[-2000:])

    def test_a_legitimate_value_change_via_the_catalogue_keeps_all_real_tests_green(self):
        """A well-formed catalogue change to the message's value is
        supposed to be safe by construction: CustomerControllerIntegrationTest
        asserts on the id suffix and the JSON shape (never the message
        text itself), and CustomerServiceTest reads
        CustomerService.CUSTOMER_NOT_FOUND_MESSAGE dynamically rather
        than hard-coding an expected literal — so changing the value
        through this catalogue must NOT spuriously break either. This is
        the actual acceptance bar for "this operation is genuinely
        safe", proven with a real Maven run, not asserted from reading
        the source. Applied to a throwaway SECOND clone so the other
        tests in this class are never affected."""
        workspace2, ok, out = de.create_isolated_workspace("backend-test-changed", repo_url=str(self.origin))
        self.addCleanup(lambda: de.cleanup_workspace(workspace2))
        self.assertTrue(ok, out)

        target_path = workspace2 / bc.BACKEND_TARGET_FILE
        content = target_path.read_text(encoding="utf-8")
        new_content = bc.apply_operation(content, "customer_not_found_message", "Customer record not found (TEST PROBE)")
        bc.compute_single_line_diff(content, new_content)  # must not raise (diff purity)
        target_path.write_text(new_content, encoding="utf-8")

        compile_ok, compile_out = be.run_maven_compile(workspace2 / "app")
        self.assertTrue(compile_ok, compile_out[-2000:])
        test_ok, test_out = be.run_maven_targeted_tests(workspace2 / "app")
        self.assertTrue(test_ok, test_out[-2000:])

    def test_real_maven_compile_catches_syntactically_broken_java(self):
        """Proves the compile step is a genuine gate, not a rubber
        stamp: directly corrupting the target file's Java syntax (never
        something apply_operation's own regex substitution could
        produce, since its replacement is confined inside one already-
        matched string literal) must make a real `mvnw compile` fail.
        Applied to a throwaway THIRD clone."""
        workspace3, ok, out = de.create_isolated_workspace("backend-test-syntax-broken", repo_url=str(self.origin))
        self.addCleanup(lambda: de.cleanup_workspace(workspace3))
        self.assertTrue(ok, out)

        target_path = workspace3 / bc.BACKEND_TARGET_FILE
        content = target_path.read_text(encoding="utf-8")
        corrupted = content.replace("public class CustomerService {", "public class CustomerService { this is not valid java (((")
        target_path.write_text(corrupted, encoding="utf-8")

        compile_ok, compile_out = be.run_maven_compile(workspace3 / "app")
        self.assertFalse(compile_ok, "a genuinely broken .java file must fail a real mvnw compile")


class ProductionFieldAssertionTestCase(unittest.TestCase):
    """assert_production_field and the API-response extractor -- fast,
    fully mocked (no real network), covering the JSON parsing/matching
    contract in isolation from the real-Maven tests above."""

    def test_matches_when_live_value_equals_expected(self):
        def fetch(url):
            return 404, '{"error": "Customer record not found: 999999"}'

        status, body, live_value, matched = be.assert_production_field(
            fetch, "http://x/customers/999999",
            lambda b: bc.extract_value_from_not_found_api_response(b, "customer_not_found_message"),
            "Customer record not found",
        )
        self.assertEqual(status, 404)
        self.assertEqual(live_value, "Customer record not found")
        self.assertTrue(matched)

    def test_does_not_match_when_live_value_differs(self):
        def fetch(url):
            return 404, '{"error": "Customer not found: 999999"}'

        _, _, live_value, matched = be.assert_production_field(
            fetch, "http://x/customers/999999",
            lambda b: bc.extract_value_from_not_found_api_response(b, "customer_not_found_message"),
            "Customer record not found",
        )
        self.assertEqual(live_value, "Customer not found")
        self.assertFalse(matched)

    def test_unparseable_body_never_reports_a_false_match(self):
        def fetch(url):
            return 500, "not json at all"

        _, _, live_value, matched = be.assert_production_field(
            fetch, "http://x/customers/999999",
            lambda b: bc.extract_value_from_not_found_api_response(b, "customer_not_found_message"),
            "Customer record not found",
        )
        self.assertIsNone(live_value)
        self.assertFalse(matched)

    def test_extract_value_from_not_found_api_response_parses_the_real_shape(self):
        self.assertEqual(
            bc.extract_value_from_not_found_api_response('{"error": "Customer not found: 42"}', "customer_not_found_message"),
            "Customer not found",
        )

    def test_extract_value_from_not_found_api_response_honest_none_on_bad_shape(self):
        self.assertIsNone(bc.extract_value_from_not_found_api_response("{}", "customer_not_found_message"))
        self.assertIsNone(bc.extract_value_from_not_found_api_response("not json", "customer_not_found_message"))
        self.assertIsNone(bc.extract_value_from_not_found_api_response('{"error": "no colon here"}', "customer_not_found_message"))


if __name__ == "__main__":
    unittest.main()
