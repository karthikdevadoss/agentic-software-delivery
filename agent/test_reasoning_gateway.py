"""
Focused regression tests for agent/reasoning_gateway.py (Base Architecture
V3, Phase 3's central Reasoning Gateway) -- the one sanctioned boundary
for a single-shot advisory model call. agent/test_triage_execution.py
already exercises the gateway's real happy path indirectly (every
diagnose()/generate_candidate_patch() test with an injected create_fn
goes through reasoning_gateway.call()); this file tests the gateway
itself directly, including the denial paths that codebase doesn't
exercise (unknown purpose, LLM_MODE=DISABLED, missing API key).

Run: python agent/test_reasoning_gateway.py
"""

import os
import unittest
from unittest.mock import MagicMock, patch

import reasoning_gateway as rg


def _fake_response(text: str, stop_reason: str = "end_turn"):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = stop_reason
    response.usage = MagicMock(
        input_tokens=10, output_tokens=5,
        cache_creation_input_tokens=None, cache_read_input_tokens=None,
    )
    return response


class PurposeAllowlistTestCase(unittest.TestCase):
    def test_unknown_purpose_is_denied_before_any_network_call(self):
        create_fn = MagicMock()
        result = rg.call(
            purpose="DO_ANYTHING_I_WANT", system_prompt="s", user_message="u",
            max_tokens=100, create_fn=create_fn,
        )
        self.assertIsNone(result["text"])
        self.assertFalse(result["model_called"])
        self.assertEqual(result["authority"], "ADVISORY")
        self.assertIn("not in ADVISORY_PURPOSES", result["denial_reason"])
        create_fn.assert_not_called()

    def test_every_real_call_site_purpose_is_a_real_advisory_purpose(self):
        # Guards against a future call site introducing a typo'd purpose
        # string that would silently always be denied.
        for purpose in ("NOVEL_ROOT_CAUSE_HYPOTHESES", "NOVEL_IMPLEMENTATION_PROPOSAL"):
            self.assertIn(purpose, rg.ADVISORY_PURPOSES)


class LlmModeDisabledTestCase(unittest.TestCase):
    def test_llm_mode_disabled_makes_zero_network_calls(self):
        create_fn = MagicMock()
        with patch.dict(os.environ, {"LLM_MODE": "DISABLED"}):
            result = rg.call(
                purpose="NOVEL_ROOT_CAUSE_HYPOTHESES", system_prompt="s", user_message="u",
                max_tokens=100, create_fn=create_fn,
            )
        self.assertIsNone(result["text"])
        self.assertFalse(result["model_called"])
        self.assertIn("LLM_MODE=DISABLED", result["denial_reason"])
        create_fn.assert_not_called()

    def test_llm_mode_disabled_is_case_and_whitespace_insensitive(self):
        self.assertTrue(rg.llm_mode_disabled.__call__)  # sanity: real function, not a constant
        with patch.dict(os.environ, {"LLM_MODE": "  disabled  "}):
            self.assertTrue(rg.llm_mode_disabled())
        with patch.dict(os.environ, {"LLM_MODE": "enabled"}):
            self.assertFalse(rg.llm_mode_disabled())
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(rg.llm_mode_disabled())


class MissingApiKeyTestCase(unittest.TestCase):
    def test_no_create_fn_and_no_api_key_is_an_honest_denial_not_a_crash(self):
        with patch.dict(os.environ, {}, clear=True):
            result = rg.call(
                purpose="NOVEL_ROOT_CAUSE_HYPOTHESES", system_prompt="s", user_message="u",
                max_tokens=100, create_fn=None, api_key=None,
            )
        self.assertIsNone(result["text"])
        self.assertFalse(result["model_called"])
        self.assertIn("ANTHROPIC_API_KEY", result["denial_reason"])


class RealCallShapeTestCase(unittest.TestCase):
    def test_successful_call_returns_stripped_text_and_records_usage(self):
        create_fn = MagicMock(return_value=_fake_response("  hello world  "))
        with patch("metrics.record_model_usage") as mock_record:
            result = rg.call(
                purpose="NOVEL_ROOT_CAUSE_HYPOTHESES", system_prompt="sys", user_message="usr",
                max_tokens=100, create_fn=create_fn,
            )
        self.assertEqual(result["text"], "hello world")
        self.assertTrue(result["model_called"])
        self.assertEqual(result["authority"], "ADVISORY")
        self.assertIsNone(result["denial_reason"])
        mock_record.assert_called_once()
        self.assertEqual(create_fn.call_args.kwargs["model"], "claude-sonnet-5")
        self.assertEqual(create_fn.call_args.kwargs["system"], "sys")

    def test_effort_kwarg_is_passed_through_as_output_config_when_given(self):
        create_fn = MagicMock(return_value=_fake_response("ok"))
        rg.call(
            purpose="NOVEL_IMPLEMENTATION_PROPOSAL", system_prompt="s", user_message="u",
            max_tokens=100, create_fn=create_fn, effort="low",
        )
        self.assertEqual(create_fn.call_args.kwargs["output_config"], {"effort": "low"})

    def test_no_effort_kwarg_omits_output_config(self):
        create_fn = MagicMock(return_value=_fake_response("ok"))
        rg.call(
            purpose="NOVEL_IMPLEMENTATION_PROPOSAL", system_prompt="s", user_message="u",
            max_tokens=100, create_fn=create_fn,
        )
        self.assertNotIn("output_config", create_fn.call_args.kwargs)

    def test_markdown_code_fence_is_stripped(self):
        create_fn = MagicMock(return_value=_fake_response("```java\npublic class X {}\n```"))
        result = rg.call(
            purpose="NOVEL_IMPLEMENTATION_PROPOSAL", system_prompt="s", user_message="u",
            max_tokens=100, create_fn=create_fn,
        )
        self.assertEqual(result["text"], "public class X {}")

    def test_empty_text_content_is_an_honest_denial_not_a_blank_success(self):
        # The real AEQ-class bug this project already hit once: extended
        # thinking can consume the whole max_tokens budget before any text
        # block appears -- content is real (a ThinkingBlock) but yields no
        # usable text. Must be a distinct, honest denial, not a silent "".
        response = MagicMock()
        response.content = []  # no text blocks at all
        response.stop_reason = "max_tokens"
        response.usage = MagicMock(
            input_tokens=1, output_tokens=1,
            cache_creation_input_tokens=None, cache_read_input_tokens=None,
        )
        create_fn = MagicMock(return_value=response)
        result = rg.call(
            purpose="NOVEL_ROOT_CAUSE_HYPOTHESES", system_prompt="s", user_message="u",
            max_tokens=100, create_fn=create_fn,
        )
        self.assertIsNone(result["text"])
        self.assertTrue(result["model_called"])  # a real call WAS made, unlike the denial cases above
        self.assertIn("max_tokens", result["denial_reason"])

    def test_authority_is_always_the_literal_string_advisory(self):
        # Every branch -- denial or success -- must carry this, so a
        # caller can never mistake a result for authoritative by omission.
        create_fn = MagicMock(return_value=_fake_response("ok"))
        success = rg.call(purpose="HUMAN_EXPLANATION", system_prompt="s", user_message="u",
                           max_tokens=10, create_fn=create_fn)
        denial = rg.call(purpose="NOT_A_REAL_PURPOSE", system_prompt="s", user_message="u",
                          max_tokens=10, create_fn=create_fn)
        self.assertEqual(success["authority"], "ADVISORY")
        self.assertEqual(denial["authority"], "ADVISORY")


if __name__ == "__main__":
    unittest.main()
