"""Hermetic tests for usage_intel core: normalization, provenance, pricing,
dedupe, nesting, retries, streaming, attribution, date ranges, outcomes.

Expected financial values are computed BY HAND in the comments from the
verified list prices (docs/AI_USAGE_SOURCES.md), not by calling the code
under test.
"""
import unittest
from datetime import date

from usage_intel import analytics, events, outcomes, pricing
from usage_intel.events import RequestType, Source, UsageEvent

TS = "2026-11-28T10:00:00.000Z"


def anth(n, usage, model="claude-sonnet-5-5", **kw):
    ev = events.from_anthropic(usage, response_model=model, request_id=f"req_{n}", timestamp=kw.pop("timestamp", TS), **kw)
    ev.success = kw.get("success", True) if "success" not in kw else ev.success
    return pricing.estimate(ev)


class NormalizationTests(unittest.TestCase):
    def test_anthropic_input_excludes_cache(self):
        ev = events.from_anthropic({"input_tokens": 100, "output_tokens": 50, "cache_read_input_tokens": 1000,
                                    "cache_creation_input_tokens": 200}, response_model="claude-sonnet-5-5", request_id="a")
        self.assertEqual((ev.input_tokens, ev.cache_read_tokens, ev.cache_write_tokens, ev.output_tokens), (100, 1000, 200, 50))
        self.assertEqual(ev.total_tokens, 1350)
        self.assertEqual(ev.provenance["input_tokens"], "provider_reported")
        self.assertEqual(ev.provenance["reasoning_tokens"], "unavailable")

    def test_openai_input_includes_cached_and_writes_output_includes_reasoning(self):
        # input_tokens 12000 includes 4000 cached + 7000 cache writes -> 1000 uncached.
        ev = events.from_openai({"input_tokens": 12000, "output_tokens": 1186,
                                 "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000},
                                 "output_tokens_details": {"reasoning_tokens": 1024}},
                                response_model="gpt-6.2-sol", request_id="o")
        self.assertEqual((ev.input_tokens, ev.cache_read_tokens, ev.cache_write_tokens), (1000, 4000, 7000))
        self.assertEqual((ev.output_tokens, ev.reasoning_tokens), (1186, 1024))
        self.assertEqual(ev.total_tokens, 13186, "reasoning is inside output, not added again")

    def test_openai_chat_completions_field_names(self):
        ev = events.from_openai({"prompt_tokens": 500, "completion_tokens": 20,
                                 "prompt_tokens_details": {"cached_tokens": 128}}, request_id="c")
        self.assertEqual((ev.input_tokens, ev.cache_read_tokens, ev.output_tokens), (372, 128, 20))

    def test_missing_usage_is_unknown_not_zero(self):
        ev = events.from_anthropic({}, request_id="x", response_model="claude-sonnet-5-5")
        self.assertIsNone(ev.input_tokens)
        self.assertIsNone(ev.total_tokens)
        self.assertEqual(ev.provenance["output_tokens"], "unavailable")

    def test_same_request_same_id_retry_new_id(self):
        a = events.from_anthropic({"input_tokens": 1}, request_id="r1")
        b = events.from_anthropic({"input_tokens": 1}, request_id="r1")
        c = events.from_anthropic({"input_tokens": 1}, request_id="r1", attempt=2)
        self.assertEqual(a.event_id, b.event_id)
        self.assertNotEqual(a.event_id, c.event_id)
        self.assertTrue(c.is_retry)


