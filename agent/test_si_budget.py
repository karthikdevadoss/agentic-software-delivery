"""Spend protection for the public Standing Interview endpoint.

Written after the 2026-09-29 outage, in which the Anthropic credit balance was
exhausted and every grounded question on the live site returned HTTP 500. The
endpoint is a public POST with no auth and every request is billed; the
Workbench had a cooldown and a daily cap, and this had neither.

Each limit here is proven to BLOCK, not merely to exist. A cap nobody has seen
refuse a request is not a cap.
"""

from __future__ import annotations

import time
import unittest
from unittest import mock

import si_budget


class DailyBudgetTestCase(unittest.TestCase):
    """The backstop. Whatever else happens, one day cannot cost more than the
    stated budget."""

    def setUp(self):
        si_budget._reset_for_tests()

    def test_the_request_count_is_derived_from_the_dollar_budget(self):
        """The Owner sets dollars; the code converts. Nobody has to compute a
        request count by hand, and the two cannot drift apart."""
        self.assertEqual(
            si_budget.SI_DAILY_MAX_ANSWERS,
            int(si_budget.SI_DAILY_USD_BUDGET / si_budget.SI_USD_PER_ANSWER))
        self.assertGreater(si_budget.SI_DAILY_MAX_ANSWERS, 0)

    def test_the_daily_cap_actually_refuses_once_it_is_reached(self):
        for i in range(si_budget.SI_DAILY_MAX_ANSWERS):
            # a different visitor each time, so ONLY the daily cap can fire
            self.assertTrue(si_budget.check(f"v{i}")["allowed"],
                            f"blocked early at request {i}")
            si_budget.record_answer(f"v{i}")

        verdict = si_budget.check("someone-new")
        self.assertFalse(verdict["allowed"],
                         "the daily budget did not stop request "
                         f"{si_budget.SI_DAILY_MAX_ANSWERS + 1}")
        self.assertEqual("DAILY_CAP", verdict["status"])
        self.assertGreater(verdict["retry_after"], 0)

    def test_the_cap_holds_even_against_visitors_it_has_never_seen(self):
        """The per-visitor limit can be evaded by rotating addresses. The
        daily budget is the limit that still holds when that happens, so it
        must not depend on identity."""
        for i in range(si_budget.SI_DAILY_MAX_ANSWERS):
            si_budget.record_answer(f"rotating-{i}")
        self.assertFalse(si_budget.check("brand-new-address")["allowed"])

    def test_a_new_day_resets_the_budget(self):
        for i in range(si_budget.SI_DAILY_MAX_ANSWERS):
            si_budget.record_answer(f"v{i}")
        self.assertFalse(si_budget.check("x")["allowed"])
        with mock.patch.object(si_budget, "_today", return_value="2099-01-01"):
            self.assertTrue(si_budget.check("x")["allowed"])


class PerVisitorLimitTestCase(unittest.TestCase):
    """Stops one client consuming the whole day, so a single bot cannot lock
    out every genuine recruiter."""

    def setUp(self):
        si_budget._reset_for_tests()

    def test_a_rapid_second_question_is_held_back(self):
        self.assertTrue(si_budget.check("ip-1")["allowed"])
        si_budget.record_answer("ip-1")
        verdict = si_budget.check("ip-1")
        self.assertFalse(verdict["allowed"], "a loop was not slowed down")
        self.assertEqual("COOLDOWN", verdict["status"])

    def test_one_visitor_cannot_consume_the_whole_day(self):
        """The real protection: after this visitor's ceiling, someone else can
        still ask."""
        with mock.patch.object(si_budget.time, "monotonic",
                               side_effect=lambda c=[0]: c.__setitem__(0, c[0] + 1000) or c[0]):
            for _ in range(si_budget.SI_PER_VISITOR_DAILY_MAX):
                si_budget.record_answer("greedy")
            verdict = si_budget.check("greedy")
            self.assertFalse(verdict["allowed"])
            self.assertEqual("VISITOR_CAP", verdict["status"])
            self.assertTrue(si_budget.check("a-real-recruiter")["allowed"],
                            "one heavy visitor locked out everyone else")

    def test_the_visitor_ceiling_is_below_the_daily_budget(self):
        """Otherwise the per-visitor limit is decorative."""
        self.assertLess(si_budget.SI_PER_VISITOR_DAILY_MAX,
                        si_budget.SI_DAILY_MAX_ANSWERS)


