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
            self.assertEqual(m["threshold"], eval_runner.ALL_METRIC_THRESHOLDS[m["key"]])
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


class AgentDecisionSectionTestCase(unittest.TestCase):
    RESULTS = {"run_at_utc": "2026-09-16T09:46:39+00:00", "results": [
        {"eval_id": "E1", "ticket": "t1", "verdict": "PASS", "reason": "r",
         "tool_calls": [{"name": "read_file", "input": {"path": "secret-ish"}, "result_excerpt": "x"},
                        {"name": "search_code", "input": {}, "result_excerpt": "y"},
                        {"name": "read_file", "input": {}, "result_excerpt": "z"}],
         "write_occurred": False, "approval_present": False, "unsafe_action_attempted": False,
         "model": "m", "evidence_reference": "C:\\Users\\someone\\file.json"},
        {"eval_id": "E2", "ticket": "", "verdict": "NOT_EXECUTED", "reason": "r", "tool_calls": 0,
         "write_occurred": False, "approval_present": True, "unsafe_action_attempted": False, "model": "m"},
    ]}
    DATASET = {"cases": [{"eval_id": "E1", "name": "correct_plan"}, {"eval_id": "E2", "name": "x"}]}

    def setUp(self):
        self.out = pub.build_agent_decision_section(self.RESULTS, self.DATASET, "c" * 40)

    def test_labelled_with_recorded_date_and_counts_as_recorded(self):
        self.assertEqual(self.out["label"], "recorded 2026-09-16")
        self.assertEqual(self.out["summary"], {"PASS": 1, "FAIL": 0, "NOT_EXECUTED": 1, "UNKNOWN": 0})
        self.assertEqual(self.out["cases_total"], 2)
        self.assertEqual(self.out["approval_gate_exercised_cases"], 1)
        self.assertEqual(self.out["cases"][0]["name"], "correct_plan")

    def test_tool_calls_published_as_count_and_names_only(self):
        c = self.out["cases"][0]
        self.assertEqual(c["tool_calls"], 3)
        self.assertEqual(c["tools_used"], ["read_file", "search_code"])
        self.assertNotIn("result_excerpt", json.dumps(self.out))
        self.assertEqual(self.out["cases"][1]["tool_calls"], 0)

    def test_local_machine_path_is_not_published(self):
        self.assertNotIn("Users", json.dumps(self.out))
        self.assertNotIn("evidence_reference", self.out["cases"][0])


AD_SECTION = {"cases_total": 6, "summary": {"PASS": 6, "FAIL": 0, "NOT_EXECUTED": 0, "UNKNOWN": 0},
              "run_at_utc": "2026-09-16T09:46:39+00:00", "recorded_commit": "d" * 40}
INPUTS = {"files": {f: f"{i:064d}" for i, f in enumerate(pub.EVAL_INPUT_FILES)}, "thresholds": "t" * 64}


PERM = {"summary": {"cases": 10, "passed": 10, "leaks_or_failures": 0}, "per_case": []}
SELF = {"summary": {"cases": 20, "catch_rate": 0.9, "good_pass_rate": 1.0}, "per_case": []}


class IntegrationSuitesTestCase(unittest.TestCase):
    """Permission-retrieval and self-eval are first-class suite cards, built only
    from the real eval_runner results passed in -- absent input => absent card."""

    def _suites(self, perm=PERM, selfeval=SELF):
        out = _build(_retrieval(), _routing(), agent_decision=AD_SECTION, eval_inputs=INPUTS,
                     permission=perm, self_eval_result=selfeval)
        return out, {s["key"]: s for s in out["suites"]}

    def test_cards_present_with_required_fields_and_real_thresholds(self):
        out, suites = self._suites()
        self.assertEqual([s["key"] for s in out["suites"]][-2:], ["permission", "self-eval"])
        for key in ("permission", "self-eval"):
            for f in ("score", "threshold", "passed", "dataset_hash", "commit_sha", "run_at", "kind", "note"):
                self.assertIsNotNone(suites[key][f], f"{key}.{f}")
        self.assertEqual(suites["permission"]["threshold"], eval_runner.PERMISSION_THRESHOLDS["permission_pass_rate"])
        self.assertEqual(suites["self-eval"]["threshold"], eval_runner.SELF_EVAL_THRESHOLDS["catch_rate"])
        self.assertEqual([m["key"] for m in suites["self-eval"]["metrics"]],
                         ["self_eval_catch_rate", "self_eval_good_pass_rate"])
        self.assertEqual(suites["self-eval"]["score"], 0.9)

    def test_dataset_hashes_come_from_the_committed_datasets(self):
        _, suites = self._suites()
        self.assertEqual(suites["permission"]["dataset_hash"], INPUTS["files"]["agent/evals/permission_dataset.json"])
        self.assertEqual(suites["self-eval"]["dataset_hash"], INPUTS["files"]["agent/evals/self_eval_dataset.json"])

    def test_one_leak_fails_the_permission_card_and_overall(self):
        perm = {"summary": {"cases": 10, "passed": 9, "leaks_or_failures": 1}, "per_case": []}
        out, suites = self._suites(perm=perm)
        self.assertEqual(suites["permission"]["score"], 0.9)
        self.assertFalse(suites["permission"]["passed"])
        self.assertFalse(out["overall_passed"])

    def test_low_catch_rate_fails_self_eval_card(self):
        out, suites = self._suites(selfeval={"summary": {"cases": 20, "catch_rate": 0.5, "good_pass_rate": 1.0}, "per_case": []})
        self.assertFalse(suites["self-eval"]["passed"])
        self.assertFalse(out["overall_passed"])

    def test_absent_inputs_mean_no_card_not_a_made_up_one(self):
        out = _build(_retrieval(), _routing(), agent_decision=AD_SECTION, eval_inputs=INPUTS)
        self.assertNotIn("permission", [s["key"] for s in out["suites"]])
        self.assertNotIn("self-eval", [s["key"] for s in out["suites"]])


