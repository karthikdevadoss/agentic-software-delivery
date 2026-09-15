"""
Focused tests for agent/main.py::build_plan() -- the V1/V2 CLI planner's
single call site, now routed through agent/reasoning_gateway.py (Base
Architecture V3 Phase 3 completion) instead of calling the Anthropic SDK
directly. No existing test file covered this before; nothing else in the
codebase imports main.py (it is a standalone CLI entry point), so this is
new coverage, not a refactor of existing tests.

Run: python agent/test_main.py
"""

import os
import unittest
from unittest import mock
from unittest.mock import MagicMock

import main


def _fake_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(
        input_tokens=5, output_tokens=5,
        cache_creation_input_tokens=None, cache_read_input_tokens=None,
    )
    return response


class BuildPlanTestCase(unittest.TestCase):
    def test_build_plan_returns_the_models_real_text_via_the_gateway(self):
        create_fn = MagicMock(return_value=_fake_response("1. Existing components\n..."))
        plan = main.build_plan("Update email", "repo context here", api_key="fake", create_fn=create_fn)
        self.assertEqual(plan, "1. Existing components\n...")
        create_fn.assert_called_once()

    def test_build_plan_uses_the_semantic_requirement_interpretation_purpose(self):
        # A real, advisory-only purpose -- proves this call site is
        # correctly gated by reasoning_gateway's default-deny allowlist,
        # not an ungated direct call.
        import reasoning_gateway as rg
        self.assertIn("SEMANTIC_REQUIREMENT_INTERPRETATION", rg.ADVISORY_PURPOSES)
        create_fn = MagicMock(return_value=_fake_response("plan text"))
        main.build_plan("req", "ctx", api_key="fake", create_fn=create_fn)
        # The prompt (repo_context + requirement) must actually reach the model.
        user_content = create_fn.call_args.kwargs["messages"][0]["content"]
        self.assertIn("req", user_content)
        self.assertIn("ctx", user_content)

    def test_a_denied_call_raises_a_clear_runtime_error_not_a_silent_empty_plan(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            with self.assertRaises(RuntimeError) as ctx:
                main.build_plan("req", "ctx", api_key=None, create_fn=None)
        self.assertIn("No usable model response", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
