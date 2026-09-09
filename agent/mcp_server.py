"""
MCP adapter (Phase A) — exposes the existing read-only repository tools
through the Model Context Protocol (current stable spec: 2026-07-28) using
the official modelcontextprotocol/python-sdk (`mcp` package) — the Tier-1,
spec-owner implementation, chosen over the standalone `fastmcp` package
after empirically verifying it meets every requirement (see
docs/DECISIONS.md for the full comparison and why).

This file contains ZERO tool business logic of its own. Every tool below
is a thin wrapper that calls straight into tools.py — the exact same
path-security, redaction, and truncation logic used by the direct
Anthropic tool-calling agent (agent_loop.py) is reused here unchanged.
tools.RepoToolError is re-raised as mcp's ToolError so the *specific*
failure reason reaches the calling client, not a generic "tool failed".

Local dev/demo: run with stdio (the default transport) — matches how
Claude Desktop/Claude Code and other local MCP clients connect.
    python agent/mcp_server.py

Future hosted multi-tenant platform: the 2026-07-28 spec's Streamable HTTP
transport is now stateless (no more Mcp-Session-Id / sticky sessions), so
it can run behind an ordinary load balancer without per-server state:
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
(not started by default here — parameterize when actually hosting; legacy
SSE transport is still available in this SDK for backward compatibility
with older clients, via mcp.run(transport="sse"), but Streamable HTTP is
the current recommended choice for new hosted deployments, not SSE.)

Read-only, no write/build/deploy tools are exposed here by design.
"""

import time

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import tools
import metrics

mcp = MCPServer("agentic-software-delivery-repo-tools")


def _call(name, fn, *args):
    start = time.monotonic()
    try:
        result = fn(*args)
        metrics.record_tool_call(
            tool=name, input_summary=str(args), success=True,
            duration_ms=round((time.monotonic() - start) * 1000, 1),
            result_size=len(result),
        )
        return result
    except tools.RepoToolError as exc:
        metrics.record_tool_call(
            tool=name, input_summary=str(args), success=False,
            duration_ms=round((time.monotonic() - start) * 1000, 1),
            result_size=0, blocked_unsafe=metrics.is_security_block(str(exc)),
        )
        raise ToolError(str(exc))


@mcp.tool()
def list_repository_files(directory: str = ".") -> str:
    """List files under a repository-relative directory (default: repo root)."""
    return _call("list_repository_files", tools.list_repository_files, directory)


@mcp.tool()
def read_file(path: str) -> str:
    """Read the text contents of one repository file by its repo-relative path."""
    return _call("read_file", tools.read_file, path)


@mcp.tool()
def search_code(query: str, glob: str = "**/*.java") -> str:
    """Case-insensitive literal substring search across repository source files."""
    return _call("search_code", tools.search_code, query, glob)


@mcp.tool()
def semantic_repository_search(query: str, top_k: int = 5) -> str:
    """Semantic search over an index of repository files/docs. Candidates only —
    confirm with read_file/search_code before relying on results."""
    return _call("semantic_repository_search", tools.semantic_repository_search, query, top_k)


if __name__ == "__main__":
    mcp.run()