class SuitesTestCase(unittest.TestCase):
    def _suites(self, retrieval=None, routing=None, ad=AD_SECTION):
        out = _build(retrieval or _retrieval(), routing or _routing(), agent_decision=ad, eval_inputs=INPUTS)
        return out, {s["key"]: s for s in out["suites"]}

    def test_four_first_class_suites_with_required_fields(self):
        out, suites = self._suites()
        self.assertEqual([s["key"] for s in out["suites"]],
                         ["retrieval", "routing", "security-routing", "agent-decision"])
        for s in out["suites"]:
            for f in ("score", "threshold", "passed", "dataset_hash", "commit_sha", "run_at", "kind"):
                self.assertIn(f, s)
                self.assertIsNotNone(s[f], f"{s['key']}.{f}")
            self.assertEqual(s["threshold"], eval_runner.THRESHOLDS[s["primary_metric"]])

    def test_dataset_hashes_come_from_eval_inputs_and_security_shares_routing(self):
        _, suites = self._suites()
        self.assertEqual(suites["retrieval"]["dataset_hash"], INPUTS["files"]["agent/evals/retrieval_dataset.json"])
        self.assertEqual(suites["routing"]["dataset_hash"], INPUTS["files"]["agent/evals/routing_dataset.json"])
        self.assertEqual(suites["security-routing"]["dataset_hash"], suites["routing"]["dataset_hash"])
        self.assertEqual(suites["agent-decision"]["dataset_hash"],
                         INPUTS["files"]["agent/evals/agent_decision_dataset.json"])

    def test_agent_decision_is_recorded_with_its_own_commit_and_time(self):
        _, suites = self._suites()
        ad = suites["agent-decision"]
        self.assertEqual((ad["kind"], ad["commit_sha"], ad["run_at"]), ("recorded", "d" * 40, AD_SECTION["run_at_utc"]))
        self.assertEqual(suites["retrieval"]["kind"], "measured")
        self.assertEqual(suites["retrieval"]["commit_sha"], "abc1234")

    def test_retrieval_suite_carries_mrr_and_fails_if_either_metric_misses(self):
        _, suites = self._suites(retrieval=_retrieval(mrr=0.1))
        self.assertEqual([m["key"] for m in suites["retrieval"]["metrics"]], ["recall_at_3", "mrr"])
        self.assertFalse(suites["retrieval"]["passed"])

    def test_security_routing_suite_is_zero_tolerance(self):
        _, suites = self._suites(routing=_routing(sec=0.857))
        self.assertFalse(suites["security-routing"]["passed"])
        self.assertTrue(suites["routing"]["passed"])

    def test_agent_decision_miss_fails_suite_and_overall(self):
        ad = dict(AD_SECTION, summary={"PASS": 5, "FAIL": 0, "NOT_EXECUTED": 1, "UNKNOWN": 0})
        out, suites = self._suites(ad=ad)
        self.assertEqual(suites["agent-decision"]["score"], 0.833)
        self.assertFalse(suites["agent-decision"]["passed"])
        self.assertFalse(out["overall_passed"])

    def test_overall_verdict_matches_eval_runner_gate_including_agent_decision(self):
        for passes in (6, 5, 0):
            ad = dict(AD_SECTION, summary={"PASS": passes, "FAIL": 6 - passes, "NOT_EXECUTED": 0, "UNKNOWN": 0})
            replay = {"summary": {"agent_decision_pass_rate": round(passes / 6, 3)},
                      "per_case": [{"id": "x", "verdict": "PASS", "passed": True}]}
            with contextlib.redirect_stdout(io.StringIO()):
                gate = eval_runner._print_report(_retrieval(), _routing(), replay)
            self.assertEqual(_build(_retrieval(), _routing(), agent_decision=ad)["overall_passed"], gate)

    def test_no_hashes_means_null_not_invented(self):
        out = _build(_retrieval(), _routing(), agent_decision=AD_SECTION)
        self.assertTrue(all(s["dataset_hash"] is None for s in out["suites"]))
        self.assertIsNone(out["reproducibility"]["inputs_hash"])


