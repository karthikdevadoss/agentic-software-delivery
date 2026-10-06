"""
Unit tests for agent/publish_eval_results.py using synthetic eval output --
no index, no embedding model, no network. Hermetic.

Run: python agent/test_publish_eval_results.py
"""

import contextlib
import io
import json
import unittest

import eval_runner
import publish_eval_results as pub


def _retrieval(r3=0.833, mrr=0.868, r5=0.917, cases=None):
    cases = cases if cases is not None else [
        {"id": "rq-01", "query": "q1", "hit_at_3": True, "hit_at_5": True,
         "reciprocal_rank": 1.0, "top_result": "a.java"},
        {"id": "rq-02", "query": "q2", "hit_at_3": False, "hit_at_5": True,
         "reciprocal_rank": 0.16666666, "top_result": "b.md"},
    ]
    return {"summary": {"cases": len(cases), "recall_at_3": r3, "recall_at_5": r5, "mrr": mrr},
            "per_case": cases}


def _routing(acc=1.0, sec=1.0):
    per_case = [
        {"id": "r1", "requirement": "x", "expected_route": "REJECT_UNAUTHORIZED",
         "actual_route": "REJECT_UNAUTHORIZED", "correct": True},
        {"id": "r2", "requirement": "y", "expected_route": "SEARCH",
         "actual_route": "SEARCH", "correct": True},
        {"id": "r3", "requirement": "z", "expected_route": "SEARCH",
         "actual_route": "SEARCH", "correct": True},
    ]
    return {"summary": {"cases": len(per_case), "routing_accuracy": acc,
                        "security_case_accuracy": sec}, "per_case": per_case}


def _build(retrieval, routing, **kw):
    return pub.build_eval_results(retrieval, routing, commit_sha="abc1234",
                                  generated_at="2026-10-06T09:40:00Z",
                                  embedding_model="local:test", **kw)


class BuildEvalResultsTestCase(unittest.TestCase):
    def test_all_passing_has_required_fields(self):
        out = _build(_retrieval(), _routing())
        self.assertTrue(out["overall_passed"])
        self.assertEqual(out["commit_sha"], "abc1234")
        self.assertEqual(out["generated_at"], "2026-10-06T09:40:00Z")
        self.assertEqual(out["labelled_set"],
                         {"retrieval_cases": 2, "routing_cases": 3, "security_routing_cases": 1})
        keys = [m["key"] for m in out["metrics"]]
        self.assertEqual(keys, ["recall_at_3", "mrr", "routing_accuracy", "security_case_accuracy"])
        for m in out["metrics"]:
            self.assertEqual(m["threshold"], eval_runner.THRESHOLDS[m["key"]])
            self.assertTrue(m["passed"])
        self.assertEqual(out["informational"]["recall_at_5"], 0.917)
        self.assertEqual(out["retrieval_cases"][1]["reciprocal_rank"], 0.167)
        self.assertIn("eval_runner.py all", out["ci_gate"]["command"])

    def test_retrieval_drop_below_threshold_fails(self):
        out = _build(_retrieval(r3=0.39), _routing())
        self.assertFalse(out["overall_passed"])
        r3 = next(m for m in out["metrics"] if m["key"] == "recall_at_3")
        self.assertFalse(r3["passed"])

    def test_score_exactly_at_threshold_passes(self):
        out = _build(_retrieval(r3=eval_runner.THRESHOLDS["recall_at_3"],
                                mrr=eval_runner.THRESHOLDS["mrr"]), _routing())
        self.assertTrue(out["overall_passed"])

    def test_security_metric_is_zero_tolerance(self):
        out = _build(_retrieval(), _routing(sec=0.99))
        sec = next(m for m in out["metrics"] if m["key"] == "security_case_accuracy")
        self.assertEqual(sec["comparator"], "==")
        self.assertFalse(sec["passed"])
        self.assertFalse(out["overall_passed"])

    def test_missing_score_fails_rather_than_passing(self):
        out = _build(_retrieval(r3=None), _routing())
        self.assertFalse(out["overall_passed"])

    def test_output_is_json_serialisable(self):
        json.dumps(_build(_retrieval(), _routing()))

    def test_overall_verdict_matches_eval_runner_gate(self):
        """The published pass/fail must agree with the CI gate
        (eval_runner._print_report) for passing and failing inputs."""
        scenarios = [
            (_retrieval(), _routing()),
            (_retrieval(r3=0.2), _routing()),
            (_retrieval(mrr=0.1), _routing()),
            (_retrieval(), _routing(acc=0.5)),
            (_retrieval(), _routing(sec=0.9)),
        ]
        for retrieval, routing in scenarios:
            with contextlib.redirect_stdout(io.StringIO()):
                gate = eval_runner._print_report(retrieval, routing)
            self.assertEqual(_build(retrieval, routing)["overall_passed"], gate)


class MetricPassesTestCase(unittest.TestCase):
    def test_unknown_comparator_raises(self):
        with self.assertRaises(ValueError):
            pub.metric_passes(1.0, 1.0, "<")


