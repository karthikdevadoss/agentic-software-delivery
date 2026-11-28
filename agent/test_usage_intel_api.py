"""Hermetic tests for usage_intel.api: authorization, demo/live isolation,
validation, and that every response carries its dataset and legends."""
import unittest

from usage_intel import api
from usage_intel.events import UsageEvent
from usage_intel.outcomes import Outcome

PUBLIC = api.principal_for(False)
OWNER = api.principal_for(True)


def live_loader():
    ev = UsageEvent(event_id="L1", timestamp=api._today().isoformat() + "T09:00:00Z", provider="anthropic",
                    requested_model="claude-sonnet-5-5", input_tokens=1_000_000, output_tokens=0,
                    cost_estimated=2.0, session_id="live-s", task_id="live-t", org_id="org_platform_owner",
                    user_id="owner", dataset="live")
    return {"events": [ev], "outcomes": [Outcome("o", "live-t", "dev_task_completed", "completed", evidence="objective")],
            "learning": [], "budgets": []}


class ApiTests(unittest.TestCase):
    def test_public_gets_labelled_demo(self):
        r = api.overview(PUBLIC, {"dataset": "demo", "range": "30d"})
        self.assertEqual(r["dataset"], "demo")
        self.assertIn("Fictional", r["demo_label"])
        self.assertGreater(r["overview"]["requests"], 0)
        self.assertIn("unavailable", r["provenance_legend"])
        self.assertIn("equivalent_api_value", r["billing_legend"])

    def test_public_cannot_read_live(self):
        for fn in (api.overview, api.breakdown, api.sessions, api.recommendations, api.models, api.learning_view):
            with self.assertRaises(api.ApiError) as cm:
                fn(PUBLIC, {"dataset": "live"}, live_loader=live_loader)
            self.assertEqual(cm.exception.status, 403)

    def test_owner_live_never_contains_demo(self):
        r = api.overview(OWNER, {"dataset": "live", "range": "7d"}, live_loader=live_loader)
        self.assertEqual(r["dataset"], "live")
        self.assertIsNone(r["demo_label"])
        self.assertEqual(r["overview"]["requests"], 1)
        self.assertEqual(r["overview"]["cost_estimated"], 2.0)
        self.assertEqual(r["overview"]["value"]["verified_successes"], 1)

    def test_bad_params(self):
        for params in ({"dataset": "prod"}, {"range": "forever"}, {"range": "custom", "start": "28/11/2026"}):
            with self.assertRaises(api.ApiError) as cm:
                api.overview(PUBLIC, params)
            self.assertEqual(cm.exception.status, 400)
        with self.assertRaises(api.ApiError):
            api.breakdown(PUBLIC, {"by": "email"})

    def test_filters_and_breakdown(self):
        r = api.breakdown(PUBLIC, {"dataset": "demo", "by": "model", "team_id": "team_support"})
        keys = {row["key"] for row in r["rows"]}
        self.assertNotIn("claude-opus-5-5", keys)  # Opus is only used by team_platform in the demo

    def test_session_detail_and_404(self):
        sid = api.sessions(PUBLIC, {"dataset": "demo"})["sessions"][0]["session_id"]
        self.assertEqual(api.session_detail(PUBLIC, {"dataset": "demo"}, sid)["session"]["session_id"], sid)
        with self.assertRaises(api.ApiError) as cm:
            api.session_detail(PUBLIC, {"dataset": "demo"}, "nope")
        self.assertEqual(cm.exception.status, 404)

    def test_writes_need_owner(self):
        with self.assertRaises(api.ApiError) as cm:
            api.record_outcome(PUBLIC, {"task_id": "t", "outcome_type": "x", "status": "completed", "evidence": "human"},
                               saver=lambda o, a: None)
        self.assertEqual(cm.exception.status, 403)
        with self.assertRaises(api.ApiError):
            api.record_learning(PUBLIC, {"records": []}, saver=lambda r, a: 0)

    def test_outcome_validation(self):
        saved = []
        ok = api.record_outcome(OWNER, {"task_id": "t", "outcome_type": "code_fix_verified", "status": "completed",
                                        "evidence": "objective"}, saver=lambda o, a: saved.append((o, a)))
        self.assertTrue(ok["recorded"]["verified_success"])
        self.assertEqual(saved[0][1], "owner")
        bad = [{"task_id": "t", "outcome_type": "x", "status": "done", "evidence": "human"},
               {"task_id": "t", "outcome_type": "x", "status": "completed", "evidence": "vibes"},
               {"task_id": "t", "outcome_type": "x", "status": "completed", "evidence": "human", "time_saved_minutes": 5},
               {"task_id": "t", "outcome_type": "x", "status": "completed", "evidence": "human", "dataset": "demo"}]
        for body in bad:
            with self.assertRaises(api.ApiError) as cm:
                api.record_outcome(OWNER, body, saver=lambda o, a: None)
            self.assertEqual(cm.exception.status, 400)

    def test_learning_manual_and_import(self):
        got = []
        r = api.record_learning(OWNER, {"records": [{"session_id": "s", "section": "S", "concept": "C",
                                                      "event": "introduced", "minutes": 5}]},
                                saver=lambda recs, a: got.extend(recs) or len(recs))
        self.assertEqual((r["recorded"], r["source"], got[0].user_id), (1, "manual", "owner"))
        r2 = api.record_learning(OWNER, {"import": {"format": "csv", "text": "session_id,section,concept,event\ns,S,C,studied\n"}},
                                 saver=lambda recs, a: len(recs))
        self.assertEqual(r2["source"], "imported")
        with self.assertRaises(api.ApiError):
            api.record_learning(OWNER, {"records": [{"session_id": "s", "section": "S", "concept": "C",
                                                      "event": "introduced", "source": "platform"}]},
                                saver=lambda recs, a: 0)

    def test_budget_counts_metered_spend_only(self):
        from usage_intel import analytics
        r = api.overview(PUBLIC, {"dataset": "demo", "range": "month"})
        o = r["overview"]
        self.assertGreater(o["equivalent_api_value"], 0)  # demo has subscription usage
        month = analytics.filter_events(api._demo_for(api._today().isoformat())["events"],
                                        start=api._today().replace(day=1).isoformat(), end=api._today().isoformat())
        t = analytics.totals(month)
        self.assertAlmostEqual(o["budget"]["spent"], round(t["spend_estimated"], 6))
        self.assertLess(o["budget"]["spent"], t["cost_estimated"])

    def test_outcome_attribution_is_server_assigned(self):
        # QA finding 2026-11-28: a client-set user_id/org_id/team_id was accepted.
        for field in ("user_id", "org_id", "team_id"):
            with self.assertRaises(api.ApiError) as cm:
                api.record_outcome(OWNER, {"task_id": "t", "outcome_type": "x", "status": "completed",
                                           "evidence": "human", field: "mallory"}, saver=lambda o, a: None)
            self.assertEqual(cm.exception.status, 400)
        saved = []
        api.record_outcome(OWNER, {"task_id": "t", "outcome_type": "x", "status": "completed", "evidence": "human"},
                           saver=lambda o, a: saved.append(o))
        self.assertEqual((saved[0].user_id, saved[0].org_id), ("owner", "org_platform_owner"))

    def test_outcome_types_checked(self):
        for extra in ({"attempts": "abc"}, {"attempts": -1}, {"attempts": True}, {"human_review_minutes": "5"},
                      {"feedback": "x" * 281}, {"project_id": 7}):
            with self.assertRaises(api.ApiError) as cm:
                api.record_outcome(OWNER, {"task_id": "t", "outcome_type": "x", "status": "completed",
                                           "evidence": "human", **extra}, saver=lambda o, a: None)
            self.assertEqual(cm.exception.status, 400, extra)

    def test_live_learning_never_contains_demo_records(self):
        demo_data = api._demo_for(api._today().isoformat())
        leaked = api.load(OWNER, "live", live_loader=lambda: {**demo_data, "budgets": []})
        self.assertEqual(leaked["learning"], [])
        self.assertTrue(api.load(PUBLIC, "demo")["learning"])

    def test_unknown_budget_spend_is_not_zero(self):
        from usage_intel import analytics
        o = analytics.overview([], [], {"scope": "org", "limit": 100.0, "spent": None})
        self.assertIsNone(o["budget"]["consumed_ratio"])
        self.assertIsNone(o["budget"]["remaining"])


if __name__ == "__main__":
    unittest.main()