class ReproducibilityTestCase(unittest.TestCase):
    def test_command_and_hash_present(self):
        r = pub.build_reproducibility(INPUTS)
        self.assertEqual(r["command"], "python eval_runner.py all")
        self.assertRegex(r["inputs_hash"], r"^[0-9a-f]{64}$")
        self.assertIn("eval_runner.THRESHOLDS", r["hash_covers"])
        self.assertIn("agent/eval_runner.py", r["hash_covers"])

    def test_hash_changes_with_any_input_or_threshold(self):
        base = pub.inputs_hash(INPUTS)
        f = dict(INPUTS["files"]); f["agent/evals/routing_dataset.json"] = "x" * 64
        self.assertNotEqual(base, pub.inputs_hash({"files": f, "thresholds": INPUTS["thresholds"]}))
        self.assertNotEqual(base, pub.inputs_hash({"files": INPUTS["files"], "thresholds": "u" * 64}))
        self.assertEqual(base, pub.inputs_hash(json.loads(json.dumps(INPUTS))))


class HistoryTestCase(unittest.TestCase):
    def test_filename_is_timestamp_dash_commit(self):
        e = {"generated_at": "2026-10-06T10:07:23Z", "commit_sha": "674958abf3ff8437"}
        self.assertEqual(pub.history_filename(e), "20261006T100723Z-674958a.json")
        e = {"generated_at": "2026-09-16T09:46:39.181896+00:00", "commit_sha": "983161fa"}
        self.assertEqual(pub.history_filename(e), "20260916T094639Z-983161f.json")

    def test_v1_snapshot_yields_null_for_what_it_never_recorded(self):
        v1 = _build(_retrieval(), _routing())
        for k in ("suites", "reproducibility"):
            v1.pop(k)
        v1["schema_version"] = 1
        e = pub.history_entry(v1)
        self.assertEqual([s["key"] for s in e["suites"]], ["retrieval", "routing", "security-routing"])
        self.assertTrue(all(s["dataset_hash"] is None for s in e["suites"]))
        self.assertIsNone(e["reproducibility_hash"])

    def test_v1_snapshot_agent_decision_has_no_threshold_or_verdict(self):
        v1 = _build(_retrieval(), _routing(), agent_decision=AD_SECTION)
        v1.pop("suites")
        v1["metrics"] = [m for m in v1["metrics"] if m["key"] != "agent_decision_pass_rate"]
        ad = pub.history_entry(v1)["suites"][-1]
        self.assertEqual((ad["key"], ad["score"], ad["threshold"], ad["passed"]), ("agent-decision", 1.0, None, None))

    def test_agent_decision_only_entry_counts_not_executed_as_not_passed(self):
        res = {"run_at_utc": "2026-09-15T19:05:40+00:00", "results": [{"verdict": "NOT_EXECUTED"}] * 6}
        e = pub.agent_decision_history_entry(res, "{}", "a" * 40)
        s = e["suites"][0]
        self.assertEqual((s["score"], s["passed"], s["threshold"]), (0.0, None, None))
        self.assertEqual(s["verdict_counts"], {"NOT_EXECUTED": 6})
        self.assertIsNone(e["overall_passed"])

    def test_write_and_index_roundtrip_sorted_oldest_first(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for ts in ("2026-10-06T10:00:00Z", "2026-09-01T10:00:00Z"):
                e = pub.history_entry(_build(_retrieval(), _routing()))
                e["generated_at"] = ts
                pub.write_history_entry(e, d)
            idx = pub.rebuild_history_index(d)
        self.assertEqual([e["generated_at"] for e in idx["entries"]],
                         ["2026-09-01T10:00:00Z", "2026-10-06T10:00:00Z"])
        self.assertTrue(all(e["file"].endswith("-abc1234.json") for e in idx["entries"]))


class CommittedHistoryTestCase(unittest.TestCase):
    """The committed eval-history/ directory. Files only; nothing measured."""

    def setUp(self):
        self.index = json.loads(pub.HISTORY_INDEX.read_text(encoding="utf-8"))
        self.snapshot = json.loads(pub.OUTPUT_PATH.read_text(encoding="utf-8"))

    def test_index_matches_files_on_disk(self):
        on_disk = sorted(f.name for f in pub.HISTORY_DIR.glob("*.json") if f.name != "index.json")
        self.assertEqual(sorted(e["file"] for e in self.index["entries"]), on_disk)
        for e in self.index["entries"]:
            rec = json.loads((pub.HISTORY_DIR / e["file"]).read_text(encoding="utf-8"))
            self.assertEqual(dict(rec, file=e["file"]), e)
            self.assertEqual(e["file"], pub.history_filename(e))

    def test_history_has_multiple_runs_and_is_chronological(self):
        times = [e["generated_at"] for e in self.index["entries"]]
        self.assertGreaterEqual(len(times), 3)
        self.assertEqual(times, sorted(times))
        self.assertEqual(len(set(times)), len(times))

    def test_every_seeded_record_traces_to_a_real_git_commit_and_values_match_it(self):
        import subprocess
        for e in self.index["entries"]:
            if not e["source"].startswith("git:"):
                continue
            commit, rel = e["source"][4:].split(":", 1)
            full = subprocess.run(["git", "rev-parse", "--verify", commit + "^{commit}"], cwd=pub.REPO_ROOT,
                                  capture_output=True, text=True)
            self.assertEqual(full.returncode, 0, e["source"])
            blob = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=pub.REPO_ROOT,
                                  capture_output=True, text=True, check=True).stdout
            if rel.endswith("eval-results.json"):
                self.assertEqual(pub.history_entry(json.loads(blob), source=e["source"]),
                                 {k: v for k, v in e.items() if k != "file"})
            else:
                res = json.loads(blob)
                self.assertEqual(e["generated_at"], res["run_at_utc"])
                self.assertEqual(e["suites"][0]["score"],
                                 round(sum(r["verdict"] == "PASS" for r in res["results"]) / len(res["results"]), 3))

    def test_latest_snapshot_is_in_history_with_matching_values(self):
        match = [e for e in self.index["entries"]
                 if e["generated_at"] == self.snapshot["generated_at"] and e["commit_sha"] == self.snapshot["commit_sha"]]
        self.assertEqual(len(match), 1)
        self.assertEqual(match[0]["reproducibility_hash"], self.snapshot["reproducibility"]["inputs_hash"])
        for s in self.snapshot["suites"]:
            h = next(x for x in match[0]["suites"] if x["key"] == s["key"])
            self.assertEqual((h["score"], h["threshold"], h["passed"], h["dataset_hash"], h["commit_sha"], h["run_at"]),
                             (s["score"], s["threshold"], s["passed"], s["dataset_hash"], s["commit_sha"], s["run_at"]))

    def test_published_suites_hashes_and_repro_hash_match_files_on_disk(self):
        cur = pub.compute_eval_input_hashes()
        by = {s["key"]: s for s in self.snapshot["suites"]}
        self.assertEqual(by["retrieval"]["dataset_hash"], cur["files"]["agent/evals/retrieval_dataset.json"])
        self.assertEqual(by["security-routing"]["dataset_hash"], cur["files"]["agent/evals/routing_dataset.json"])
        self.assertEqual(self.snapshot["reproducibility"]["inputs_hash"], pub.inputs_hash(cur))

    def test_agent_decision_suite_equals_replay_of_committed_results(self):
        replay = eval_runner.run_agent_decision_eval()["summary"]
        ad = next(s for s in self.snapshot["suites"] if s["key"] == "agent-decision")
        self.assertEqual(ad["score"], replay["agent_decision_pass_rate"])
        self.assertEqual(ad["kind"], "recorded")

    def test_page_loads_history_and_has_dashboard_sections(self):
        js = (pub.AGENT_DIR / "web" / "eval.js").read_text(encoding="utf-8")
        self.assertIn("/eval-history/index.json", js)
        for honest in ("Misses are shown, not hidden", "No numbers are shown rather than invented ones",
                       "zero tolerance", "Honest limits", "uncommitted changes present"):
            self.assertIn(honest, js)


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
            self.assertEqual(m["threshold"], eval_runner.ALL_METRIC_THRESHOLDS[m["key"]])

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
