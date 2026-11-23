"""
Hermetic tests for MCP HTTP bearer auth (agent/mcp_auth.py + mcp_server.py).

Real uvicorn server on a loopback ephemeral port in a background thread, driven by
the official MCP streamable-HTTP client and raw HTTP. JWTs are signed with a key
generated per test run (nothing secret is committed); no IdP, no network.

Run: python agent/test_mcp_auth.py
"""

import asyncio
import json
import socket
import threading
import time
import unittest
from unittest import mock

import httpx2
import jwt
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

import mcp_auth
import mcp_server

STATIC = "s" * 40
ISSUER = "https://issuer.example.test"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC_PEM = _KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def _pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def _hand_made_hs256(claims, secret):
    import base64, hashlib, hmac as _hmac
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    signing = b64(b'{"alg":"HS256","typ":"JWT"}') + b"." + b64(json.dumps(claims).encode())
    return (signing + b"." + b64(_hmac.new(secret, signing, hashlib.sha256).digest())).decode()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Server:
    def __init__(self, env):
        self.port = _free_port()
        self.url = f"http://127.0.0.1:{self.port}/mcp"
        env = {"MCP_RESOURCE_URL": self.url, **env}
        app = mcp_server.build_http_app(env, port=self.port)
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=self.port,
                                                    log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("server did not start")

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(5)


def make_jwt(scope, *, key=_KEY, aud=None, iss=ISSUER, exp_delta=300, aud_url=None):
    claims = {"iss": iss, "aud": aud or aud_url, "exp": int(time.time()) + exp_delta,
              "scope": scope, "sub": "tester", "client_id": "test-client"}
    return jwt.encode(claims, _pem(key), algorithm="RS256")


def mcp_call(url, token, tool, args):
    """Real MCP client call -> CallToolResult (raises on HTTP-level auth failure)."""
    async def go():
        client = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"} if token else {})
        async with client:
            async with streamable_http_client(url, http_client=client) as (r, w):
                async with ClientSession(r, w) as session:
                    await session.initialize()
                    return await session.call_tool(tool, args)
    return asyncio.run(go())


def raw_post(url, token, payload):
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx2.post(url, headers=headers, content=json.dumps(payload), timeout=10)


CALL_READ = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "read_file", "arguments": {"path": "app/pom.xml"}}}
CALL_SEARCH = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
               "params": {"name": "search_code", "arguments": {"query": "Customer"}}}


class FailClosedConfigTests(unittest.TestCase):
    def test_no_credentials_refuses_to_build_http_app(self):
        with self.assertRaises(mcp_auth.McpAuthConfigError):
            mcp_server.build_http_app({})

    def test_short_static_token_rejected(self):
        with self.assertRaises(mcp_auth.McpAuthConfigError):
            mcp_server.build_http_app({"MCP_BEARER_TOKEN": "short"})

    def test_jwt_key_without_issuer_rejected(self):
        with self.assertRaises(mcp_auth.McpAuthConfigError):
            mcp_server.build_http_app({"MCP_JWT_PUBLIC_KEY_PEM": PUBLIC_PEM})

    def test_unknown_scope_rejected(self):
        with self.assertRaises(mcp_auth.McpAuthConfigError):
            mcp_server.build_http_app({"MCP_BEARER_TOKEN": STATIC, "MCP_BEARER_SCOPES": "repo:write"})

    def test_every_registered_tool_has_a_scope_mapping(self):
        import asyncio as aio
        names = {t.name for t in aio.run(mcp_server.mcp.list_tools())}
        self.assertEqual(names, set(mcp_auth.TOOL_SCOPES))


class StaticTokenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _Server({"MCP_BEARER_TOKEN": STATIC, "MCP_BEARER_SCOPES": "repo:search"}).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.srv.__exit__()

    def test_unauthenticated_is_401_with_challenge(self):
        r = raw_post(self.srv.url, None, CALL_SEARCH)
        self.assertEqual(r.status_code, 401)
        challenge = r.headers["www-authenticate"]
        self.assertTrue(challenge.startswith("Bearer "))
        self.assertIn("/.well-known/oauth-protected-resource/mcp", challenge)

    def test_wrong_token_is_401(self):
        self.assertEqual(raw_post(self.srv.url, "x" * 40, CALL_SEARCH).status_code, 401)

    def test_token_in_query_string_not_accepted(self):
        r = raw_post(self.srv.url + f"?access_token={STATIC}", None, CALL_SEARCH)
        self.assertEqual(r.status_code, 401)

    def test_protected_resource_metadata_served_without_auth(self):
        base = self.srv.url.rsplit("/mcp", 1)[0]
        r = httpx2.get(base + "/.well-known/oauth-protected-resource/mcp", timeout=10)
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        self.assertEqual(doc["resource"].rstrip("/"), self.srv.url)
        self.assertGreaterEqual(len(doc["authorization_servers"]), 1)

    def test_valid_token_right_scope_allowed(self):
        result = mcp_call(self.srv.url, STATIC, "search_code", {"query": "Customer"})
        self.assertFalse(result.is_error)

    def test_valid_token_wrong_scope_is_403_insufficient_scope(self):
        r = raw_post(self.srv.url, STATIC, CALL_READ)
        self.assertEqual(r.status_code, 403)
        challenge = r.headers["www-authenticate"]
        self.assertIn('error="insufficient_scope"', challenge)
        self.assertIn('scope="repo:read"', challenge)
        self.assertNotIn("pom.xml", r.text)
        self.assertNotIn("<project", r.text)

    def test_wrong_scope_through_official_client_never_returns_file_contents(self):
        with self.assertRaises(BaseException) as ctx:
            mcp_call(self.srv.url, STATIC, "read_file", {"path": "app/pom.xml"})
        self.assertNotIn("<project", str(ctx.exception))


class JwtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = _Server({"MCP_JWT_PUBLIC_KEY_PEM": PUBLIC_PEM, "MCP_ISSUER_URL": ISSUER}).__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.srv.__exit__()

    def tok(self, scope, **kw):
        kw.setdefault("aud_url", self.srv.url)
        return make_jwt(scope, **kw)

    def test_read_scope_can_read_but_not_search(self):
        t = self.tok("repo:read")
        self.assertFalse(mcp_call(self.srv.url, t, "list_repository_files", {"directory": "docs"}).is_error)
        self.assertEqual(raw_post(self.srv.url, t, CALL_SEARCH).status_code, 403)

    def test_search_scope_cannot_read_or_list(self):
        t = self.tok("repo:search")
        self.assertEqual(raw_post(self.srv.url, t, CALL_READ).status_code, 403)
        listing = {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": "list_repository_files", "arguments": {"directory": "."}}}
        self.assertEqual(raw_post(self.srv.url, t, listing).status_code, 403)
        self.assertFalse(mcp_call(self.srv.url, t, "search_code", {"query": "Customer"}).is_error)

    def test_both_scopes_allowed_and_path_security_still_enforced(self):
        t = self.tok("repo:read repo:search")
        result = mcp_call(self.srv.url, t, "read_file", {"path": "../../etc/passwd"})
        self.assertTrue(result.is_error)
        self.assertIn("path traversal is not allowed", result.content[0].text)

    def test_empty_scope_denied_everything(self):
        t = self.tok("")
        self.assertEqual(raw_post(self.srv.url, t, CALL_SEARCH).status_code, 403)

    def test_expired_token_is_401(self):
        self.assertEqual(raw_post(self.srv.url, self.tok("repo:read repo:search", exp_delta=-60),
                                  CALL_SEARCH).status_code, 401)

    def test_wrong_audience_is_401(self):
        t = self.tok("repo:read repo:search", aud="https://other.example.test/mcp")
        self.assertEqual(raw_post(self.srv.url, t, CALL_SEARCH).status_code, 401)

    def test_wrong_issuer_is_401(self):
        t = self.tok("repo:read repo:search", iss="https://evil.example.test")
        self.assertEqual(raw_post(self.srv.url, t, CALL_SEARCH).status_code, 401)

    def test_token_signed_by_unknown_key_is_401(self):
        t = self.tok("repo:read repo:search", key=_OTHER_KEY)
        self.assertEqual(raw_post(self.srv.url, t, CALL_SEARCH).status_code, 401)

    def test_alg_none_and_hs256_rejected(self):
        claims = {"iss": ISSUER, "aud": self.srv.url, "exp": int(time.time()) + 300,
                  "scope": "repo:read repo:search"}
        none_tok = jwt.encode(claims, None, algorithm="none")
        hs_tok = _hand_made_hs256(claims, PUBLIC_PEM.encode())  # classic key-confusion attempt
        for t in (none_tok, hs_tok):
            self.assertEqual(raw_post(self.srv.url, t, CALL_SEARCH).status_code, 401)

    def test_malformed_token_is_401(self):
        self.assertEqual(raw_post(self.srv.url, "not.a.jwt", CALL_SEARCH).status_code, 401)


class StdioLocalTrustTests(unittest.IsolatedAsyncioTestCase):
    """Stdio/in-process server has no auth surface by design (local-only trust)."""

    async def test_local_server_has_no_auth_and_tools_work(self):
        from mcp import Client
        async with Client(mcp_server.mcp) as client:
            r = await client.call_tool("list_repository_files", {"directory": "docs"})
        self.assertFalse(r.is_error)

    async def test_auth_enabled_server_fails_closed_without_token_in_context(self):
        verifier = mcp_auth.StaticTokenVerifier(STATIC, ["repo:read", "repo:search"], "http://x/mcp")
        _, settings, _ = mcp_auth.build_auth({"MCP_BEARER_TOKEN": STATIC}, "http://127.0.0.1:1/mcp")
        server = mcp_server.create_server(verifier, settings)
        from mcp import Client
        async with Client(server) as client:  # in-process: no HTTP, so no verified token
            r = await client.call_tool("read_file", {"path": "app/pom.xml"})
        self.assertTrue(r.is_error)
        self.assertIn("Unauthorized", r.content[0].text)
        self.assertNotIn("<project", r.content[0].text)


if __name__ == "__main__":
    unittest.main()
