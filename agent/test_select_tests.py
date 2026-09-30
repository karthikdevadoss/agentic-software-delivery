"""Tests for the cost-aware selector and the fail-closed paid-test guard.

These assert on the real OUTPUT of agent/select_tests.py and
agent/paid_test_guard.py, not on a description of what they are supposed to do.
The distinction matters here more than usual: the property being protected is
"this change cannot spend money", and a comment saying so has no effect at
runtime.

OBSERVED FAILING, as CLAUDE.md requires of every new guard. Each of the three
load-bearing cases below was run against a deliberately seeded mutation and
watched fail for the intended reason before being recorded as passing. The real
output is in docs/TESTING.md's RED->GREEN section rather than paraphrased here.

Zero model calls. Every case is pure Python over an injected env dict or a
literal path list.
"""

from __future__ import annotations

import unittest

import paid_test_guard as guard
import select_tests as sel


class TheRuleThatIsNotNegotiable(unittest.TestCase):
    """A CSS/image/visual-HTML change must never select a paid suite.

    Seeded mutation used to prove this fails: adding "si-answer-quality-paid" to
    CLASS_TO_SUITES["CSS_VISUAL"]. Observed FAIL on all four cases.
    """

    CSS_ONLY = [
        ["agent/web/style.css"],
        ["agent/web/style.css", "agent/web/triage.css", "agent/web/showcase.css"],
        ["agent/web/style.css", "agent/web/favicon.ico"],
        ["agent/web/dashboard.css"],
    ]

    def test_no_css_only_change_selects_a_paid_suite(self):
        for paths in self.CSS_ONLY:
            with self.subTest(paths=paths):
                result = sel.select(paths)
                paid = [s["suite"] for s in result["included_suites"]
                        if s["cost_class"] == "paid"]
                self.assertEqual(
                    paid, [],
                    f"a visual-only change selected paid suite(s) {paid}. This is the "
                    f"one rule in the selector that has no acceptable exception.",
                )

    def test_css_only_change_reports_zero_expected_paid_calls_and_zero_budget(self):
        result = sel.select(["agent/web/style.css"])
        self.assertEqual(result["expected_paid_model_calls"], 0)
        self.assertEqual(result["max_paid_budget"], 0.00)

    def test_static_html_copy_change_also_selects_no_paid_suite(self):
        """Recruiter copy is the change the Owner makes most often. It reaches no
        model either."""
        result = sel.select(["agent/web/home.html"])
        self.assertEqual(result["change_class"], "STATIC_HTML_COPY")
        self.assertEqual(
            [s["suite"] for s in result["included_suites"] if s["cost_class"] == "paid"],
            [],
        )


class EveryRequiredChangeClassIsReachable(unittest.TestCase):
    """A class nothing can match is a class that silently never applies -- the
    same defect shape as a Playwright spec no source path maps to. Each of the
    eight required classes gets a real path that must land in it."""

    EXPECTED = {
        "CSS_VISUAL": "agent/web/style.css",
        "STATIC_HTML_COPY": "agent/web/home.html",
        "FRONTEND_JS": "agent/web/workbench.js",
        "PYTHON_APP_LOGIC": "agent/session_history.py",
        "JAVA_BACKEND": "app/src/main/java/com/example/customer/CustomerController.java",
        "PROMPT_MODEL_AGENT": "agent/standing_interview.py",
        "CI_TESTING_INFRA": ".github/workflows/ci.yml",
        "SECURITY_WRITE_AUTHORITY": "agent/write_tools.py",
    }

    def test_each_of_the_eight_classes_is_reached_by_a_real_path(self):
        for expected_class, path in sorted(self.EXPECTED.items()):
            with self.subTest(expected_class=expected_class):
                got = sel.classify_paths([path])["change_class"]
                self.assertEqual(
                    got, expected_class,
                    f"{path} classified as {got}, expected {expected_class}",
                )

    def test_exactly_one_class_needs_paid_evaluation(self):
        """If a second class ever wants paid evaluation that is a real decision
        to make deliberately, not something to discover from a bill."""
        paid_classes = [name for name, _rx, _why, paid in sel.CHANGE_CLASS_RULES if paid]
        self.assertEqual(paid_classes, ["PROMPT_MODEL_AGENT"])


