"""Tests for the release-health runner's three-outcome verdict.

WHY THIS FILE EXISTS. The verdict logic decides whether this repository is allowed
to call a branch green, and it was originally proven only by a throwaway script in
a scratch directory. That is proof that evaporates: the next person to touch
_classify_playwright_failures has nothing telling them what the three cases are
supposed to do.

The load-bearing property is not "UNVERIFIED works". It is that UNVERIFIED cannot
be reached by accident — a failure outside the declared register, or one whose
prerequisite is actually present, must keep the verdict RED. Those are the two
assertions that stop a convenient excuse from becoming a green build.

Hermetic: every case is pure Python over fabricated failure lines and an injected
prerequisite checker. No browser, no server, no model.
"""

from __future__ import annotations

import unittest

import release_health as rh


def verdict(attributable, real) -> str:
    """The same three-way decision main() makes, over the classifier's output.

    Deliberately re-expressed here rather than imported: main() interleaves it with
    printing and JSON writing, and extracting it just to test it would change
    production code to suit a test. The rule is two lines long and the risk of the
    two drifting is covered by test_the_runner_still_has_all_three_outcomes below,
    which asserts the real source still contains each verdict string.
    """
    if attributable and not real:
        return "UNVERIFIED"
    return "RED" if real else "GREEN"


# Real failure lines, in Playwright's list-reporter shape, with the Windows
# backslash separator the runner actually sees.
USAGE_FAIL = (r"1) [chromium] > e2e\usage.spec.js:25:3 > "
              r"historical list shows real sessions and Session History panel")
USAGE_FAIL_2 = (r"2) [chromium] > e2e\usage.spec.js:31:3 > "
                r"known-cost Workbench run: tokens and actual cost are visible")
PROFILE_FAIL = (r"3) [chromium] > e2e\profile.spec.js:59:3 > "
                r"the verified-run page clearly identifies itself")
CUSTOMER_APP_FAIL = (r"4) [chromium] > e2e\customer-app-frontend.spec.js:48:3 > "
                     r"an anonymous visitor sees only the login gate")
UNREGISTERED_FAIL = (r"5) [chromium] > e2e\home.spec.js:12:3 > "
                     r"home renders its own real identity")


class _FakeHave:
    """Injects prerequisite answers so a case does not depend on what this machine
    happens to have installed -- the exact trap that made four Python modules look
    hermetic because this laptop held a JDK and a ledger URL."""

    def __init__(self, absent=(), present=()):
        self.absent, self.present = set(absent), set(present)

    def __call__(self, what):
        if what in self.absent:
            return False, f"{what} is absent (injected)"
        if what in self.present:
            return True, ""
        return True, ""


class ClassifierTestCase(unittest.TestCase):
    def setUp(self):
        self._real_have = rh._have
        self.addCleanup(lambda: setattr(rh, "_have", self._real_have))

    def test_only_environment_failures_with_absent_prerequisites_is_unverified(self):
        rh._have = _FakeHave(absent={"small_session_history", "verified_run_in_ledger"})
        a, u, notes = rh._classify_playwright_failures(
            [USAGE_FAIL, USAGE_FAIL_2, PROFILE_FAIL])
        self.assertEqual(len(a), 3)
        self.assertEqual(u, [])
        self.assertEqual(verdict(a, u), "UNVERIFIED")
        self.assertTrue(notes, "an attributable failure must carry its reason")

    def test_one_unregistered_failure_forces_red(self):
        """The guardrail. A failure the register knows nothing about must never be
        swept into an environment excuse."""
        rh._have = _FakeHave(absent={"small_session_history", "verified_run_in_ledger"})
        a, u, _ = rh._classify_playwright_failures(
            [USAGE_FAIL, USAGE_FAIL_2, PROFILE_FAIL, UNREGISTERED_FAIL])
        self.assertIn(UNREGISTERED_FAIL, u)
        self.assertEqual(verdict(a, u), "RED")

    def test_a_present_prerequisite_makes_its_failure_real_again(self):
        """The other guardrail, and the one a real observation produced: with the
        Customer App running, the suite went from 5 failures to 3. So a registered
        spec whose prerequisite IS present has genuinely failed, and the register
        must stop excusing it."""
        rh._have = _FakeHave(present={"customer_app"})
        a, u, _ = rh._classify_playwright_failures([CUSTOMER_APP_FAIL])
        self.assertEqual(a, [], "a present prerequisite must excuse nothing")
        self.assertEqual(u, [CUSTOMER_APP_FAIL])
        self.assertEqual(verdict(a, u), "RED")

    def test_no_failures_at_all_is_green(self):
        a, u, _ = rh._classify_playwright_failures([])
        self.assertEqual(verdict(a, u), "GREEN")

    def test_forward_slash_and_backslash_spec_paths_both_match(self):
        """Playwright prints Windows paths with backslashes and POSIX paths with
        forward slashes. A register keyed on one and matched against the other
        would silently attribute nothing -- which fails safe, but would make the
        whole mechanism dead code on one platform."""
        rh._have = _FakeHave(absent={"small_session_history"})
        posix = "1) [chromium] > e2e/usage.spec.js:25:3 > historical list"
        a, u, _ = rh._classify_playwright_failures([posix])
        self.assertEqual(len(a), 1, "a forward-slash spec path must still match")
        self.assertEqual(u, [])

    def test_an_unknown_prerequisite_never_becomes_an_excuse(self):
        """_have returns (True, "") for a name it does not recognise. That has to
        mean 'treated as present, so the failure is real' -- never 'unknown, so
        assume absent and excuse it'."""
        rh._have = self._real_have
        ok, _ = rh._have("something_nobody_declared")
        self.assertTrue(ok, "an unrecognised prerequisite must read as PRESENT")


