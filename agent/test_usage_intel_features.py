"""Hermetic tests: access isolation, demo isolation, learning metrics (by
hand), import parsing, recommendations (fire on bad data, silent on clean
data), model comparison."""
import json
import unittest
from datetime import date

from usage_intel import access, analytics, compare, demo, learning, recommend
from usage_intel.events import UsageEvent
from usage_intel.learning import LearningRecord
from usage_intel.outcomes import Outcome


def ev(i, **kw):
    base = dict(event_id=f"e{i}", timestamp="2026-11-28T10:00:00Z", provider="anthropic",
                requested_model="claude-sonnet-5-5", input_tokens=1000, output_tokens=100, cost_estimated=0.01)
    base.update(kw)
    return UsageEvent(**base)


class AccessTests(unittest.TestCase):
    rows = [ev(1, org_id="A", team_id="t1", user_id="u1"), ev(2, org_id="A", team_id="t2", user_id="u2"),
            ev(3, org_id="B", team_id="t9", user_id="u9"), ev(4, org_id="A", team_id="t1", user_id="u1", dataset="demo")]

    def ids(self, p):
        return [r.event_id for r in access.scope(p, self.rows)]

    def test_roles(self):
        self.assertEqual(self.ids(access.Principal("owner")), ["e1", "e2", "e3"])
        self.assertEqual(self.ids(access.Principal("org_admin", org_id="A")), ["e1", "e2"])
        self.assertEqual(self.ids(access.Principal("team_lead", org_id="A", team_id="t1")), ["e1"])
        self.assertEqual(self.ids(access.Principal("member", org_id="A", team_id="t1", user_id="u1")), ["e1"])

    def test_public_sees_only_demo_and_live_never_sees_demo(self):
        self.assertEqual(self.ids(access.Principal("demo_viewer")), ["e4"])
        self.assertNotIn("e4", self.ids(access.Principal("owner")))

    def test_out_of_scope_filters_are_refused(self):
        with self.assertRaises(access.Forbidden):
            access.check_filters(access.Principal("org_admin", org_id="A"), org_id="B")
        with self.assertRaises(access.Forbidden):
            access.check_filters(access.Principal("member", org_id="A", user_id="u1"), user_id="u2")
        access.check_filters(access.Principal("member", org_id="A", user_id="u1"), user_id="u1")

    def test_unknown_role_rejected(self):
        with self.assertRaises(ValueError):
            access.Principal("superuser")


class DemoTests(unittest.TestCase):
    def test_deterministic_labelled_and_isolated(self):
        a, b = demo.build(today=date(2026, 11, 28)), demo.build(today=date(2026, 11, 28))
        self.assertEqual([e.event_id for e in a["events"]], [e.event_id for e in b["events"]])
        self.assertTrue(all(e.dataset == "demo" for e in a["events"]))
        self.assertTrue(all(o.dataset == "demo" for o in a["outcomes"]))
        self.assertTrue(all(r.source == "demo" for r in a["learning"]))
        leaf = analytics.leaves(a["events"])
        self.assertTrue(all(e.provenance.get("input_tokens") == "demo" for e in leaf))
        self.assertTrue(all(e.provenance.get("cost_estimated") == "demo" for e in leaf))
        self.assertIn("Fictional", a["label"])

    def test_dates_follow_today_so_filters_work(self):
        d = demo.build(today=date(2026, 11, 28), days=30)
        days = {e.timestamp[:10] for e in d["events"]}
        self.assertEqual((min(days), max(days)), ("2026-10-30", "2026-11-28"))

    def test_no_real_identities(self):
        d = demo.build(today=date(2026, 11, 28))
        users = {e.user_id for e in d["events"] if e.user_id}
        self.assertEqual(users, {"dana", "eli", "farah", "gus", "hana", "ivo"})
        self.assertTrue(all(e.org_id == demo.ORG for e in d["events"]))


