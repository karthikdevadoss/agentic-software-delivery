"""
Focused tests for agent/change_risk.py (Testing Architecture V1 §B).

Run: python agent/test_change_risk.py
"""

import unittest

import change_risk as cr


class ClassifyFileTestCase(unittest.TestCase):
    def test_security_config_is_high_cross_module(self):
        c = cr.classify_file("app/src/main/java/com/example/customer/security/SecurityConfig.java")
        self.assertEqual(c.risk, "HIGH")
        self.assertEqual(c.blast_radius, "CROSS_MODULE")

    def test_flyway_migration_is_high_system(self):
        c = cr.classify_file("app/src/main/resources/db/migration/V5__add_thing.sql")
        self.assertEqual(c.risk, "HIGH")
        self.assertEqual(c.blast_radius, "SYSTEM")

    def test_risk_policy_is_critical(self):
        c = cr.classify_file("agent/risk_policy.py")
        self.assertEqual(c.risk, "CRITICAL")

    def test_static_frontend_is_low_local(self):
        c = cr.classify_file("app/src/main/resources/static/index.html")
        self.assertEqual(c.risk, "LOW")
        self.assertEqual(c.blast_radius, "LOCAL")

    def test_business_logic_is_medium_module(self):
        c = cr.classify_file("app/src/main/java/com/example/customer/service/CustomerService.java")
        self.assertEqual(c.risk, "MEDIUM")
        self.assertEqual(c.blast_radius, "MODULE")

    def test_pom_xml_is_high_system(self):
        c = cr.classify_file("app/pom.xml")
        self.assertEqual(c.risk, "HIGH")
        self.assertEqual(c.blast_radius, "SYSTEM")

    def test_ci_workflow_is_high_system(self):
        c = cr.classify_file(".github/workflows/ci.yml")
        self.assertEqual(c.risk, "HIGH")
        self.assertEqual(c.blast_radius, "SYSTEM")

    def test_docs_are_low_local(self):
        c = cr.classify_file("docs/PROJECT_STATE.json".replace(".json", ".md"))
        self.assertEqual(c.risk, "LOW")

    def test_exception_handler_is_cross_module_not_module(self):
        """Regression for the real thing that just happened this session:
        GlobalExceptionHandler affects every controller's error shape, so
        it must never be classified as a merely-local/module change."""
        c = cr.classify_file("app/src/main/java/com/example/customer/exception/GlobalExceptionHandler.java")
        self.assertEqual(c.blast_radius, "CROSS_MODULE")

    def test_kafka_outbox_is_module_not_local(self):
        c = cr.classify_file("app/src/main/java/com/example/customer/outbox/OutboxPublisher.java")
        self.assertEqual(c.blast_radius, "MODULE")

    def test_redis_cache_is_module(self):
        c = cr.classify_file("app/src/main/java/com/example/customer/cache/ContractPlanCacheService.java")
        self.assertEqual(c.blast_radius, "MODULE")

    def test_gitignore_is_low_local_not_unrecognized(self):
        c = cr.classify_file(".gitignore")
        self.assertTrue(c.matched)
        self.assertEqual(c.risk, "LOW")
        self.assertEqual(c.blast_radius, "LOCAL")

    def test_gitattributes_is_deliberately_left_unrecognized(self):
        """Unlike .gitignore, .gitattributes has real runtime effect in
        this project (it controls CRLF/LF normalization and was the fix
        for a real prior incident: app/mvnw's executable bit/shebang
        getting corrupted on checkout) -- it must stay unrecognized here
        so agent/test_impact_analysis.py's explicit FAIL_CLOSED_PATTERNS
        catches it, not be quietly classified as safe."""
        c = cr.classify_file(".gitattributes")
        self.assertFalse(c.matched)

    def test_completely_unrecognized_path_is_not_matched(self):
        c = cr.classify_file("some/brand/new/top-level/thing.xyz")
        self.assertFalse(c.matched)
        self.assertEqual(c.risk, "UNKNOWN")


class ClassifyChangeTestCase(unittest.TestCase):
    def test_empty_change_is_low_local(self):
        c = cr.classify_change([])
        self.assertEqual(c.risk, "LOW")
        self.assertEqual(c.blast_radius, "LOCAL")

    def test_overall_is_the_max_across_files_not_diluted(self):
        """One risky file in a batch of otherwise-safe files must not be
        diluted down by the safe ones."""
        c = cr.classify_change([
            "docs/PROJECT_STATE.md",
            "app/src/main/java/com/example/customer/security/SecurityConfig.java",
            "app/src/main/resources/static/index.html",
        ])
        self.assertEqual(c.risk, "HIGH")
        self.assertEqual(c.blast_radius, "CROSS_MODULE")

    def test_one_unrecognized_path_forces_unknown_overall(self):
        """Known-safe files must never mask an unrecognized/unbounded one
        -- this is the deterministic 'fail closed' signal."""
        c = cr.classify_change([
            "app/src/main/resources/static/index.html",
            "brand/new/unmapped/thing.xyz",
        ])
        self.assertEqual(c.risk, "UNKNOWN")
        self.assertEqual(c.blast_radius, "UNKNOWN")
        self.assertIn("brand/new/unmapped/thing.xyz", c.unrecognized_paths)

    def test_this_sessions_real_diff_classifies_as_expected(self):
        """Dogfooding: the exact file set this session actually committed
        (b908f62) should classify as HIGH/CROSS_MODULE overall (SecurityConfig
        + application.properties), not something weaker."""
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
        c = cr.classify_change(real_diff)
        self.assertEqual(c.risk, "HIGH")
        self.assertEqual(c.blast_radius, "CROSS_MODULE")
        self.assertEqual(c.unrecognized_paths, [])


if __name__ == "__main__":
    unittest.main()
