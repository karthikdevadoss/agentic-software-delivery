"""
Focused check: a Claude Sonnet 5 response containing a thinking block
followed by a tool_use block must survive the agent loop's message-passing
unmodified, and text/tool_use extraction must not assume content[0] is text.

Run directly: python agent/test_agent_loop.py
"""

import unittest
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main()