class PricingTests(unittest.TestCase):
    def test_sonnet_5_5_plain(self):
        # 1,000,000 in x $2 + 100,000 out x $10 per 1M = 2.00 + 1.00 = 3.00
        ev = anth(1, {"input_tokens": 1_000_000, "output_tokens": 100_000})
        self.assertAlmostEqual(ev.cost_estimated, 3.00, places=8)
        self.assertEqual(ev.pricing_version, "anthropic-2026-11-28-v1")

    def test_cache_read_and_5m_and_1h_writes(self):
        # Opus 5.5: in 10,000 x $4 = 0.04; out 2,000 x $20 = 0.04; cache read 50,000 x $0.20 = 0.01;
        # writes 3,000 total of which 1,000 at 1h ($8) = 0.008 and 2,000 at 5m ($5) = 0.01 -> 0.108
        ev = anth(2, {"input_tokens": 10_000, "output_tokens": 2_000, "cache_read_input_tokens": 50_000,
                      "cache_creation_input_tokens": 3_000,
                      "cache_creation": {"ephemeral_5m_input_tokens": 2_000, "ephemeral_1h_input_tokens": 1_000}},
                  model="claude-opus-5-5")
        self.assertAlmostEqual(ev.cost_estimated, 0.108, places=8)
        self.assertIn("1-hour rate", ev.cost_method)

    def test_haiku_long_context_tier_counts_cache(self):
        # prompt = 40,000 in + 70,000 cache read = 110,000 > 100,000 -> long tier:
        # 40,000 x $0.50 = 0.02; 70,000 x $0.05 = 0.0035; 1,000 out x $2.50 = 0.0025 -> 0.026
        ev = anth(3, {"input_tokens": 40_000, "cache_read_input_tokens": 70_000, "output_tokens": 1_000},
                  model="claude-haiku-5-5")
        self.assertAlmostEqual(ev.cost_estimated, 0.026, places=8)
        self.assertIn("long-context", ev.cost_method)
        # Just under: 90,000 in x $0.10 = 0.009; 1,000 out x $0.50 = 0.0005 -> 0.0095
        ev2 = anth(4, {"input_tokens": 90_000, "output_tokens": 1_000}, model="claude-haiku-5-5")
        self.assertAlmostEqual(ev2.cost_estimated, 0.0095, places=8)

    def test_openai_cached_input_rate(self):
        # gpt-6.2-sol: uncached 1000 x $2 = 0.002; cached 4000 x $0.10 = 0.0004;
        # writes 7000 at input rate $2 = 0.014; out 1186 x $10 = 0.01186 -> 0.02826
        ev = events.from_openai({"input_tokens": 12000, "output_tokens": 1186,
                                 "input_tokens_details": {"cached_tokens": 4000, "cache_write_tokens": 7000}},
                                response_model="gpt-6.2-sol", request_id="p", timestamp=TS)
        self.assertAlmostEqual(pricing.estimate(ev).cost_estimated, 0.02826, places=8)

    def test_price_in_force_on_the_event_date(self):
        # Two dated entries for one model: the event date picks the price.
        import pricing_config
        from unittest import mock
        hist = {("anthropic", "test-model"): [
            {"effective_date": "2026-01-01", "version": "v-jan", "source": "test", "input": 1 / 1e6,
             "output": 0, "cache_read": 0, "cache_write": 0},
            {"effective_date": "2026-06-01", "version": "v-jun", "source": "test", "input": 3 / 1e6,
             "output": 0, "cache_read": 0, "cache_write": 0}]}
        with mock.patch.dict(pricing_config._PRICING_HISTORY, hist):
            a = anth(5, {"input_tokens": 1_000_000, "output_tokens": 0}, model="test-model", timestamp="2026-03-01T00:00:00Z")
            b = anth(6, {"input_tokens": 1_000_000, "output_tokens": 0}, model="test-model", timestamp="2026-07-01T00:00:00Z")
            c = anth(7, {"input_tokens": 1_000_000, "output_tokens": 0}, model="test-model", timestamp="2025-12-01T00:00:00Z")
        self.assertEqual((a.cost_estimated, a.pricing_version), (1.0, "v-jan"))
        self.assertEqual((b.cost_estimated, b.pricing_version), (3.0, "v-jun"))
        # Before any verified price: earliest one, labelled as back-applied.
        self.assertEqual((c.cost_estimated, c.pricing_version), (1.0, "v-jan"))
        self.assertIn("BACK-APPLIED", c.cost_method)
        self.assertEqual(c.provenance["cost_estimated"], "estimated_back_applied")

    def test_unknown_model_is_unpriced_not_zero(self):
        ev = anth(7, {"input_tokens": 10, "output_tokens": 10}, model="some-unlisted-model")
        self.assertIsNone(ev.cost_estimated)
        self.assertIn("unpriced", ev.cost_method)

    def test_incomplete_stream_is_partial(self):
        ev = events.from_anthropic({"input_tokens": 1_000_000}, response_model="claude-sonnet-5-5",
                                   request_id="s", timestamp=TS)
        events.mark_incomplete_stream(ev)
        pricing.estimate(ev)
        self.assertAlmostEqual(ev.cost_estimated, 2.00, places=8)  # input only
        self.assertIn("PARTIAL", ev.cost_method)
        self.assertEqual(ev.provenance["cost_estimated"], "estimated_partial")
        self.assertFalse(ev.complete)
        ev2 = events.from_anthropic({"input_tokens": 10}, response_model="claude-sonnet-5-5", request_id="s2")
        events.mark_incomplete_stream(ev2, received_output_chars=400)
        self.assertEqual((ev2.output_tokens, ev2.provenance["output_tokens"]), (100, "estimated"))


