# MCP server authentication and authorization

Added 2026-11-23. Code: `agent/mcp_auth.py`, wiring in `agent/mcp_server.py`,
tests in `agent/test_mcp_auth.py`. The server stays **read-only**; no write,
build or deploy tool exists and path-security (`tools.py`) is unchanged.

## Sources followed (retrieved 2026-11-23)

Current MCP spec revision: **2026-07-28** (spec index still points at
`schema/2026-07-28`; no newer revision was found).

- https://modelcontextprotocol.io/specification/ (index; names 2026-07-28)
- https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization.md
- https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/authorization-server-discovery.md
- Official Python SDK, resource-server page:
  https://py.sdk.modelcontextprotocol.io/run/authorization/ (installed `mcp` 2.3.0)

## Trust models

| Transport | Auth | Model |
|---|---|---|
| stdio (default, `python agent/mcp_server.py`) | none | **Local-only trust.** The spec says stdio SHOULD NOT use the HTTP flow; whoever can launch the process can use all five tools. Not for sharing. |
| Streamable HTTP (`MCP_TRANSPORT=streamable-http`) | Bearer token required | OAuth 2.1 resource-server subset. **Fails closed**: with no token/key configured the process exits and nothing listens. |
| In-process `Client(mcp)` | none | Test/dev only; skips HTTP, so auth does not apply. |

## Configuration (HTTP only; env vars)

| Var | Meaning |
|---|---|
| `MCP_BEARER_TOKEN` | Shared static token, >= 32 chars (dev/CI). Constant-time compared. |
| `MCP_BEARER_SCOPES` | Space-separated scopes for that token. Default `repo:search` (least privilege). |
| `MCP_JWT_PUBLIC_KEY_PEM` / `MCP_JWT_PUBLIC_KEY_FILE` | Public key (PEM) to verify signed access tokens. RS256/ES256 only (no `none`, no HS*). |
| `MCP_ISSUER_URL` | Required with a JWT key: the expected `iss`; also advertised as the authorization server. |
| `MCP_RESOURCE_URL` | Canonical URL of the MCP endpoint (default `http://HOST:PORT/mcp`). JWT `aud` must equal it (RFC 8707). |
| `MCP_HOST`, `MCP_PORT` | Bind address (default `127.0.0.1:8000`). |

Generate a throwaway token: `python -c "import secrets;print(secrets.token_urlsafe(32))"`.
Never commit it. Clients send `Authorization: Bearer <token>` on every request
(never in the query string).

## Scopes -> tools (default deny)

| Scope | Tools |
|---|---|
| `repo:search` | `search_code`, `semantic_repository_search`, `search_project_context` |
| `repo:read` | `list_repository_files`, `read_file` |

A tool not in this table is callable by no scope. `repo:search` cannot read or
list files. Scope names are this project's own; the spec does not define any.

## Behaviour (what the spec pages say, and what we do)

- Missing, malformed, wrong-key, expired, wrong-issuer or wrong-audience token
  -> **401** with `WWW-Authenticate: Bearer ... resource_metadata="..."` (SDK).
- Valid token lacking the tool's scope -> **403** `WWW-Authenticate: Bearer
  error="insufficient_scope", scope="<needed>", resource_metadata="..."` (spec
  "Runtime Insufficient Scope Errors"), produced before the tool runs; the body
  names no file or path. Each tool re-checks scope itself (defence in depth).
- RFC 9728 Protected Resource Metadata served at
  `/.well-known/oauth-protected-resource/mcp` (SDK).
- `initialize` / `tools/list` need a valid token but no particular scope, so a
  search-only token can see tool *names*.

## Honest limits

- **Not full spec compliance.** Resource-server side only. No authorization
  server, token issuance, client registration, PKCE flow or consent UI exists
  here, so an off-the-shelf MCP client cannot self-onboard; tokens are minted
  out of band.
- With only the shared static token there is no authorization server; the
  metadata's `authorization_servers` is the resource origin as a placeholder
  (the spec requires >= 1 entry). Do not treat it as a real AS.
- JWT verification uses a single configured public key: no JWKS fetch, no key
  rotation, no revocation/introspection, no `nbf`/replay tracking.
- Static token = one shared secret with one scope set; no per-user identity,
  audit trail, rate limiting or multi-tenancy. Not a production gateway.
- No TLS termination here; hosting must put it behind HTTPS (I did not verify the spec's exact
  HTTPS wording; the Security Considerations page was not read) and set an explicit Host
  allow-list when binding beyond loopback.
- Scope is per tool only. Per-document ACLs / permission-aware retrieval are
  **future work** and not implemented.
- `/mcp` is not deployed on the public site; nothing here was deployed.