class MixedChangesTakeTheRiskiestClass(unittest.TestCase):
    """A commit that touches a stylesheet AND a prompt is a prompt change that
    happens to include a stylesheet. Averaging would let the cheap half hide the
    expensive half -- which is exactly how a CSS tweak would end up shipping an
    unevaluated prompt change."""

    def test_css_plus_prompt_is_classified_as_the_prompt_change(self):
        result = sel.select(["agent/web/style.css", "agent/standing_interview.py"])
        self.assertEqual(result["change_class"], "PROMPT_MODEL_AGENT")

    def test_css_plus_security_boundary_is_classified_as_the_security_change(self):
        result = sel.select(["agent/web/style.css", "agent/write_tools.py"])
        self.assertEqual(result["change_class"], "SECURITY_WRITE_AUTHORITY")

    def test_the_reason_names_the_competing_classes_not_just_the_winner(self):
        result = sel.select(["agent/web/style.css", "agent/standing_interview.py"])
        self.assertIn("CSS_VISUAL", result["change_class_reason"])


class FailingClosedMeansBreadthNotSpend(unittest.TestCase):
    """The distinction this asserts is the whole reason to write it down: an
    unbounded change runs MORE FREE TESTS. It never starts spending because the
    selector was unsure."""

    def test_an_unrecognized_path_is_unbounded(self):
        result = sel.select(["some/place/nobody/mapped.xyz"])
        self.assertEqual(result["change_class"], "UNBOUNDED")

    def test_an_unbounded_change_still_expects_zero_paid_calls(self):
        result = sel.select(["some/place/nobody/mapped.xyz"])
        self.assertEqual(result["expected_paid_model_calls"], 0)
        self.assertEqual(
            [s["suite"] for s in result["included_suites"] if s["cost_class"] == "paid"],
            [],
            "failing closed must mean more free tests, never more spend",
        )

    def test_an_unbounded_change_selects_the_full_deterministic_set(self):
        included = {s["suite"] for s in sel.select(["some/unmapped.xyz"])["included_suites"]}
        for expected in ("java-customer-app", "java-microservices", "real-topology",
                         "playwright-functional", "rag-mcp-evals"):
            self.assertIn(expected, included)

    def test_a_tia_fail_closed_path_overrides_a_cheap_looking_class(self):
        """.github/workflows/ci.yml matches CI_TESTING_INFRA by name AND makes
        TIA fail closed. The override must win, and it must be visible in the
        reason rather than only in the suite list."""
        result = sel.select([".github/workflows/ci.yml"])
        self.assertTrue(result["tia_fail_closed"])
        self.assertEqual(result["change_class"], "UNBOUNDED")
        self.assertIn("failed closed", result["change_class_reason"])


class PaidGuardIsDefaultDeny(unittest.TestCase):
    """Seeded mutation used to prove these fail: changing the guard's `and` to an
    `or` so either condition alone authorizes. Observed FAIL on
    test_the_flag_alone_is_not_enough and test_a_positive_budget_alone_is_not_enough.
    """

    SUITE = "si-answer-quality-paid"

    def test_a_bare_environment_refuses(self):
        with self.assertRaises(guard.PaidTestsNotAuthorized):
            guard.require_paid_tests_allowed(self.SUITE, env={})

    def test_the_flag_alone_is_not_enough(self):
        with self.assertRaises(guard.PaidTestsNotAuthorized):
            guard.require_paid_tests_allowed(self.SUITE, env={"ALLOW_PAID_TESTS": "1"})

    def test_a_positive_budget_alone_is_not_enough(self):
        with self.assertRaises(guard.PaidTestsNotAuthorized):
            guard.require_paid_tests_allowed(
                self.SUITE, env={"PAID_TEST_BUDGET_USD": "5.00"})

    def test_a_zero_budget_refuses_even_with_the_flag(self):
        with self.assertRaises(guard.PaidTestsNotAuthorized):
            guard.require_paid_tests_allowed(
                self.SUITE,
                env={"ALLOW_PAID_TESTS": "1", "PAID_TEST_BUDGET_USD": "0"})

    def test_a_malformed_budget_refuses_rather_than_defaulting(self):
        """An unparseable ceiling is an unknown ceiling. CLAUDE.md: unknown must
        never silently become a number."""
        with self.assertRaises(guard.PaidTestsNotAuthorized):
            guard.require_paid_tests_allowed(
                self.SUITE,
                env={"ALLOW_PAID_TESTS": "1", "PAID_TEST_BUDGET_USD": "abc"})

    def test_a_negative_budget_refuses(self):
        with self.assertRaises(guard.PaidTestsNotAuthorized):
            guard.require_paid_tests_allowed(
                self.SUITE,
                env={"ALLOW_PAID_TESTS": "1", "PAID_TEST_BUDGET_USD": "-1"})

    def test_an_unrecognised_flag_value_refuses(self):
        for value in ("0", "", "false", "no", "off", "maybe", "TRUE ish"):
            with self.subTest(value=value):
                with self.assertRaises(guard.PaidTestsNotAuthorized):
                    guard.require_paid_tests_allowed(
                        self.SUITE,
                        env={"ALLOW_PAID_TESTS": value, "PAID_TEST_BUDGET_USD": "5"})

    def test_both_conditions_together_authorize_and_return_the_budget(self):
        """The allow path has to work, or the guard is just a wall and nobody
        would trust the refusals to be about authorization rather than breakage.
        Returning the budget makes no provider call."""
        budget = guard.require_paid_tests_allowed(
            self.SUITE,
            env={"ALLOW_PAID_TESTS": "yes", "PAID_TEST_BUDGET_USD": "5.00"})
        self.assertEqual(budget, 5.00)

    def test_the_refusal_message_names_both_conditions_not_only_the_missing_one(self):
        """Someone who set the flag and forgot the budget should not have to
        guess; and someone reading the message later should see the whole
        contract, not half of it."""
        try:
            guard.require_paid_tests_allowed(self.SUITE, env={"ALLOW_PAID_TESTS": "1"})
        except guard.PaidTestsNotAuthorized as exc:
            message = str(exc)
        else:
            self.fail("expected a refusal")
        self.assertIn("ALLOW_PAID_TESTS", message)
        self.assertIn("PAID_TEST_BUDGET_USD", message)
        self.assertIn("No model API call was made.", message)


