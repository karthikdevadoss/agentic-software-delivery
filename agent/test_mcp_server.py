"""
Focused automated tests for the MCP adapter (agent/mcp_server.py) — resolves
ACTION_QUEUE.json ACT-003 (MCP portion).

Uses the official mcp SDK's in-process Client (no subprocess/network) —
the same mechanism agent/mcp_demo.py uses for manual verification, now
automated and asserted.

Run: python agent/test_mcp_server.py
"""

import unittest
from unittest import mock

from mcp import Client

import tools
from mcp_server import mcp


class McpServerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_lists_all_four_tools(self):
        async with Client(mcp) as client:
            result = await client.list_tools()
            names = {t.name for t in result.tools}
        self.assertEqual(
            names,
            {"list_repository_files", "read_file", "search_code", "semantic_repository_search"},
        )

    async def test_invocation_returns_real_result(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "list_repository_files", {"directory": "app/src/main/java"}
            )
        self.assertFalse(result.is_error)
        self.assertIn("CustomerController.java", result.content[0].text)

    async def test_unsafe_path_rejected_safely_not_crashed(self):
        async with Client(mcp) as client:
            result = await client.call_tool("read_file", {"path": "../../etc/passwd"})
        self.assertTrue(result.is_error)
        self.assertIn("path traversal is not allowed", result.content[0].text)

    async def test_semantic_search_invocable_through_mcp(self):
        async with Client(mcp) as client:
            result = await client.call_tool(
                "semantic_repository_search", {"query": "customer email", "top_k": 2}
            )
        self.assertFalse(result.is_error)
        # Either real candidates, or the "no index" error surfaced safely —
        # both are valid outcomes depending on whether the index exists;
        # what must never happen is a crash, which async-with completing
        # without raising already proves.
        self.assertTrue(len(result.content[0].text) > 0)

    async def test_read_file_delegates_to_tools_not_reimplemented(self):
        """Proves mcp_server.py has no second path-security implementation —
        it must call straight into tools.read_file."""
        with mock.patch("tools.read_file", return_value="--- fake ---\nmocked") as mocked:
            async with Client(mcp) as client:
                result = await client.call_tool("read_file", {"path": "app/pom.xml"})
            mocked.assert_called_once_with("app/pom.xml")
        self.assertEqual(result.content[0].text, "--- fake ---\nmocked")

    async def test_search_code_delegates_to_tools_not_reimplemented(self):
        with mock.patch("tools.search_code", return_value="fake result") as mocked:
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "search_code", {"query": "email", "glob": "**/*.java"}
                )
            mocked.assert_called_once_with("email", "**/*.java")
        self.assertEqual(result.content[0].text, "fake result")

    async def test_mcp_error_surfaces_specific_reason_not_generic(self):
        """A RepoToolError's actual message must reach the client, not a
        generic 'error executing tool' with no detail."""
        async with Client(mcp) as client:
            result = await client.call_tool("read_file", {"path": ""})
        self.assertTrue(result.is_error)
        self.assertIn("path is required", result.content[0].text)


if __name__ == "__main__":
    unittest.main()
