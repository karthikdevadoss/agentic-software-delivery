"""
Bearer-token resource-server auth for the MCP server's HTTP transport.

Follows the MCP authorization spec 2026-07-28 (resource-server subset) -- see
docs/MCP_AUTH.md for the exact pages used and what is NOT implemented.

What the official `mcp` SDK (2.3.0) already does once handed a TokenVerifier +
AuthSettings, and what this module therefore reuses rather than reimplements:
  * parses `Authorization: Bearer`, returns 401 + WWW-Authenticate
    (`resource_metadata=`) for missing/invalid/expired tokens;
  * serves RFC 9728 Protected Resource Metadata at the well-known URI;
  * rejects tokens whose resource indicator is not this server
    (AuthSettings.validate_token_resource).

What this module adds:
  * two TokenVerifiers: a shared static token (dev/CI) and a signed JWT
    (RS256/ES256, public key only, checks iss/aud/exp);
  * per-tool scopes (default deny), enforced at the HTTP layer as
    `403 insufficient_scope` (spec "Runtime Insufficient Scope Errors") and
    again inside each tool as defence in depth;
  * fail-closed configuration: no token configured => the HTTP app refuses
    to be built.

Stdio has no auth surface (spec: stdio SHOULD NOT use this flow); it is a
local-only trust model, documented in docs/MCP_AUTH.md.
"""

import hmac
import json
import os
from urllib.parse import urlparse

import jwt
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.routes import build_resource_metadata_url
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl

SCOPE_SEARCH = "repo:search"
SCOPE_READ = "repo:read"

# Default deny: a tool that is not listed here is callable by NO scope.
TOOL_SCOPES = {
    "search_code": SCOPE_SEARCH,
    "semantic_repository_search": SCOPE_SEARCH,
    "search_project_context": SCOPE_SEARCH,
    "list_repository_files": SCOPE_READ,
    "read_file": SCOPE_READ,
}

MIN_STATIC_TOKEN_LEN = 32
JWT_ALGORITHMS = ["RS256", "ES256"]  # asymmetric only: no shared-secret / "none" algs
_BODY_PEEK_LIMIT = 1024 * 1024


class McpAuthConfigError(RuntimeError):
    """Hosted MCP auth is not (safely) configured -- the HTTP app must not start."""


def scope_allows(tool: str, scopes) -> bool:
    required = TOOL_SCOPES.get(tool)
    return required is not None and required in set(scopes)


class StaticTokenVerifier:
    """One shared bearer token with a fixed scope set (dev/CI; not a real IdP)."""

    def __init__(self, token: str, scopes: list[str], resource: str):
        if len(token) < MIN_STATIC_TOKEN_LEN:
            raise McpAuthConfigError(
                f"MCP_BEARER_TOKEN must be at least {MIN_STATIC_TOKEN_LEN} characters")
        self._token = token.encode()
        self._scopes = scopes
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token.encode(), self._token):
            return None
        return AccessToken(token=token, client_id="static-token", scopes=list(self._scopes),
                           resource=self._resource)


class JwtTokenVerifier:
    """Verifies a signed access token (RFC 9068-style `scope` claim) against a
    configured public key. `aud` must equal this server's resource URL (RFC 8707)."""

    def __init__(self, public_key_pem: str, issuer: str, resource: str):
        self._key = public_key_pem
        self._issuer = issuer
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(
                token, self._key, algorithms=JWT_ALGORITHMS, issuer=self._issuer,
                audience=self._resource,
                options={"require": ["exp", "iss", "aud"]},
            )
        except jwt.PyJWTError:
            return None
        raw = claims.get("scope", claims.get("scp", ""))
        scopes = raw.split() if isinstance(raw, str) else [s for s in raw if isinstance(s, str)]
        return AccessToken(token=token, client_id=str(claims.get("client_id", claims.get("azp", "unknown"))),
                           scopes=scopes, expires_at=int(claims["exp"]), resource=self._resource,
                           subject=claims.get("sub"), claims={"iss": claims["iss"]})


class AnyOfVerifier:
    def __init__(self, verifiers):
        self._verifiers = verifiers

    async def verify_token(self, token: str) -> AccessToken | None:
        for v in self._verifiers:
            result = await v.verify_token(token)
            if result is not None:
                return result
        return None


