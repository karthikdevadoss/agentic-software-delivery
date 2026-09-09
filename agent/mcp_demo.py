"""
MCP verification demo (Phase A, requirement #8): proves an independent
MCP client — not our own direct-tool-calling agent_loop.py — can discover
and invoke the repository tools exposed by mcp_server.py over the real MCP
protocol, using the official SDK's in-process Client (no subprocess/socket
needed for this local verification; the same Client class works identically
over stdio/streamable-http for a real remote client).

Run: python agent/mcp_demo.py
"""

import asyncio

from mcp import Client

from mcp_server import mcp


async def main():
    async with Client(mcp) as client:
        tools_result = await client.list_tools()
        tool_list = tools_result.tools if hasattr(tools_result, "tools") else tools_result
        print(f"Discovered {len(tool_list)} tools via MCP:")
        for t in tool_list:
            print(f"  - {t.name}: {t.description[:70]}...")

        print()
        print("Invoking list_repository_files(app/src/main/java) via MCP client:")
        result = await client.call_tool("list_repository_files", {"directory": "app/src/main/java"})
        print(result.content[0].text)

        print()
        print("Invoking semantic_repository_search via MCP client:")
        result = await client.call_tool(
            "semantic_repository_search", {"query": "customer email validation", "top_k": 3}
        )
        print(result.content[0].text)

        print()
        print("Invoking a deliberately unsafe path via MCP client (must fail safely):")
        result = await client.call_tool("read_file", {"path": "../../etc/passwd"})
        if result.is_error:
            print(f"  correctly rejected: {result.content[0].text}")
        else:
            print("  UNEXPECTED: call succeeded — this should have been rejected")


if __name__ == "__main__":
    asyncio.run(main())
