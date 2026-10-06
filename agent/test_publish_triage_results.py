"""
Tests for agent/publish_triage_results.py and a staleness guard for the
committed agent/web/triage-evidence.json. Hermetic: synthetic inputs and
file hashing only -- no Java, no model, no network, no Railway.

Run: python agent/test_publish_triage_results.py
"""

import json
import tempfile
import unittest
from pathlib import Path

import publish_triage_results as pt

REGENERATE = "regenerate: cd agent && python publish_triage_results.py (see its docstring for the Java step)"

WEB_SRC = 'Route("/triage", x)\nRoute("/triage/scenario-b", y)\n'
CATALOGUE = {"scenarios": [
    {"id": "TRIAGE-A-THING", "title": "A title", "status": "LIVE", "risk": "LOW"},
    {"id": "TRIAGE-B-OTHER", "title": "B title", "status": "LIVE", "risk": "LOW"},
]}
JAVA = {
    "A": [{"class": "TriageScenarioAIntegrationTest", "file": "a", "declared_tests": 5, "needs_docker": False}],
    "B": [{"class": "TriageScenarioBIntegrationTest", "file": "b", "declared_tests": 4, "needs_docker": False},
          {"class": "TriageScenarioBPostgresIntegrationTest", "file": "bp", "declared_tests": 2, "needs_docker": True}],
    "D": [{"class": "TriageScenarioDIntegrationTest", "file": "d", "declared_tests": 5, "needs_docker": False}],
}
SUREFIRE = {
    "TriageScenarioAIntegrationTest": {"tests": 5, "failures": 0, "errors": 0, "skipped": 0},
    "TriageScenarioBPostgresIntegrationTest": {"tests": 2, "failures": 0, "errors": 0, "skipped": 2},
    "TriageScenarioDIntegrationTest": {"tests": 5, "failures": 0, "errors": 0, "skipped": 0},
}
ENV_NOTHING = {"java": None, "docker_available": False, "anthropic_key_configured": False}


class ScenarioBuildingTestCase(unittest.TestCase):
    def setUp(self):
        self.scenarios = pt.build_scenarios(CATALOGUE, JAVA, SUREFIRE, WEB_SRC, {"D": "Scenario D: x"})
        self.by_letter = {s["letter"]: s for s in self.scenarios}

    def test_java_only_scenario_is_listed_and_flagged_not_hidden(self):
        d = self.by_letter["D"]
        self.assertFalse(d["in_catalogue"])
        self.assertEqual(d["title"], "Scenario D: x")
        self.assertIn("not listed in triage/scenarios.yaml", d["catalogue_status"])
        self.assertIsNone(d["walkthrough_page"])

    def test_walkthrough_page_only_when_routed(self):
        self.assertEqual(self.by_letter["A"]["walkthrough_page"], "/triage")
        self.assertEqual(self.by_letter["B"]["walkthrough_page"], "/triage/scenario-b")

    def test_missing_surefire_report_is_none_not_zero(self):
        b = self.by_letter["B"]["java_integration_tests"][0]
        self.assertIsNone(b["result"])

    def test_not_run_lists_reasons_honestly(self):
        not_run = pt.build_not_run(self.scenarios, ENV_NOTHING)
        whats = " | ".join(n["what"] for n in not_run)
        self.assertIn("Live reproduce / reset / approve", whats)
        self.assertIn("Diagnosis accuracy score", whats)
        self.assertIn("AI diagnosis", whats)
        self.assertIn("TriageScenarioBIntegrationTest", whats)          # no report
        self.assertIn("TriageScenarioBPostgresIntegrationTest", whats)  # docker skip

    def test_ai_item_dropped_when_key_configured(self):
        env = dict(ENV_NOTHING, anthropic_key_configured=True)
        whats = " | ".join(n["what"] for n in pt.build_not_run(self.scenarios, env))
        self.assertNotIn("AI diagnosis", whats)

    def test_evidence_has_no_score(self):
        out = pt.build_triage_evidence(scenarios=self.scenarios, python_tests={}, environment=ENV_NOTHING,
                                       commit_sha="a" * 40, generated_at="t", working_tree_dirty=False,
                                       inputs={"files": {}})
        self.assertIsNone(out["scoring"])
        json.dumps(out)


class ParsingTestCase(unittest.TestCase):
    def test_count_java_tests_ignores_comments(self):
        src = "/** mentions @Test here */\n// @Test\n@Test void a(){}\n@Test\nvoid b(){}\n"
        self.assertEqual(pt.count_java_tests(src), 2)

    def test_parse_unittest_ok_and_failed(self):
        ok = pt.parse_unittest_output("....\nRan 4 tests in 0.1s\n\nOK (skipped=1)\n")
        self.assertEqual((ok["tests"], ok["passed"], ok["skipped"], ok["ok"]), (4, 3, 1, True))
        bad = pt.parse_unittest_output(
            "FAIL: test_x (mod.Case.test_x)\n...\nRan 3 tests in 0.1s\n\nFAILED (failures=1, errors=1)\n")
        self.assertEqual((bad["passed"], bad["failures"], bad["errors"], bad["ok"]), (1, 1, 1, False))
        self.assertEqual(bad["failing"], ["mod.Case.test_x"])

    def test_parse_unittest_garbage_is_none(self):
        self.assertIsNone(pt.parse_unittest_output("no summary here"))

    def test_scenario_letter(self):
        self.assertEqual(pt.scenario_letter("TRIAGE-C-ADMIN"), "C")
        self.assertIsNone(pt.scenario_letter("OTHER"))

    def test_surefire_parse_reads_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "TEST-com.example.customer.triage.TriageScenarioAIntegrationTest.xml").write_text(
                '<testsuite name="com.example.customer.triage.TriageScenarioAIntegrationTest" '
                'tests="5" errors="0" skipped="1" failures="1"></testsuite>', encoding="utf-8")
            out = pt.parse_surefire(Path(tmp))
        r = out["TriageScenarioAIntegrationTest"]
        self.assertEqual((r["tests"], r["failures"], r["skipped"]), (5, 1, 1))


class TriageEvidenceFreshTestCase(unittest.TestCase):
    """Staleness guard: the committed JSON must describe the current
    catalogue, triage code and triage tests."""

    def setUp(self):
        self.published = json.loads(pt.OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_inputs_unchanged_since_publish(self):
        recorded = self.published["inputs"]["files"]
        current = pt.compute_input_hashes()["files"]
        changed = sorted(k for k in set(recorded) | set(current) if recorded.get(k) != current.get(k))
        self.assertEqual(changed, [], f"triage inputs changed since triage-evidence.json was published "
                                      f"(at {self.published['commit_sha'][:7]}); {REGENERATE}")

    def test_published_file_is_honest_about_scoring(self):
        self.assertIsNone(self.published["scoring"])
        self.assertTrue(self.published["not_run"])

    def test_page_is_routed_and_loads_the_json(self):
        import web_server
        routes = {r.path: r for r in web_server.routes if hasattr(r, "path")}
        self.assertIn("/triage/evidence", routes)
        self.assertIs(routes["/triage/evidence"].endpoint, web_server.triage_evidence_page)
        js = (pt.AGENT_DIR / "web" / "triage-evidence.js").read_text(encoding="utf-8")
        self.assertIn("/triage-evidence.json", js)


if __name__ == "__main__":
    unittest.main()
