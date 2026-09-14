"""
Focused tests for agent/test_impact_analysis.py (Testing Architecture V1
§C/§D). Run: python agent/test_test_impact_analysis.py
"""

import unittest

import test_impact_analysis as tia


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

    def test_frontend_change_with_no_dedicated_customer_app_spec_is_honestly_flagged(self):
        selection = tia.analyze(["app/src/main/resources/static/index.html"])
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


if __name__ == "__main__":
    unittest.main()
