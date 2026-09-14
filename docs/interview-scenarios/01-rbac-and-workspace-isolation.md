# Interview Scenario: USER/ADMIN RBAC + Workspace Isolation

Derived from the actual implementation: `app/src/main/java/com/example/customer/security/{SecurityConfig,WorkspaceAccessGuard,DemoJwtIssuer}.java`, `AdminCustomerController.java`.

## Business Why

A multi-persona demo/production system must guarantee that a regular USER
can never read or modify another customer's data — not "the UI doesn't show
it," a real server-side guarantee that holds even against a client
deliberately incrementing an id in the URL. An ADMIN persona separately
needs a legitimate, gated, cross-customer view for support/operations use
cases, without that becoming a general bypass of authentication.

## Requirement

- A USER-role JWT may only ever act on the ONE customer bound to its own
  identity.
- An ADMIN-role JWT may act on any customer, but is still a real,
  server-verified, correctly-scoped JWT — never a shared secret or a
  client-side flag.
- Unauthorized cross-customer access must return a real HTTP 403, not a
  filtered/empty 200 (which would look like "no data" rather than "denied,"
  a meaningfully different signal to a client and to an auditor).

## Architecture

Two independent, composable layers:
1. **Scope-based route authorization** (`SecurityConfig`'s
   `authorizeHttpRequests`) — coarse-grained, per-HTTP-method-and-path,
   driven by the JWT's `scope` claim (Spring Security's default
   `JwtAuthenticationConverter` prefixes each space-delimited scope with
   `SCOPE_`, so `scope: "customer:read"` becomes the authority
   `SCOPE_customer:read` with zero custom converter code needed).
2. **Per-request workspace ownership check** (`WorkspaceAccessGuard`) —
   fine-grained, per-customer-id, driven by the JWT's own `cid` (customer
   id) and `role` claims, called explicitly inside each customer-scoped
   controller method.

These are deliberately separate concerns: scope authorization answers "can
this token EVER call this kind of operation," workspace isolation answers
"can this SPECIFIC token act on THIS SPECIFIC customer."

## Request Flow

```
Client --(Bearer JWT)--> Spring Security filter chain
   |
   |-- oauth2ResourceServer: NimbusJwtDecoder verifies signature (HMAC),
   |   expiry, issuer, audience (JwtValidators.createDefaultWithValidators)
   |-- authorizeHttpRequests: coarse SCOPE_xxx check per route
   |     -> fails: AuthenticationEntryPoint (401) or AccessDeniedHandler (403),
   |        both emit real JSON {"error": "..."} plus a security.rejections
   |        Micrometer counter, tagged by reason (unauthenticated vs
   |        insufficient_scope) -- a real observability signal, not just a
   |        status code
   |
   v (authorized at the route level)
Controller method (e.g. GET /customers/{id})
   |-- WorkspaceAccessGuard.assertAccessible(requestedCustomerId, jwt)
   |     role == "ADMIN"  -> bypass, proceed
   |     role == null     -> legacy/unscoped anonymous demo token, bypass
   |                         (documented, deliberate: matches pre-existing
   |                         tested behavior for internal/backend automation)
   |     role == "USER"   -> cid claim must equal requestedCustomerId,
   |                         else throw ForbiddenWorkspaceAccessException
   v
GlobalExceptionHandler maps ForbiddenWorkspaceAccessException -> 403 JSON
```

## Java/Spring Implementation

- `SecurityConfig` is stateless (`SessionCreationPolicy.STATELESS`, no
  cookies/session ever issued) and disables CSRF **deliberately, not
  carelessly** — CSRF protects session/cookie-authenticated browser flows,
  which don't exist in a bearer-token API; the code comment records this
  reasoning explicitly rather than leaving a reader to wonder if it's an
  oversight.
- `WorkspaceAccessGuard` is a plain `@Component`, called explicitly by each
  controller method that needs it — not a global filter. This is a
  deliberate trade-off: explicit per-endpoint calls are more boilerplate
  than a blanket filter, but make each endpoint's isolation requirement
  visible in its own code, and avoid accidentally isolating an endpoint
  (like `/admin/customers`) that is supposed to be cross-customer by
  design.
- BCrypt (`BCryptPasswordEncoder`) hashes real demo credentials at seed
  time; login verification (`DemoLoginController`, not shown here) never
  does a plaintext comparison.

## Database/Data Flow

`WorkspaceAccessGuard` never queries the database — it only compares JWT
claims (`cid`, `role`) already verified by signature against the requested
path parameter. This is a deliberate performance/simplicity choice: the
authorization decision is O(1) and requires zero extra I/O per request,
because the claim itself was already cryptographically bound to the
identity at token-issuance time.

