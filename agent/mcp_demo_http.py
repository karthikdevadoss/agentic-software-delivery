"""
MCP streamable-http transport verification (ACT-005 / BL-011).

Unlike mcp_demo.py (which proves the MCP protocol itself works, using the
SDK's in-process Client -- no real network involved), this proves the
STREAMABLE HTTP TRANSPORT specifically: spawns agent/mcp_server.py as a
real separate OS process bound to a real localhost port, then connects
with a real HTTP-based MCP client (mcp.client.streamable_http) -- the
same code path a genuinely remote client would use. Never previously run;
only coded/documented before this (see docs/ACTION_QUEUE.json's ACT-005).

Run: python agent/mcp_demo_http.py
"""

import asyncio
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

HOST = "127.0.0.1"
PORT = 8791
URL = f"http://{HOST}:{PORT}/mcp"


def _wait_for_server(timeout_s: float = 15.0) -> bool:
    """Polls the real port until the server responds to *something* (even a
    protocol-level 4xx counts -- we only need the TCP/HTTP server to be up,
    the real MCP handshake happens over the real client below)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1.0)
            return True
        except urllib.error.HTTPError:
            return True  # server is up and answering HTTP, just not with GET
        except Exception:
            time.sleep(0.3)
    return False


async def _run_over_real_http():
    async with streamable_http_client(URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init_result = await session.initialize()
            print(f"Real MCP handshake over real HTTP succeeded: server={init_result.server_info.name!r} "
                  f"protocolVersion={init_result.protocol_version!r}")

            tools_result = await session.list_tools()
            print(f"Discovered {len(tools_result.tools)} tools via real HTTP MCP client:")
            for t in tools_result.tools:
                print(f"  - {t.name}")

            print()
            print("Invoking list_repository_files(docs) over real HTTP:")
            result = await session.call_tool("list_repository_files", {"directory": "docs"})
            print(result.content[0].text[:300])

            print()
            print("Invoking a deliberately unsafe path over real HTTP (must fail safely):")
            result = await session.call_tool("read_file", {"path": "../../etc/passwd"})
            if result.is_error:
                print(f"  correctly rejected: {result.content[0].text}")
            else:
                raise AssertionError("UNEXPECTED: call succeeded over real HTTP -- security boundary did not hold")


def main():
    env = dict(os.environ)
    env["MCP_TRANSPORT"] = "streamable-http"
    env["MCP_HOST"] = HOST
    env["MCP_PORT"] = str(PORT)

    server_proc = subprocess.Popen(
        [sys.executable, "mcp_server.py"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        if not _wait_for_server():
            server_proc.terminate()
            out, _ = server_proc.communicate(timeout=5)
            raise SystemExit(f"Real MCP streamable-http server never came up on {URL}. Server output:\n{out}")

        asyncio.run(_run_over_real_http())
        print()
        print("REAL, VERIFIED: the streamable-http transport works end-to-end over an actual HTTP connection "
              "to a separate OS process -- not just coded/documented (closes ACT-005 / BL-011).")
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()


if __name__ == "__main__":
    main()