class SelectorNeverAuthorizesItself(unittest.TestCase):
    """Two separate mechanisms on purpose. The selector says a paid suite is
    NEEDED; only the guard says it is ALLOWED. A selector that could do both
    would be one bug away from doing both at once."""

    def test_selector_reports_the_guards_verdict_rather_than_forming_its_own(self):
        result = sel.select(["agent/standing_interview.py"])
        self.assertIn("paid_tests_authorized", result)
        self.assertFalse(
            result["paid_tests_authorized"],
            "Sprint 17 must never run with paid tests authorized",
        )
        self.assertTrue(result["paid_guard_refusal_reasons"])

    def test_a_needed_paid_suite_is_marked_required_before_deploy_not_run_now(self):
        result = sel.select(["agent/standing_interview.py"])
        paid = [s for s in result["included_suites"] if s["cost_class"] == "paid"]
        self.assertTrue(paid, "a prompt change must still SAY a paid evaluation is needed")
        for s in paid:
            self.assertEqual(s["disposition"], "REQUIRED_BEFORE_DEPLOY")


class EmptyAndCheapFloor(unittest.TestCase):
    def test_no_changed_files_is_its_own_class(self):
        self.assertEqual(sel.select([])["change_class"], "EMPTY")

    def test_every_non_empty_change_runs_the_cheap_floor(self):
        for paths in (["agent/web/style.css"], ["agent/write_tools.py"], ["x.unknown"]):
            with self.subTest(paths=paths):
                included = {s["suite"] for s in sel.select(paths)["included_suites"]}
                for floor in sel.ALWAYS:
                    self.assertIn(floor, included)

    def test_the_quality_monitor_suite_is_never_release_blocking(self):
        self.assertFalse(sel.SUITES["python-quality-monitors"]["release_blocking"])

    def test_every_suite_declares_a_cost_class_of_exactly_free_or_paid(self):
        for name, meta in sel.SUITES.items():
            with self.subTest(suite=name):
                self.assertIn(meta["cost_class"], ("free", "paid"))

    def test_every_suite_carries_at_least_one_of_the_five_taxonomy_tags(self):
        allowed = {"quick", "full", "visual", "live", "paid"}
        for name, meta in sel.SUITES.items():
            with self.subTest(suite=name):
                self.assertTrue(set(meta["tags"]) <= allowed,
                                f"{name} has tags outside the taxonomy: {meta['tags']}")
                self.assertTrue(meta["tags"], f"{name} has no tag")

    def test_a_paid_cost_class_always_carries_the_paid_tag(self):
        """Otherwise a suite could be paid in behaviour and free-looking in the
        matrix, which is the drift that makes a cost taxonomy worthless."""
        for name, meta in sel.SUITES.items():
            if meta["cost_class"] == "paid":
                with self.subTest(suite=name):
                    self.assertIn("paid", meta["tags"])


if __name__ == "__main__":
    unittest.main()
