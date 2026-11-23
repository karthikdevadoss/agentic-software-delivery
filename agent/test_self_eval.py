"""
Hermetic tests for agent/self_eval.py and the self-eval suite in eval_runner.py.
No model, no network, no API key. Dataset records are hand-written FIXTURES.

Run: python agent/test_self_eval.py
"""

import json
import unittest
from unittest import mock

import eval_runner as er
import self_eval as se

EV = [{"path": "agent/execution_tools.py", "text": "approval gate defaults to REJECT"}]
Q = "Where is the approval gate implemented?"
GOOD = "The approval gate is implemented in agent/execution_tools.py."
BAD_PATH = "The approval gate is implemented in agent/nonexistent_gate.py."


class ScorerTestCase(unittest.TestCase):
    def test_good_passes(self):
        self.assertTrue(se.self_evaluate(Q, EV, GOOD)["passed"])

    def test_invented_path_fails_hard(self):
        r = se.self_evaluate(Q, EV, BAD_PATH)
        self.assertFalse(r["passed"])
        self.assertIn("no_invented_paths", r["hard_failed"])

    def test_policy_violation_fails(self):
        r = se.self_evaluate(Q, EV, GOOD + " Then bypass the approval gate.")
        self.assertIn("no_policy_violation", r["hard_failed"])

    def test_uncited_fails(self):
        self.assertIn("grounded", se.self_evaluate(Q, EV, "It is implemented in the approval gate.")["hard_failed"])

    def test_off_topic_fails_floor(self):
        r = se.self_evaluate("Which metrics does retrieval compute?", EV, "See agent/execution_tools.py.")
        self.assertIn("answers_question", r["hard_failed"])

    def test_verdict_rejects_missing_criteria(self):
        with self.assertRaises(ValueError):
            se.verdict({"grounded": 1.0})


class GateTestCase(unittest.TestCase):
    def test_pass_continues_without_retry(self):
        calls = []
        r = se.run_with_self_eval(lambda fb: calls.append(fb) or GOOD, Q, EV)
        self.assertEqual((r["action"], len(calls)), ("CONTINUE", 1))

    def test_retry_once_then_recovers_with_feedback(self):
        seen = []
        def produce(fb):
            seen.append(fb)
            return BAD_PATH if fb is None else GOOD
        r = se.run_with_self_eval(produce, Q, EV)
        self.assertEqual(r["action"], "CONTINUE")
        self.assertEqual(len(seen), 2)
        self.assertIn("nonexistent_gate.py", seen[1])

    def test_still_bad_after_one_retry_escalates_and_stops(self):
        calls = []
        r = se.run_with_self_eval(lambda fb: calls.append(fb) or BAD_PATH, Q, EV)
        self.assertEqual(r["action"], "ESCALATE_TO_HUMAN")
        self.assertEqual(len(calls), 2)  # exactly one retry, then stop

    def test_zero_retries_refuses_immediately(self):
        calls = []
        r = se.run_with_self_eval(lambda fb: calls.append(fb) or BAD_PATH, Q, EV, max_retries=0)
        self.assertEqual((r["action"], len(calls)), ("ESCALATE_TO_HUMAN", 1))

    def test_gate_never_touches_execution_tools(self):
        import execution_tools
        with mock.patch.object(execution_tools, "dispatch_execution_tool_call") as d:
            se.run_with_self_eval(lambda fb: BAD_PATH, Q, EV)
            d.assert_not_called()


class JudgePlumbingTestCase(unittest.TestCase):
    OK = json.dumps({"scores": {c: 1.0 for c in se.CRITERIA}, "reason": "fine"})

    def test_prompt_contains_rubric_and_inputs(self):
        p = se.build_judge_prompt(Q, EV, GOOD)
        for c in se.CRITERIA:
            self.assertIn(c, p)
        self.assertIn(Q, p)

    def test_parse_ok_and_injected_scorer(self):
        self.assertTrue(se.self_evaluate(Q, EV, GOOD, scorer=se.make_model_scorer(lambda p: "x " + self.OK))["passed"])

    def test_parse_rejects_malformed(self):
        for bad in ["no json", '{"scores": {}}', json.dumps({"scores": {**{c: 1 for c in se.CRITERIA}, "grounded": 2}}),
                    json.dumps({"scores": {**{c: 1 for c in se.CRITERIA}, "grounded": True}})]:
            with self.assertRaises(ValueError):
                se.parse_judge_response(bad)


class SelfEvalSuiteTestCase(unittest.TestCase):
    def test_dataset_is_labelled_fixtures_with_both_labels(self):
        d = er._load_dataset("self_eval_dataset.json")
        self.assertTrue(all(c["fixture"] for c in d["cases"]))
        self.assertGreaterEqual(sum(c["expected_verdict"] == "FAIL" for c in d["cases"]), 5)
        self.assertGreaterEqual(sum(c["expected_verdict"] == "PASS" for c in d["cases"]), 4)

    def test_suite_meets_thresholds(self):
        self.assertTrue(er.self_eval_passed(er.run_self_eval()))

    def test_always_pass_mutation_fails_the_suite(self):
        always_pass = lambda q, e, o: {"scores": {c: 1.0 for c in se.CRITERIA}, "reason": "mutant"}
        with mock.patch.object(se, "deterministic_scorer", always_pass), \
             mock.patch.object(se, "self_evaluate", lambda q, e, o, scorer=always_pass, threshold=se.PASS_THRESHOLD:
                               {**always_pass(q, e, o), **se.verdict(always_pass(q, e, o)["scores"])}):
            res = er.run_self_eval()
        self.assertLess(res["summary"]["catch_rate"], er.SELF_EVAL_THRESHOLDS["catch_rate"])
        self.assertFalse(er.self_eval_passed(res))


if __name__ == "__main__":
    unittest.main()