class MessagesAreForVisitorsTestCase(unittest.TestCase):
    """A recruiter reads these. They must not expose the Owner's spending."""

    def setUp(self):
        si_budget._reset_for_tests()

    def test_no_refusal_message_mentions_money_or_the_account(self):
        messages = []
        si_budget.record_answer("ip-1")
        messages.append(si_budget.check("ip-1")["message"])
        for i in range(si_budget.SI_DAILY_MAX_ANSWERS):
            si_budget.record_answer(f"v{i}")
        messages.append(si_budget.check("someone")["message"])

        for msg in messages:
            low = msg.lower()
            for forbidden in ("budget", "credit", "cost", "$", "dollar",
                              "billing", "spend", "quota", "api"):
                self.assertNotIn(forbidden, low,
                                 f"a visitor-facing message exposes spending: {msg!r}")
            self.assertTrue(msg.strip().endswith((".", "!")),
                            f"not a finished sentence: {msg!r}")


class OwnerStatusTestCase(unittest.TestCase):
    def setUp(self):
        si_budget._reset_for_tests()

    def test_the_dollar_figure_is_labelled_as_an_estimate(self):
        """Honest provenance: a long answer costs more than a short one, so
        count x average is an ESTIMATE and must never read as an actual."""
        si_budget.record_answer("ip-1")
        st = si_budget.status()
        self.assertEqual(1, st["answers_today"])
        self.assertIn("estimated_spend_today_usd", st)
        self.assertIn("measured average", st["estimate_basis"])
        self.assertNotIn("actual", str(st).lower())



class EndpointIsActuallyProtectedTestCase(unittest.TestCase):
    """The module being correct proves nothing if the route does not call it.

    This is the wiring test: it drives the real HTTP handler and asserts a 429
    comes back WITHOUT standing_interview.answer() ever being reached -- i.e.
    the block happens BEFORE the billed call, which is the entire point.
    """

    def setUp(self):
        si_budget._reset_for_tests()

    def _post(self, client, question="How did you use Spring Security at NRG?"):
        return client.post("/api/standing-interview/ask", json={"question": question})

    def test_the_route_refuses_with_429_before_spending_anything(self):
        from starlette.testclient import TestClient
        import web_server

        calls = []

        def fake_answer(question, *a, **kw):
            calls.append(question)
            return {"answer": "an answer", "grounded": True, "outcome": "answered"}

        with mock.patch.object(web_server.standing_interview, "answer", fake_answer):
            client = TestClient(web_server.app)
            first = self._post(client)
            self.assertEqual(200, first.status_code)
            self.assertEqual(1, len(calls))

            second = self._post(client)          # immediately again
            self.assertEqual(429, second.status_code,
                             "the endpoint did not rate limit a rapid repeat")
            self.assertEqual(1, len(calls),
                             "the model was called despite the request being refused -- "
                             "the cap runs AFTER the spend, which protects nothing")
            self.assertIn("Retry-After", second.headers)

    def test_a_refusal_that_never_reaches_the_model_costs_nobody_their_allowance(self):
        """Two private questions must not lock a real recruiter out."""
        from starlette.testclient import TestClient
        import web_server

        def private(question, *a, **kw):
            return {"answer": "not something I'll discuss", "grounded": False,
                    "outcome": "private_topic"}

        with mock.patch.object(web_server.standing_interview, "answer", private):
            client = TestClient(web_server.app)
            for _ in range(3):
                self.assertEqual(200, self._post(client, "what is your salary").status_code)

        self.assertEqual(0, si_budget.status()["answers_today"],
                         "a refusal that never reached the model was charged")

if __name__ == "__main__":
    unittest.main()