def fixture():
    """Two sessions, one agent execution with two nested calls and a retry."""
    ag = events.container(RequestType.AGENT_EXECUTION, event_id="agent1", session_id="s1", task_id="t1",
                          user_id="u1", project_id="p1", timestamp=TS)
    c1 = anth(10, {"input_tokens": 100_000, "output_tokens": 10_000}, session_id="s1", task_id="t1",
              user_id="u1", project_id="p1", parent_event_id="agent1")             # 0.2 + 0.1 = 0.30
    c2 = anth(11, {"input_tokens": 50_000, "output_tokens": 5_000}, session_id="s1", task_id="t1",
              user_id="u1", project_id="p1", parent_event_id="agent1", attempt=2)   # 0.1 + 0.05 = 0.15, retry
    c3 = anth(12, {"input_tokens": 1_000_000, "output_tokens": 0}, model="claude-haiku-5-5", session_id="s2",
              task_id="t2", user_id="u2", project_id="p2", timestamp="2026-11-27T09:00:00Z")  # 1M prompt > 100k: long tier 1M x $0.50 = 0.50, back-applied
    c3.success = False
    for c in (c1, c2):
        c.success = True
    return [ag, c1, c2, c3, c1]  # c1 recorded twice on purpose


class AnalyticsTests(unittest.TestCase):
    def test_totals_no_double_count(self):
        t = analytics.totals(fixture())
        # leaves: c1 (once), c2, c3 -> 3 requests; cost 0.30 + 0.15 + 0.50 = 0.95
        self.assertEqual(t["requests"], 3)
        self.assertAlmostEqual(t["cost_estimated"], 0.95, places=8)
        self.assertEqual(t["input_tokens"], 1_150_000)
        self.assertEqual(t["retry_rate"], round(1 / 3, 4))
        self.assertEqual(t["error_rate"], round(1 / 3, 4))
        self.assertEqual(t["sessions"], 2)

    def test_breakdown_by_user_and_project(self):
        by_user = {r["key"]: r for r in analytics.breakdown(fixture(), "user_id")}
        self.assertAlmostEqual(by_user["u1"]["cost_estimated"], 0.45, places=8)
        self.assertAlmostEqual(by_user["u2"]["cost_estimated"], 0.50, places=8)
        by_model = {r["key"]: r["requests"] for r in analytics.breakdown(fixture(), "model")}
        self.assertEqual(by_model, {"claude-sonnet-5-5": 2, "claude-haiku-5-5": 1})
        with self.assertRaises(ValueError):
            analytics.breakdown(fixture(), "password")

    def test_date_ranges_and_filter(self):
        today = date(2026, 11, 28)
        self.assertEqual(analytics.date_range("today", today=today), ("2026-11-28", "2026-11-28"))
        self.assertEqual(analytics.date_range("yesterday", today=today), ("2026-11-27", "2026-11-27"))
        self.assertEqual(analytics.date_range("7d", today=today), ("2026-11-22", "2026-11-28"))
        self.assertEqual(analytics.date_range("month", today=today), ("2026-11-01", "2026-11-28"))
        y = analytics.filter_events(fixture(), start="2026-11-27", end="2026-11-27")
        self.assertEqual([e.request_id for e in analytics.leaves(y)], ["req_12"])

    def test_session_detail_top_cost_and_share(self):
        d = analytics.session_detail(fixture(), "s1")
        self.assertEqual(d["totals"]["requests"], 2)
        self.assertEqual(d["top_cost_requests"][0]["event_id"], fixture()[1].event_id)
        # 0.30 of 0.45
        self.assertAlmostEqual(d["top_cost_requests"][0]["cost_share"], 0.6667, places=4)
        self.assertIsNone(analytics.session_detail(fixture(), "nope"))


