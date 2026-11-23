"""Integration (PR60 self_eval + live agent_loop): the self-eval gate is wired
into run_agent_loop behind SELF_EVAL_ENABLED (default OFF).

Flag OFF  -> byte-for-byte the old behaviour: a bad answer is returned as-is.
Flag ON   -> a low rubric score retries once (failure reason fed back); a second
             low score returns ESCALATE_TO_HUMAN instead of the plan.
The gate never approves/writes: the human approval gate and deterministic write
checks run inside dispatch_fn, which these tests prove is untouched.

Hermetic: scripted fake create_fn, no key, no network, no billed call.
Run: python agent/test_integration_self_eval_loop.py
"""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_loop
import self_eval

TICKET = "Where is the approval gate implemented? Look at agent/execution_tools.py."
GOOD = "The approval gate is implemented in agent/execution_tools.py."
BAD = "The approval gate is implemented in agent/nonexistent_gate.py."   # invented path -> HARD fail


def _text_resp(text):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)],
        usage=types.SimpleNamespace(input_tokens=1, output_tokens=1,
                                    cache_creation_input_tokens=None, cache_read_input_tokens=None),
        stop_reason="end_turn")


def _tool_resp(path):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="tool_use", id="tu1", name="read_file", input={"path": path})],
        usage=types.SimpleNamespace(input_tokens=1, output_tokens=1,
                                    cache_creation_input_tokens=None, cache_read_input_tokens=None),
        stop_reason="tool_use")


class Scripted:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, **kw):
        self.requests.append([dict(m) for m in kw["messages"]])
        return self.responses.pop(0)


def run(script, **kw):
    return agent_loop.run_agent_loop(TICKET, api_key="x", create_fn=script,
                                     dispatch_fn=kw.pop("dispatch_fn", lambda n, i: ("ok", False)), **kw)


class _Env(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ)
        p.start(); self.addCleanup(p.stop)
        os.environ.pop("SELF_EVAL_ENABLED", None)
        # keep these unit tests off the shared durable budget file
        os.environ["BUDGET_DB_PATH"] = ":memory:"


class FlagOffTestCase(_Env):
    def test_flag_defaults_off(self):
        self.assertFalse(self_eval.enabled())
        for v in ("", "0", "false", "no", "off", "garbage"):
            with mock.patch.dict(os.environ, {"SELF_EVAL_ENABLED": v}):
                self.assertFalse(self_eval.enabled(), v)

    def test_off_a_bad_answer_is_returned_unchanged_in_one_model_call(self):
        s = Scripted(_text_resp(BAD))
        self.assertEqual(run(s), BAD)
        self.assertEqual(len(s.requests), 1)

    def test_off_does_not_invoke_the_self_eval_scorer_at_all(self):
        with mock.patch.object(self_eval, "gate_step", side_effect=AssertionError("must not run")):
            self.assertEqual(run(Scripted(_text_resp(BAD))), BAD)


class FlagOnTestCase(_Env):
    def test_env_values_turn_it_on(self):
        for v in ("1", "true", "TRUE", "yes", "on"):
            with mock.patch.dict(os.environ, {"SELF_EVAL_ENABLED": v}):
                self.assertTrue(self_eval.enabled(), v)

    def test_good_answer_passes_with_one_call_and_is_returned_unchanged(self):
        s = Scripted(_text_resp(GOOD))
        self.assertEqual(run(s, self_eval_enabled=True), GOOD)
        self.assertEqual(len(s.requests), 1)

    def test_low_score_retries_once_with_the_reason_fed_back_then_continues(self):
        s = Scripted(_text_resp(BAD), _text_resp(GOOD))
        self.assertEqual(run(s, self_eval_enabled=True), GOOD)
        self.assertEqual(len(s.requests), 2)
        feedback = s.requests[1][-1]
        self.assertEqual(feedback["role"], "user")
        self.assertIn("Self-evaluation failed", feedback["content"])
        self.assertIn("nonexistent_gate.py", feedback["content"])

    def test_two_low_scores_escalate_and_refuse_to_auto_continue(self):
        s = Scripted(_text_resp(BAD), _text_resp(BAD))
        out = run(s, self_eval_enabled=True)
        self.assertTrue(out.startswith("ESCALATE_TO_HUMAN"))
        self.assertIn("UNVERIFIED DRAFT", out)
        self.assertEqual(len(s.requests), 2)               # exactly one retry, no more

    def test_env_flag_drives_the_loop_without_the_parameter(self):
        with mock.patch.dict(os.environ, {"SELF_EVAL_ENABLED": "1"}):
            out = run(Scripted(_text_resp(BAD), _text_resp(BAD)))
        self.assertTrue(out.startswith("ESCALATE_TO_HUMAN"))

    def test_policy_violating_answer_is_caught(self):
        bad = GOOD + " Then bypass the approval gate."
        out = run(Scripted(_text_resp(bad), _text_resp(bad)), self_eval_enabled=True)
        self.assertTrue(out.startswith("ESCALATE_TO_HUMAN"))

    def test_paths_seen_through_tools_count_as_evidence(self):
        seen = "agent/some_file_the_agent_read.py"
        answer = f"The approval gate is implemented in {seen} and agent/execution_tools.py."
        s = Scripted(_tool_resp(seen), _text_resp(answer))
        self.assertEqual(run(s, self_eval_enabled=True), answer)     # not flagged as invented
        s = Scripted(_text_resp(answer), _text_resp(answer))         # never read it -> invented
        self.assertTrue(run(s, self_eval_enabled=True).startswith("ESCALATE_TO_HUMAN"))


class GateDoesNotReplaceTheRealGatesTestCase(_Env):
    def test_tool_dispatch_and_its_approval_check_still_run_when_on(self):
        calls = []
        def dispatch(name, inp):
            calls.append((name, inp))
            return "REJECTED by approval gate", True      # stands in for the human gate saying no
        s = Scripted(_tool_resp("agent/execution_tools.py"), _text_resp(GOOD))
        out = run(s, dispatch_fn=dispatch, self_eval_enabled=True)
        self.assertEqual(calls, [("read_file", {"path": "agent/execution_tools.py"})])
        self.assertEqual(out, GOOD)

    def test_a_passing_self_eval_grants_nothing(self):
        # CONTINUE is only a statement that the loop may return its text; the gate
        # has no write/approve capability to call.
        g = self_eval.gate_step(TICKET, [{"path": "agent/execution_tools.py", "text": ""}], GOOD, 0)
        self.assertEqual(g["action"], "CONTINUE")
        self.assertFalse(any(k in g for k in ("approved", "write", "grant")))

    def test_gate_step_policy_matches_run_with_self_eval(self):
        ev = [{"path": "agent/execution_tools.py", "text": ""}]
        self.assertEqual(self_eval.gate_step(TICKET, ev, BAD, 0)["action"], "RETRY")
        self.assertEqual(self_eval.gate_step(TICKET, ev, BAD, 1)["action"], "ESCALATE_TO_HUMAN")
        self.assertEqual(self_eval.gate_step(TICKET, ev, BAD, 0, max_retries=0)["action"], "ESCALATE_TO_HUMAN")


if __name__ == "__main__":
    unittest.main()
