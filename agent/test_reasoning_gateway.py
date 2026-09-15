"""
Focused tests for agent/reasoning_gateway.py (Base Architecture V3, Phase
3): the one sanctioned boundary for a single-shot advisory model call.
Proves the directive's non-negotiable rules are real, not just claimed --
default-denied purpose gating, LLM_MODE=DISABLED honored with zero network
calls, and every result always carries authority="ADVISORY".

Run: python agent/test_reasoning_gateway.py
"""

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reasoning_gateway as rg


class _FakeUsage:
    def __init__(self, input_tokens=10, output_tokens=20):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = None
        self.cache_read_input_tokens = None


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_FakeTextBlock(text)] if text else []
        self.usage = _FakeUsage()
        self.stop_reason = stop_reason


class PurposeGatingTestCase(unittest.TestCase):
    def test_every_real_advisory_purpose_is_allowed_through_to_a_real_call(self):
        for purpose in rg.ADVISORY_PURPOSES:
            with self.subTest(purpose=purpose):
                create_fn = mock.Mock(return_value=_FakeResponse("real answer"))
                result = rg.call(purpose, "system", "user", 100, create_fn=create_fn)
                self.assertEqual(result["text"], "real answer")
                self.assertTrue(result["model_called"])
                create_fn.assert_called_once()

    def test_an_unrecognized_purpose_is_denied_before_any_network_call(self):
        """The core Phase 3 guarantee: default-denied, not default-allowed."""
        create_fn = mock.Mock(return_value=_FakeResponse("should never be reached"))
        result = rg.call("MAKE_ME_A_SANDWICH", "system", "user", 100, create_fn=create_fn)
        self.assertIsNone(result["text"])
        self.assertFalse(result["model_called"])
        self.assertIn("not in ADVISORY_PURPOSES", result["denial_reason"])
        create_fn.assert_not_called()

    def test_every_denial_and_success_result_carries_authority_advisory(self):
        """A caller must never be able to mistake this for authoritative
        output by its absence -- authority="ADVISORY" is on every path."""
        denied = rg.call("NOT_A_REAL_PURPOSE", "s", "u", 100, create_fn=mock.Mock())
        self.assertEqual(denied["authority"], "ADVISORY")

        allowed = rg.call(
            "HUMAN_EXPLANATION", "s", "u", 100,
            create_fn=mock.Mock(return_value=_FakeResponse("ok")),
        )
        self.assertEqual(allowed["authority"], "ADVISORY")


class ZeroLlmModeTestCase(unittest.TestCase):
    def test_llm_mode_disabled_makes_zero_network_calls(self):
        create_fn = mock.Mock(return_value=_FakeResponse("should never be reached"))
        with mock.patch.dict(os.environ, {"LLM_MODE": "DISABLED"}):
            result = rg.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=create_fn)
        self.assertIsNone(result["text"])
        self.assertFalse(result["model_called"])
        self.assertIn("LLM_MODE=DISABLED", result["denial_reason"])
        create_fn.assert_not_called()

    def test_llm_mode_disabled_is_case_insensitive_and_trims_whitespace(self):
        for value in ("disabled", " Disabled ", "DISABLED"):
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"LLM_MODE": value}):
                    self.assertTrue(rg.llm_mode_disabled())

    def test_llm_mode_unset_or_other_values_do_not_disable(self):
        for value in ("", "ENABLED", "disable"):  # "disable" != "disabled", deliberately not a fuzzy match
            with self.subTest(value=value):
                with mock.patch.dict(os.environ, {"LLM_MODE": value}):
                    self.assertFalse(rg.llm_mode_disabled())
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LLM_MODE", None)
            self.assertFalse(rg.llm_mode_disabled())


class MissingApiKeyTestCase(unittest.TestCase):
    def test_no_api_key_and_no_create_fn_is_an_honest_denial_not_a_crash(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            result = rg.call("HUMAN_EXPLANATION", "s", "u", 100, api_key=None, create_fn=None)
        self.assertIsNone(result["text"])
        self.assertFalse(result["model_called"])
        self.assertIn("ANTHROPIC_API_KEY not set", result["denial_reason"])


class EmptyModelResponseTestCase(unittest.TestCase):
    def test_extended_thinking_consuming_the_whole_budget_is_reported_honestly(self):
        """The exact real failure mode this logic was carried over from
        (agent/triage_execution.py, 2026-09-15): response.content can be
        only a ThinkingBlock with zero text blocks and
        stop_reason='max_tokens'. Must be a clear denial, never a silent
        empty string treated as success."""
        create_fn = mock.Mock(return_value=_FakeResponse(text=None, stop_reason="max_tokens"))
        result = rg.call("NOVEL_IMPLEMENTATION_PROPOSAL", "s", "u", 100, create_fn=create_fn)
        self.assertIsNone(result["text"])
        self.assertTrue(result["model_called"])  # a real call WAS made, unlike a denial
        self.assertIn("max_tokens", result["denial_reason"])


class ResponseTextExtractionTestCase(unittest.TestCase):
    def test_strips_a_markdown_code_fence_wrapper(self):
        create_fn = mock.Mock(return_value=_FakeResponse("```json\n{\"a\": 1}\n```"))
        result = rg.call("GENUINE_AMBIGUITY_ANALYSIS", "s", "u", 100, create_fn=create_fn)
        self.assertEqual(result["text"], '{"a": 1}')

    def test_plain_text_with_no_fence_is_returned_stripped(self):
        create_fn = mock.Mock(return_value=_FakeResponse("  hello world  \n"))
        result = rg.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=create_fn)
        self.assertEqual(result["text"], "hello world")


class UsageRecordingTestCase(unittest.TestCase):
    def test_real_usage_is_forwarded_to_metrics(self):
        import metrics
        metrics.reset()
        create_fn = mock.Mock(return_value=_FakeResponse("ok"))
        rg.call("HUMAN_EXPLANATION", "s", "u", 100, create_fn=create_fn)
        events = metrics.get_model_usage_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["input_tokens"], 10)
        self.assertEqual(events[0]["output_tokens"], 20)


if __name__ == "__main__":
    unittest.main()