`AdminCustomerController`'s real cross-customer query
(`CustomerRepository.searchWorkspaceCustomers`) is separately scoped to
the demo workspace (a JOIN-style subquery against `demo_identity`), so even
an ADMIN's "cross-customer" view is bounded to the actual demo tenancy, not
every `Customer` row ever created historically.

## Thread/Concurrency Behavior

Each request is independently authenticated and authorized; there is no
shared mutable authorization state between concurrent requests. `Jwt`
objects are immutable value objects per Spring Security's OAuth2 resource
server design, so no synchronization is needed around the claims read in
`WorkspaceAccessGuard`.

## Failure Cases (real, tested)

- No token / invalid signature / expired token → 401, `security.rejections{reason=unauthenticated}` incremented.
- Valid token, wrong scope for the route → 403, `security.rejections{reason=insufficient_scope}` incremented.
- Valid token, correct scope, USER role, wrong `cid` → 403 via `ForbiddenWorkspaceAccessException` (a REAL 403, not a filtered/empty 200 — explicitly required and tested).
- A `Customer` row not bound to any `demo_identity` (inserted directly via the repository in a test, simulating stale/orphaned data) → proven never to appear in the ADMIN search results.

## Testing

`AdminCustomerControllerIntegrationTest` (11 tests): pagination, search by
id/name/email, empty search (returns all, not an error), no-result search
(empty page, not an error), USER gets 403 on the ADMIN endpoint,
cross-workspace isolation, ADMIN opening a customer, a USER's own change
visible to ADMIN, and a persisted change surviving a fresh independent
`/auth/login` call (the real proxy for logout+relogin, since there is no
server-side session beyond the JWT itself).

## Production Observability

Real Micrometer counters (`security.rejections`, tagged by reason) are
exported via Actuator/Prometheus — a spike in `insufficient_scope`
rejections is a real, queryable signal (e.g. a client using a stale/wrong
token type), distinguishable from a spike in `unauthenticated` rejections
(e.g. a client not sending a token at all).

## Design Trade-offs

- Explicit per-endpoint `WorkspaceAccessGuard` calls vs. a global filter:
  chosen for endpoint-level visibility and to avoid accidentally scoping an
  intentionally-cross-customer endpoint — at the cost of a developer having
  to remember to call it on every new customer-scoped endpoint (a real,
  accepted risk, mitigated by the integration test suite explicitly
  covering every customer-scoped route).
- Claims-only authorization (no DB lookup per request) vs. a
  database-backed permission check: chosen for latency and simplicity,
  relying on the JWT's own cryptographic integrity — correct as long as
  token issuance itself is trustworthy and tokens are short-lived enough
  that a revoked/changed permission propagates acceptably.

## What Changes at 10x Scale

- A claims-only authorization check still scales linearly with request
  volume with no additional DB load — this design actually scales *better*
  at 10x than a DB-backed permission check would.
- The ADMIN search query (`searchWorkspaceCustomers`) would need to move
  from a LIKE-pattern scan (fine at demo scale) to a real search index
  (e.g. Postgres full-text search or an external search service) once the
  customer table is large enough that pattern-matching scans become a
  measurable latency/CPU cost — see interview-scenarios/02 for the exact
  real bug this project already hit with LIKE/CONCAT on Postgres.
- Token revocation before natural expiry (e.g. an admin disabling an
  account) would need a real mechanism (a short-lived token + refresh, or a
  revocation list check) — this demo's tokens are pure bearer JWTs with no
  revocation path, an accepted trade-off at demo scale.

## Interview Questions This Answers

- "How do you prevent horizontal privilege escalation (user A reading user B's data by changing an id)?"
- "Why disable CSRF for a REST API — isn't that a security downgrade?"
- "How do you distinguish 'not authenticated' from 'not authorized' in both the API contract and your metrics?"
- "Where would you put an authorization check — a global filter, or per-endpoint — and why?"
- "How does JWT claim design let you avoid a database round-trip for every authorization decision?"

## Live Demo / Evidence Links

- https://agentic-delivery-customer-app-production.up.railway.app (login as a USER persona, attempt to access another customer's id directly via the API — real 403)
- https://agentic-delivery-customer-app-production.up.railway.app/admin/customers (ADMIN persona only)
- `app/src/main/java/com/example/customer/security/` (real source)
- `AdminCustomerControllerIntegrationTest` (real test source)