def build_auth(env, default_resource_url: str):
    """-> (verifier, AuthSettings, resource_url). Raises McpAuthConfigError (fail closed)."""
    resource = env.get("MCP_RESOURCE_URL") or default_resource_url
    parsed = urlparse(resource)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.fragment:
        raise McpAuthConfigError("MCP_RESOURCE_URL must be an absolute http(s) URL without a fragment")
    resource = resource.rstrip("/")

    verifiers = []
    issuer = env.get("MCP_ISSUER_URL")

    static = env.get("MCP_BEARER_TOKEN")
    if static:
        scopes = (env.get("MCP_BEARER_SCOPES") or SCOPE_SEARCH).split()  # least privilege default
        unknown = [s for s in scopes if s not in (SCOPE_SEARCH, SCOPE_READ)]
        if unknown:
            raise McpAuthConfigError(f"unknown scope(s) in MCP_BEARER_SCOPES: {unknown}")
        verifiers.append(StaticTokenVerifier(static, scopes, resource))

    pem = env.get("MCP_JWT_PUBLIC_KEY_PEM")
    if not pem and env.get("MCP_JWT_PUBLIC_KEY_FILE"):
        with open(env["MCP_JWT_PUBLIC_KEY_FILE"], encoding="utf-8") as fh:
            pem = fh.read()
    if pem:
        if not issuer:
            raise McpAuthConfigError("JWT auth requires MCP_ISSUER_URL (the expected `iss`)")
        verifiers.append(JwtTokenVerifier(pem, issuer, resource))

    if not verifiers:
        raise McpAuthConfigError(
            "refusing to serve MCP over HTTP without authentication: set MCP_BEARER_TOKEN "
            "and/or MCP_JWT_PUBLIC_KEY_PEM + MCP_ISSUER_URL (see docs/MCP_AUTH.md)")

    # Spec requires PRM `authorization_servers` to name >=1 AS. With only a shared
    # static token there is no AS; the resource origin is a placeholder (see docs).
    issuer = issuer or f"{parsed.scheme}://{parsed.netloc}"
    settings = AuthSettings(issuer_url=AnyHttpUrl(issuer), resource_server_url=AnyHttpUrl(resource),
                            validate_token_resource=True)
    verifier = verifiers[0] if len(verifiers) == 1 else AnyOfVerifier(verifiers)
    return verifier, settings, resource


class ToolScopeGuard:
    """ASGI wrapper: for a *valid* token calling `tools/call` on a tool whose scope
    it lacks, answer 403 `insufficient_scope` (RFC 6750 / MCP spec). Missing or
    invalid tokens are left to the SDK's 401 path. The body is replayed untouched."""

    def __init__(self, app, verifier, resource_metadata_url: str):
        self.app = app
        self.verifier = verifier
        self.metadata_url = resource_metadata_url

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope["headers"]}
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if not auth.lower().startswith("bearer "):
            return await self.app(scope, receive, send)
        access = await self.verifier.verify_token(auth[7:])
        if access is None:
            return await self.app(scope, receive, send)

        buffered, size, complete = [], 0, True
        while True:
            msg = await receive()
            buffered.append(msg)
            if msg["type"] != "http.request":
                break
            size += len(msg.get("body", b""))
            if not msg.get("more_body"):
                break
            if size > _BODY_PEEK_LIMIT:
                complete = False
                break

        async def replay():
            if buffered:
                return buffered.pop(0)
            return await receive()

        if complete:
            body = b"".join(m.get("body", b"") for m in buffered if m["type"] == "http.request")
            try:
                payload = json.loads(body)
            except ValueError:
                payload = None
            for call in (payload if isinstance(payload, list) else [payload]):
                if not isinstance(call, dict) or call.get("method") != "tools/call":
                    continue
                name = (call.get("params") or {}).get("name")
                if not scope_allows(str(name), access.scopes):
                    needed = TOOL_SCOPES.get(str(name))
                    return await self._forbidden(send, needed)
        return await self.app(scope, replay, send)

    async def _forbidden(self, send, needed):
        parts = ['error="insufficient_scope"']
        if needed:
            parts.append(f'scope="{needed}"')
        parts.append(f'resource_metadata="{self.metadata_url}"')
        parts.append('error_description="Token lacks the scope required for this tool"')
        body = json.dumps({"error": "insufficient_scope",
                           "error_description": "Token lacks the scope required for this tool"}).encode()
        await send({"type": "http.response.start", "status": 403, "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            (b"www-authenticate", ("Bearer " + ", ".join(parts)).encode())]})
        await send({"type": "http.response.body", "body": body})


def metadata_url_for(resource_url: str) -> str:
    return str(build_resource_metadata_url(AnyHttpUrl(resource_url)))
