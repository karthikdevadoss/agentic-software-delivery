"""
Focused tests for agent/test_impact_analysis.py (Testing Architecture V1
§C/§D). Run: python agent/test_test_impact_analysis.py
"""

import unittest

import test_impact_analysis as tia
import tools


class AnalyzeTestCase(unittest.TestCase):
    def test_no_changes_selects_nothing(self):
        selection = tia.analyze([])
        self.assertEqual(selection.java_tests, [])
        self.assertFalse(selection.fail_closed)

    def test_isolated_controller_change_selects_its_own_test_only(self):
        selection = tia.analyze(["app/src/main/java/com/example/customer/controller/CustomerController.java"])
        self.assertEqual(selection.java_tests, ["CustomerControllerIntegrationTest"])
        self.assertFalse(selection.fail_closed)

    def test_security_change_escalates_to_all_java_tests(self):
        selection = tia.analyze(["app/src/main/java/com/example/customer/security/SecurityConfig.java"])
        self.assertEqual(selection.java_tests, [tia.ALL_JAVA_MODULE_TESTS])
        self.assertFalse(selection.fail_closed)

    def test_kafka_change_triggers_mandatory_event_flow_suite(self):
        selection = tia.analyze(["app/src/main/java/com/example/customer/outbox/OutboxPublisher.java"])
        self.assertIn("CustomerPreferenceEventFlowIntegrationTest", selection.java_tests)

    def test_redis_change_triggers_mandatory_cache_suite(self):
        selection = tia.analyze(["app/src/main/java/com/example/customer/cache/ContractPlanCacheService.java"])
        self.assertIn("ContractPlanCacheIntegrationTest", selection.java_tests)

    def test_flyway_migration_triggers_mandatory_postgres_suite(self):
        selection = tia.analyze(["app/src/main/resources/db/migration/V5__x.sql"])
        self.assertIn("PostgresFlywayIntegrationTest", selection.java_tests)

    def test_pom_xml_change_fails_closed(self):
        selection = tia.analyze(["app/pom.xml"])
        self.assertTrue(selection.fail_closed)
        self.assertIn("pom.xml", selection.fail_closed_reason)

    def test_ci_workflow_change_fails_closed(self):
        selection = tia.analyze([".github/workflows/ci.yml"])
        self.assertTrue(selection.fail_closed)

    def test_risk_policy_change_fails_closed(self):
        selection = tia.analyze(["agent/risk_policy.py"])
        self.assertTrue(selection.fail_closed)

    def test_unrecognized_path_fails_closed(self):
        selection = tia.analyze(["brand/new/unmapped/thing.xyz"])
        self.assertTrue(selection.fail_closed)

    def test_docs_only_change_selects_no_java_tests(self):
        selection = tia.analyze(["docs/LESSONS.md"])
        self.assertEqual(selection.java_tests, [])
        self.assertFalse(selection.fail_closed)

    def test_customer_app_frontend_change_now_maps_to_its_real_spec(self):
        """BL-012 (2026-09-20): this used to be an honest gap (skipped, no
        spec existed) -- e2e/customer-app-update-email.spec.js now covers
        this page (added by BL-013 as a real side effect of proving Update
        Email works in a browser), so a change here is no longer silently
        unselected."""
        selection = tia.analyze(["app/src/main/resources/static/index.html"])
        self.assertIn("e2e/customer-app-update-email.spec.js", selection.playwright_specs)
        self.assertFalse(any("no dedicated Playwright spec" in s for s in selection.skipped))

    def test_frontend_change_still_honestly_flagged_when_truly_no_spec_maps_to_it(self):
        """The skip-reason machinery itself is still real, not deleted --
        exercised here via a hypothetical static/** file this repo has no
        mapping for, so the honest-gap behavior stays covered even though
        index.html itself is no longer an example of it."""
        selection = tia.analyze(["app/src/main/resources/static/some-other-page-nothing-covers.html"])
        self.assertEqual(selection.playwright_specs, [])
        self.assertTrue(any("no dedicated Playwright spec" in s for s in selection.skipped))

    def test_agentic_platform_workbench_frontend_maps_to_its_real_spec(self):
        selection = tia.analyze(["agent/web/workbench.html"])
        self.assertIn("e2e/workbench-catalogue.spec.js", selection.playwright_specs)

    def test_python_agent_change_is_flagged_not_silently_dropped(self):
        selection = tia.analyze(["agent/estimation.py"])
        self.assertTrue(any("python-regression" in s for s in selection.skipped))

    def test_this_sessions_real_diff_selects_all_java_tests_via_security_escalation(self):
        """Dogfooding against the exact file set this session actually
        committed (b908f62): SecurityConfig.java's presence must escalate
        to the full Java suite, matching what was actually run and
        verified (75/75) before that commit."""
        real_diff = [
            "app/src/main/java/com/example/customer/exception/GlobalExceptionHandler.java",
            "app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityClient.java",
            "app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityConfig.java",
            "app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityResult.java",
            "app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityService.java",
            "app/src/main/java/com/example/customer/integration/appointment/AppointmentController.java",
            "app/src/main/java/com/example/customer/integration/appointment/demo/DemoAppointmentProviderController.java",
            "app/src/main/java/com/example/customer/security/SecurityConfig.java",
            "app/src/main/resources/application.properties",
            "app/src/main/resources/static/index.html",
            "app/src/test/java/com/example/customer/integration/appointment/AppointmentAvailabilityIntegrationTest.java",
            "app/src/test/java/com/example/customer/integration/appointment/AppointmentControllerIntegrationTest.java",
        ]
        selection = tia.analyze(real_diff)
        self.assertFalse(selection.fail_closed)
        self.assertEqual(selection.java_tests, [tia.ALL_JAVA_MODULE_TESTS])