class LearningTests(unittest.TestCase):
    def test_explanation_never_counts_as_mastery(self):
        recs = [LearningRecord("s1", "Retrieval", "BM25", "introduced", minutes=10),
                LearningRecord("s1", "Retrieval", "BM25", "verification", correct=True, attempt=1, evidence="ai_explanation"),
                LearningRecord("s1", "Retrieval", "BM25", "verification", correct=True, attempt=2, evidence="self_report")]
        self.assertEqual(learning.metrics(recs)["concepts_verified"], 0)

    def test_metrics_by_hand(self):
        # Concept A: wrong then right (2 attempts). Concept B: right first time. Concept C: introduced only.
        recs = [LearningRecord("s1", "Ret", "A", "introduced", minutes=20),
                LearningRecord("s1", "Ret", "B", "introduced", minutes=10),
                LearningRecord("s2", "Ret", "C", "introduced", minutes=30),
                LearningRecord("s1", "Ret", "A", "verification", correct=False, attempt=1, evidence="assessment"),
                LearningRecord("s1", "Ret", "A", "verification", correct=True, attempt=2, evidence="assessment"),
                LearningRecord("s1", "Ret", "B", "verification", correct=True, attempt=1, evidence="reviewed_exercise"),
                LearningRecord("s2", "Ret", "A", "retention_test", correct=True, evidence="assessment"),
                LearningRecord("s2", "Ret", "B", "retention_test", correct=False, evidence="assessment")]
        m = learning.metrics(recs, {"s1": 0.10, "s2": None}, {"Ret": 4})
        self.assertEqual((m["concepts_introduced"], m["concepts_verified"]), (3, 2))
        self.assertEqual(m["first_attempt_accuracy"], 0.5)          # A wrong, B right on attempt 1
        self.assertEqual(m["attempts_per_verified_concept"], 1.5)   # (2 + 1) / 2
        self.assertEqual(m["retention_accuracy"], 0.5)
        self.assertEqual(m["learning_minutes"], 60.0)
        self.assertEqual(m["verified_per_hour"], 2.0)               # 2 verified / 1 h
        self.assertEqual(m["cost_per_verified_concept"], 0.05)      # 0.10 / 2 (s2 cost unknown, excluded)
        self.assertEqual(m["ai_cost_coverage"], "1 of 2 sessions have measured AI cost")
        self.assertEqual(m["by_section"][0]["progress"], 0.5)       # 2 of 4

    def test_import_json_and_csv(self):
        js = json.dumps([{"session_id": "x", "section": "S", "concept": "C", "event": "verification",
                          "correct": True, "attempt": 1, "evidence": "assessment"}])
        r = learning.parse_import(js, "json", user_id="owner")
        self.assertEqual((r[0].source, r[0].user_id, r[0].verifies), ("imported", "owner", True))
        csv_text = "session_id,section,concept,event,correct,attempt,evidence,minutes\nx,S,C,verification,true,1,assessment,2.5\n"
        r2 = learning.parse_import(csv_text, "csv", user_id="owner")
        self.assertEqual((r2[0].correct, r2[0].attempt, r2[0].minutes), (True, 1, 2.5))

    def test_import_rejects_unknown_fields_and_spoofed_source(self):
        with self.assertRaises(ValueError):
            learning.parse_import(json.dumps([{"session_id": "x", "section": "S", "concept": "C",
                                               "event": "introduced", "source": "platform"}]), "json", "owner")
        with self.assertRaises(ValueError):
            learning.parse_import("[]x", "xml", "owner")


def wf_events(retry_every=None, n=20):
    out = []
    for i in range(n):
        out.append(ev(i, workflow_id="wf", is_retry=bool(retry_every and i % retry_every == 0), task_id=f"t{i}",
                      error_category="timeout" if (retry_every and i % retry_every == 0) else None))
    return out