class RegisterIntegrityTestCase(unittest.TestCase):
    """The register is hand-maintained, so the ways it can rot are asserted."""

    def test_every_registered_spec_exists_on_disk(self):
        from pathlib import Path
        repo = Path(rh.__file__).resolve().parent.parent
        missing = [s for s in rh.ENVIRONMENT_DEPENDENT_SPECS
                   if not (repo / s).exists()]
        self.assertEqual(
            missing, [],
            f"the register names spec(s) that no longer exist: {missing}. A stale "
            f"entry is an excuse waiting for a spec that will never fail.")

    def _runner_source(self):
        from pathlib import Path
        return Path(rh.__file__).read_text(encoding="utf-8")

    def test_every_entry_names_a_prerequisite_the_checker_understands(self):
        source = self._runner_source()
        for spec, meta in sorted(rh.ENVIRONMENT_DEPENDENT_SPECS.items()):
            with self.subTest(spec=spec):
                need = meta["needs"]
                # An unrecognised name falls through to (True, "") -- present --
                # so the entry would never fire and would look like coverage that
                # is not there.
                self.assertIn(
                    f'what == "{need}"', source,
                    f"{spec} declares prerequisite {need!r}, which _have() does not "
                    f"check -- the entry can never fire.")

    def test_every_entry_gives_a_real_reason(self):
        for spec, meta in sorted(rh.ENVIRONMENT_DEPENDENT_SPECS.items()):
            with self.subTest(spec=spec):
                self.assertGreaterEqual(
                    len(meta["why"].split()), 12,
                    f"{spec}'s reason is too short to be checkable: {meta['why']!r}")

    def test_the_runner_still_has_all_three_outcomes(self):
        """Guards against someone simplifying the verdict back to two states and
        leaving this file's `verdict()` helper describing logic that no longer
        exists."""
        source = self._runner_source()
        for state in ("GREEN", "RED", "UNVERIFIED"):
            self.assertIn(f'"{state}"', source)
        self.assertIn(
            'return 0 if verdict == "GREEN" else 1', source,
            "UNVERIFIED must keep exiting non-zero; only GREEN may exit 0.")


class GateDeclarationTestCase(unittest.TestCase):
    def test_no_gate_is_a_paid_suite(self):
        """The runner's central promise. There must be no path from it to a
        provider, and this asserts the declaration rather than trusting the
        docstring."""
        import select_tests
        for gate in rh.GATES:
            with self.subTest(gate=gate["id"]):
                meta = select_tests.SUITES.get(gate["id"])
                if meta is not None:
                    self.assertEqual(meta["cost_class"], "free")

    def test_the_paid_suite_is_listed_as_never_release_health(self):
        self.assertIn("si-answer-quality-paid", rh.NOT_RELEASE_HEALTH)

    def test_every_gate_declares_blocking_or_monitor(self):
        for gate in rh.GATES:
            with self.subTest(gate=gate["id"]):
                self.assertIn(gate["requirement"], ("blocking", "monitor"))

    def test_every_gate_says_why_it_exists(self):
        for gate in rh.GATES:
            with self.subTest(gate=gate["id"]):
                self.assertGreaterEqual(len(gate["why"].split()), 6)

    def test_every_never_release_health_entry_gives_a_real_reason(self):
        for name, why in sorted(rh.NOT_RELEASE_HEALTH.items()):
            with self.subTest(entry=name):
                self.assertGreaterEqual(
                    len(why.split()), 12,
                    f"{name}'s exclusion reason is too short to be checkable")


class FailureLineRecoveryTestCase(unittest.TestCase):
    """_extract_failure_lines exists because this runner's own first full run lost
    every Playwright failure name to a 1500-character output tail."""

    def test_it_recovers_playwrights_numbered_failure_lines(self):
        sample = (
            "ok 1 [chromium] > a.spec.js:1:1 > works (1s)\n"
            "  1) [chromium] > e2e/usage.spec.js:12:3 > shows the ledger\n"
            "    Error: expected 3 got 0\n"
            "  2 failed\n"
            "  358 passed\n"
        )
        lines = rh._extract_failure_lines(sample)
        self.assertTrue(any("usage.spec.js:12:3" in ln for ln in lines),
                        "the line that NAMES the failing spec must be recovered")

    def test_it_recovers_unittest_and_maven_shapes_too(self):
        sample = (
            "FAIL: test_something (mod.Case.test_something)\n"
            "Tests run: 12, Failures: 1, Errors: 0\n"
            "AssertionError: 3 != 4\n"
        )
        lines = rh._extract_failure_lines(sample)
        self.assertGreaterEqual(len(lines), 3)

    def test_a_clean_log_recovers_nothing(self):
        self.assertEqual(rh._extract_failure_lines("ok 1 all good\n  5 passed\n"), [])

    def test_it_caps_a_pathological_log_and_says_so(self):
        sample = "\n".join(f"  {i}) [chromium] > spec{i}.js:1:1 > case" for i in range(200))
        lines = rh._extract_failure_lines(sample)
        self.assertLessEqual(len(lines), 41)
        self.assertTrue(any("not shown here" in ln for ln in lines),
                        "a truncated list must say it was truncated")


if __name__ == "__main__":
    unittest.main()