class FrontendSpecMapDriftTestCase(unittest.TestCase):
    """The frontend path->spec map is hand-maintained, and on 2026-09-25 it had
    already drifted from the real tree: 13 Playwright specs existed on disk and
    only 5 were reachable from any mapped source path. A frontend change
    therefore could not trigger the other 8, which is the same class of silent
    gap as verify_change.py reporting PASSED after running nothing.

    This is a RATCHET, not a clean-slate assertion. KNOWN_UNMAPPED records
    exactly the 8 specs that were already unreachable, by name, so the real
    state is visible rather than hidden. The test fails when a NEW spec appears
    without a mapping -- which is the drift worth catching, because it is the
    one that happens silently during normal work.

    Shrinking KNOWN_UNMAPPED is real work (each entry needs a source path that
    should trigger it). GROWING it to make this test pass is the failure mode
    this test exists to prevent -- add the mapping instead."""

    KNOWN_UNMAPPED = {
        "e2e/ask-codebase.spec.js",
        "e2e/golden-journey.spec.js",
        "e2e/interview-walkthrough.spec.js",
        "e2e/link-integrity.spec.js",
        "e2e/nav-consistency.spec.js",
        "e2e/pdf.spec.js",
        "e2e/profile.spec.js",
        "e2e/workbench-real-acceptance.spec.js",
    }

    def _specs_on_disk(self):
        e2e_dir = tools.REPO_ROOT / "e2e"
        return {f"e2e/{p.name}" for p in sorted(e2e_dir.glob("*.spec.js"))}

    def _specs_reachable(self):
        return {s for specs in tia.FRONTEND_PATH_TO_SPECS.values() for s in specs}

    def test_no_new_playwright_spec_is_unreachable_from_the_tia_map(self):
        unmapped = self._specs_on_disk() - self._specs_reachable()
        new = sorted(unmapped - self.KNOWN_UNMAPPED)
        self.assertEqual(
            new, [],
            f"New Playwright spec(s) exist that no source path maps to: {new}. "
            "A change to the code they cover will not trigger them. Add an entry to "
            "tia.FRONTEND_PATH_TO_SPECS mapping the relevant source path(s) to the spec "
            "-- do NOT add it to KNOWN_UNMAPPED to make this pass.",
        )

    def test_known_unmapped_list_does_not_contain_specs_that_are_now_mapped(self):
        """Keeps the ratchet honest in the other direction: once a spec is
        genuinely wired up, it must be removed from KNOWN_UNMAPPED so the
        remaining debt is always the real remaining debt."""
        stale = sorted(self.KNOWN_UNMAPPED & self._specs_reachable())
        self.assertEqual(
            stale, [],
            f"These specs are now reachable from the TIA map and must be removed "
            f"from KNOWN_UNMAPPED: {stale}",
        )

    def test_every_mapped_spec_actually_exists_on_disk(self):
        missing = sorted(self._specs_reachable() - self._specs_on_disk())
        self.assertEqual(
            missing, [],
            f"TIA maps source paths to spec file(s) that do not exist: {missing}. "
            "The map points at a deleted/renamed spec, so those paths silently select nothing.",
        )

    def test_every_mapped_source_path_still_exists(self):
        missing = sorted(p for p in tia.FRONTEND_PATH_TO_SPECS if not (tools.REPO_ROOT / p).exists())
        self.assertEqual(
            missing, [],
            f"TIA maps source paths that no longer exist: {missing}. Dead map entries "
            "hide the fact that the real file moved and is now unmapped.",
        )


if __name__ == "__main__":
    unittest.main()