class RecommendationTests(unittest.TestCase):
    def test_retry_rule_fires_with_evidence(self):
        recs = recommend.high_retry_workflows(wf_events(retry_every=2))  # 10 of 20 = 50%
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["evidence"]["retry_rate"], 0.5)
        self.assertAlmostEqual(r["potential_benefit"]["estimated_usd"], 0.10)  # 10 retries x $0.01
        self.assertIn("ESTIMATE", r["potential_benefit"]["basis"])
        for key in ("evidence", "why_it_matters", "suggested_action", "confidence", "limitations", "requires_evaluation"):
            self.assertIn(key, r)

    def test_clean_data_gives_no_advice(self):
        self.assertEqual(recommend.high_retry_workflows(wf_events()), [])
        self.assertEqual(recommend.excessive_context([ev(i, activity_category="x") for i in range(20)]), [])

    def test_excessive_context(self):
        rows = [ev(i, activity_category="support", input_tokens=2000, cost_estimated=0.01) for i in range(12)]
        rows.append(ev(99, activity_category="support", input_tokens=60000, cost_estimated=0.30))
        recs = recommend.excessive_context(rows)
        self.assertEqual(recs[0]["evidence"]["large_requests"], 1)
        self.assertTrue(recs[0]["requires_evaluation"])

    def test_expensive_model_needs_evaluation_and_never_claims_parity(self):
        evs, outs = [], []
        for i in range(12):
            evs.append(ev(i, task_id=f"a{i}", activity_category="faq", requested_model="claude-opus-5-5", cost_estimated=0.05))
            evs.append(ev(100 + i, task_id=f"b{i}", activity_category="faq", requested_model="claude-haiku-5-5", cost_estimated=0.001))
            outs += [Outcome(f"oa{i}", f"a{i}", "support_resolution", "completed", evidence="human", difficulty="simple"),
                     Outcome(f"ob{i}", f"b{i}", "support_resolution", "completed", evidence="human", difficulty="simple")]
        recs = recommend.expensive_model_for_simple_tasks(evs, outs)
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["evidence"]["cheapest_model_used"], "claude-haiku-5-5")
        self.assertEqual(recs[0]["evidence"]["input_price_ratio_vs_cheapest"], 40.0)  # $4 / $0.10
        self.assertTrue(recs[0]["requires_evaluation"])
        self.assertIn("do not prove", recs[0]["limitations"])

    def test_demo_produces_each_kind(self):
        d = demo.build(today=date(2026, 11, 28))
        kinds = {r["kind"] for r in recommend.all_recommendations(d["events"], d["outcomes"])}
        self.assertTrue({"high_retry_rate", "long_agent_runs", "expensive_model", "successful_optimisation"} <= kinds)


class CompareTests(unittest.TestCase):
    def test_cheapest_model_that_meets_quality(self):
        evs, outs = [], []
        spec = {"cheap": (0.001, 0.80), "mid": (0.01, 0.90), "dear": (0.05, 0.91)}
        for m, (cost, rate) in spec.items():
            for i in range(20):
                tid = f"{m}{i}"
                evs.append(ev(f"{m}-{i}", task_id=tid, activity_category="qa", requested_model=m, cost_estimated=cost))
                outs.append(Outcome(f"o{tid}", tid, "x", "completed" if i < rate * 20 else "failed", evidence="objective"))
        res = compare.compare(evs, outs)[0]
        # Completed when i < rate*20: cheap i<16 -> 16/20 = 0.80; mid i<18 -> 0.90; dear i<18.2 -> 19/20 = 0.95.
        # Best is 0.95; only models within 3 points (>= 0.92) qualify -> only "dear", despite its price.
        self.assertEqual(res["suggestion"]["model"], "dear")
        self.assertTrue(res["suggestion"]["advisory_only"])

    def test_no_suggestion_without_enough_tasks(self):
        evs = [ev(i, task_id=f"t{i}", activity_category="qa", requested_model=m) for i, m in enumerate(["a", "b"])]
        outs = [Outcome(f"o{i}", f"t{i}", "x", "completed", evidence="objective") for i in range(2)]
        self.assertIsNone(compare.compare(evs, outs)[0]["suggestion"])


if __name__ == "__main__":
    unittest.main()
