"""
Focused check: a Claude Sonnet 5 response containing a thinking block
followed by a tool_use block must survive the agent loop's message-passing
unmodified, and text/tool_use extraction must not assume content[0] is text.

Run directly: python agent/test_agent_loop.py
"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

import reasoning_gateway

import agent_loop
from agent_loop import _extract_text_blocks, _extract_tool_use_blocks


def _thinking_block():
    return SimpleNamespace(type="thinking", thinking="reasoning about the ticket...")


def _tool_use_block(tool_id="tool_1", name="read_file", tool_input=None):
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=tool_input or {"path": "x"})


def _text_block(text="final plan text"):
    return SimpleNamespace(type="text", text=text)


class ThinkingBlockPassthroughTest(unittest.TestCase):
    def test_assistant_turn_preserves_all_blocks_unfiltered(self):
        # content[0] is deliberately a thinking block, not text — this is
        # what Sonnet 5 returns by default while it is also requesting a tool.
        content = [_thinking_block(), _tool_use_block()]
        messages = []
        messages.append({"role": "assistant", "content": content})

        stored = messages[-1]["content"]
        self.assertIs(stored, content, "assistant content must be stored unmodified, not rebuilt")
        self.assertEqual([b.type for b in stored], ["thinking", "tool_use"])

    def test_tool_use_extraction_does_not_assume_content0_is_text(self):
        content = [_thinking_block(), _tool_use_block(name="search_code")]
        tool_uses = _extract_tool_use_blocks(content)
        self.assertEqual(len(tool_uses), 1)
        self.assertEqual(tool_uses[0].name, "search_code")

    def test_text_extraction_skips_thinking_and_tool_use_blocks(self):
        content = [_thinking_block(), _tool_use_block(), _text_block("hello")]
        text = "".join(_extract_text_blocks(content))
        self.assertEqual(text, "hello")

    def test_text_extraction_handles_multiple_text_blocks_in_order(self):
        content = [_thinking_block(), _text_block("part1 "), _text_block("part2")]
        text = "".join(_extract_text_blocks(content))
        self.assertEqual(text, "part1 part2")


def _resp(content, stop="end_turn"):
    return SimpleNamespace(
        content=content, stop_reason=stop,
        usage=SimpleNamespace(input_tokens=1, output_tokens=2,
                              cache_creation_input_tokens=None, cache_read_input_tokens=None))


class AgentLoopRoutesThroughGatewayTest(unittest.TestCase):
    def test_every_request_goes_through_gateway_converse_and_replays_blocks(self):
        t1 = [_thinking_block(), _tool_use_block()]
        responses = [_resp(t1, "tool_use"), _resp([_text_block("the plan")])]
        create_fn = mock.Mock(side_effect=responses)
        real = reasoning_gateway.converse
        with mock.patch.object(reasoning_gateway, "converse", wraps=real) as spy:
            out = agent_loop.run_agent_loop(
                "ticket", "k", dispatch_fn=lambda n, i: ("file body", False), create_fn=create_fn)
        self.assertEqual(out, "the plan")
        self.assertEqual(spy.call_count, 2)
        self.assertEqual(spy.call_args.kwargs["purpose"], agent_loop.GATEWAY_PURPOSE)
        self.assertIn(agent_loop.GATEWAY_PURPOSE, reasoning_gateway.ADVISORY_PURPOSES)
        # The exact assistant content list (thinking included) is replayed.
        second_messages = create_fn.call_args_list[1].kwargs["messages"]
        self.assertIs(second_messages[1]["content"], t1)
        self.assertEqual(second_messages[2]["content"][0]["type"], "tool_result")

    def test_kill_switch_means_zero_anthropic_calls_and_an_honest_string(self):
        with mock.patch.dict(os.environ, {"LLM_MODE": "DISABLED", "ANTHROPIC_API_KEY": "k"}), \
                mock.patch("anthropic.Anthropic") as cls:
            out = agent_loop.run_agent_loop("ticket", "k")
        cls.assert_not_called()
        self.assertIn("LLM_MODE=DISABLED", out)
        self.assertTrue(out.startswith("Unable to produce a plan"))

    def test_injected_create_fn_never_records_usage(self):
        import metrics
        metrics.reset()
        agent_loop.run_agent_loop("t", "k", create_fn=mock.Mock(return_value=_resp([_text_block("p")])))
        self.assertEqual(metrics.get_model_usage_events(), [])


if __name__ == "__main__":
    unittest.main()