class OutcomeTests(unittest.TestCase):
    def test_only_objective_or_human_evidence_verifies(self):
        o = lambda ev: outcomes.Outcome("o", "t", "dev_task_completed", "completed", evidence=ev)
        self.assertTrue(o("objective").verified_success)
        self.assertTrue(o("human").verified_success)
        self.assertFalse(o("ai_unverified").verified_success)
        self.assertFalse(o("estimated").verified_success)

    def test_value_metrics_by_hand(self):
        rows = [
            outcomes.Outcome("1", "t1", "code_fix_verified", "completed", evidence="objective", attempts=1, corrections=0,
                             time_saved_minutes=30, time_saved_source="measured"),
            outcomes.Outcome("2", "t2", "code_fix_verified", "completed", evidence="ai_unverified", attempts=2, corrections=1,
                             time_saved_minutes=60, time_saved_source="estimated"),
            outcomes.Outcome("3", "t3", "code_fix_verified", "failed", evidence="objective", corrections=2),
        ]
        cost = {"t1": 0.40, "t2": 0.20, "t3": 0.30}
        v = outcomes.value_metrics(rows, cost, active_hours=2, hourly_rate=60)
        self.assertEqual((v["tasks"], v["completed"], v["verified_successes"]), (3, 2, 1))
        self.assertAlmostEqual(v["total_cost"], 0.90)
        self.assertAlmostEqual(v["cost_per_verified_success"], 0.90)  # ALL spend / 1 verified
        self.assertAlmostEqual(v["cost_of_unsuccessful_attempts"], 0.30)
        self.assertEqual(v["first_attempt_success_rate"], 0.5)
        self.assertEqual(v["rework_rate"], round(2 / 3, 4))
        self.assertEqual((v["time_saved_minutes_measured"], v["time_saved_minutes_estimated"]), (30, 60))
        # ROI estimate: 90 min = 1.5 h x 60 = 90; (90 - 0.9) / 0.9 = 99.0
        self.assertEqual(v["roi_estimate"], 99.0)
        self.assertIn("ESTIMATE", v["roi_basis"])
        self.assertEqual(v["verified_per_hour"], 0.5)

    def test_no_outcomes_no_fake_numbers(self):
        v = outcomes.value_metrics([], {})
        self.assertIsNone(v["cost_per_verified_success"])
        self.assertIsNone(v["roi_estimate"])


if __name__ == "__main__":
    unittest.main()


class BillingSplitTests(unittest.TestCase):
    """Metered spend and subscription equivalent value are reported apart (2026-11-28)."""

    def test_split_hand_computed(self):
        from usage_intel import analytics
        evs = [UsageEvent(event_id="m1", timestamp="2026-11-20T10:00:00Z", provider="anthropic", requested_model="x", input_tokens=1, output_tokens=1,
                          cost_estimated=0.30, billing_category="metered_api"),
               UsageEvent(event_id="m2", timestamp="2026-11-20T10:00:00Z", provider="anthropic", requested_model="x", input_tokens=1, output_tokens=1,
                          cost_estimated=0.20, billing_category="metered_api"),
               UsageEvent(event_id="s1", timestamp="2026-11-20T10:00:00Z", provider="anthropic", requested_model="x", input_tokens=1, output_tokens=1,
                          cost_estimated=1.50, billing_category="equivalent_api_value")]
        t = analytics.totals(evs)
        self.assertAlmostEqual(t["cost_estimated"], 2.00)        # list-price cost of all usage
        self.assertAlmostEqual(t["spend_estimated"], 0.50)       # 0.30 + 0.20 metered only
        self.assertAlmostEqual(t["equivalent_api_value"], 1.50)  # subscription, not spend
        self.assertEqual(t["spend_estimated_coverage"], "2 of 2 calls priced")

    def test_no_subscription_usage_is_zero_not_unknown(self):
        from usage_intel import analytics
        t = analytics.totals([UsageEvent(event_id="m", timestamp="2026-11-20T10:00:00Z", provider="anthropic", requested_model="x", cost_estimated=0.1)])
        self.assertEqual(t["equivalent_api_value"], 0.0)
        self.assertEqual(t["equivalent_api_value_coverage"], "0 of 0 calls priced")