class SummariseCiRunsTestCase(unittest.TestCase):
    def test_skipped_streak_and_last_success(self):
        runs = [
            {"created_at": "2026-10-06T06:23:13Z", "head_sha": "c" * 40, "eval_step": "skipped",
             "failed_steps": ["Python hermetic test suite"]},
            {"created_at": "2026-10-05T06:24:09Z", "head_sha": "b" * 40, "eval_step": "skipped",
             "failed_steps": ["Python hermetic test suite"]},
            {"created_at": "2026-09-29T17:07:25Z", "head_sha": "a" * 40, "eval_step": "success",
             "failed_steps": []},
        ]
        out = pub.summarise_ci_runs(runs, "2026-10-06T10:00:00Z")
        self.assertEqual(out["latest_run"]["eval_step"], "skipped")
        self.assertEqual(out["latest_run"]["failed_steps_in_same_job"], ["Python hermetic test suite"])
        self.assertEqual(out["runs_since_eval_step_last_passed"], 2)
        self.assertEqual(out["last_eval_step_success"]["head_sha"], "a" * 40)

    def test_latest_run_passing(self):
        runs = [{"created_at": "t", "head_sha": "a" * 40, "eval_step": "success", "failed_steps": []}]
        out = pub.summarise_ci_runs(runs, "now")
        self.assertEqual(out["runs_since_eval_step_last_passed"], 0)

    def test_no_success_in_window_is_reported_as_unknown(self):
        runs = [{"created_at": "t", "head_sha": "a" * 40, "eval_step": "skipped", "failed_steps": []}]
        out = pub.summarise_ci_runs(runs, "now")
        self.assertIsNone(out["last_eval_step_success"])
        self.assertIsNone(out["runs_since_eval_step_last_passed"])

    def test_no_runs_means_not_captured(self):
        self.assertIsNone(pub.summarise_ci_runs([], "now"))
        self.assertIsNone(_build(_retrieval(), _routing())["ci_gate"]["observed"])


class EvalInputHashesTestCase(unittest.TestCase):
    def _fake_repo(self, tmp):
        from pathlib import Path
        root = Path(tmp)
        for rel in pub.EVAL_INPUT_FILES:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text("content of " + rel + "\n", encoding="utf-8")
        return root

    def test_hash_changes_when_an_input_file_changes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fake_repo(tmp)
            before = pub.compute_eval_input_hashes(root, {"a": 1})
            target = root / pub.EVAL_INPUT_FILES[1]
            target.write_text(target.read_text(encoding="utf-8") + "new case\n", encoding="utf-8")
            after = pub.compute_eval_input_hashes(root, {"a": 1})
        changed = [k for k in before["files"] if before["files"][k] != after["files"][k]]
        self.assertEqual(changed, [pub.EVAL_INPUT_FILES[1]])

    def test_hash_changes_when_a_threshold_changes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fake_repo(tmp)
            a = pub.compute_eval_input_hashes(root, {"recall_at_3": 0.40})
            b = pub.compute_eval_input_hashes(root, {"recall_at_3": 0.30})
        self.assertNotEqual(a["thresholds"], b["thresholds"])
        self.assertEqual(a["files"], b["files"])

    def test_crlf_checkout_hashes_the_same_as_lf(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = self._fake_repo(tmp)
            lf = pub.compute_eval_input_hashes(root, {})
            for rel in pub.EVAL_INPUT_FILES:
                p = root / rel
                p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
            crlf = pub.compute_eval_input_hashes(root, {})
        self.assertEqual(lf, crlf)

    def test_build_records_inputs_and_what_is_not_covered(self):
        out = _build(_retrieval(), _routing(), eval_inputs={"files": {"x": "1"}, "thresholds": "2"})
        self.assertEqual(out["eval_inputs"]["files"], {"x": "1"})
        self.assertTrue(out["eval_inputs"]["not_covered"])


class PublishedArtifactTestCase(unittest.TestCase):
    """The committed agent/web/eval-results.json and the /eval page that
    renders it. Reads files only -- nothing is measured here."""

    def setUp(self):
        self.data = json.loads(pub.OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_published_json_has_required_fields(self):
        for key in ("generated_at", "commit_sha", "labelled_set", "metrics",
                    "overall_passed", "ci_gate", "sources", "retrieval_cases"):
            self.assertIn(key, self.data)
        self.assertRegex(self.data["commit_sha"], r"^[0-9a-f]{40}$")
        self.assertEqual(self.data["labelled_set"]["retrieval_cases"],
                         len(self.data["retrieval_cases"]))

    def test_published_thresholds_match_eval_runner(self):
        for m in self.data["metrics"]:
            self.assertEqual(m["threshold"], eval_runner.THRESHOLDS[m["key"]])

    def test_published_verdicts_are_internally_consistent(self):
        for m in self.data["metrics"]:
            self.assertEqual(m["passed"], pub.metric_passes(m["score"], m["threshold"], m["comparator"]))
        self.assertEqual(self.data["overall_passed"], all(m["passed"] for m in self.data["metrics"]))

    def test_eval_page_is_routed_and_loads_the_json(self):
        import web_server
        routes = {r.path: r for r in web_server.routes if hasattr(r, "path")}
        self.assertIn("/eval", routes)
        self.assertIs(routes["/eval"].endpoint, web_server.eval_page)
        html = (pub.AGENT_DIR / "web" / "eval.html").read_text(encoding="utf-8")
        self.assertIn('src="/eval.js"', html)
        self.assertIn('id="top-nav"', html)
        js = (pub.AGENT_DIR / "web" / "eval.js").read_text(encoding="utf-8")
        self.assertIn("/eval-results.json", js)


if __name__ == "__main__":
    unittest.main()
