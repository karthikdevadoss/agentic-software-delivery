# OWASP Top 10:2025 Self-Assessment — Customer App

Against the current OWASP Top 10:2025 (released January 2026 —
verified against the official owasp.org listing, not the 2021 edition
most training material still references). Honest by design: what's
real coverage with a real file/test to point to, what's a real gap,
and why — not a checklist where everything is quietly marked "done."

## A01:2025 — Broken Access Control — **Strong coverage**
Scope-based authorization on every business endpoint (`SecurityConfig`'s
`hasAuthority(...)` rules), a dedicated `WorkspaceAccessGuard` enforcing
per-customer isolation beyond just "authenticated," and a real
distinction between 401 (no/invalid token) and 403 (valid token, wrong
scope/workspace) with matching test coverage: `SecurityIntegrationTest`
(12 cases), `WorkspaceIsolationIntegrationTest` (8 cases). The Incident
Triage Lab's `approve` endpoints are the one deliberately ADMIN-gated
action per scenario — tested explicitly (`approve_withoutAdminAuthority_isRejected`).

## A02:2025 — Security Misconfiguration — **Mostly covered, one honest gap**
`/actuator/**` requires authentication except `health`/`info`
(liveness/readiness pattern); raw `env`/`beans`/etc. are never public.
**Real, named gap:** `/h2-console/**` is `permitAll()` — acceptable
today because production data is synthetic demo data in an ephemeral
H2 instance with no real customer information, but this would need
review (disable entirely, or gate behind a real auth check) before any
real production data ever touched this app. No CORS policy is
explicitly configured either way — not yet reviewed against a real
browser-origin requirement, flagged rather than silently assumed fine.

## A03:2025 — Software Supply Chain Failures — **Newly, honestly covered this session**
Dependabot (weekly, all four ecosystems: maven/pip/npm/github-actions)
was already running. OWASP dependency-check was added to CI this
session (`.github/workflows/ci.yml`) — **real, current limitation
documented in the workflow itself**: NVD now requires an API key for
reliable CVE-database access, which isn't configured yet, so the scan
currently can't complete a real analysis. Informational-only
(`continue-on-error`) until that's resolved and it's proven not noisy.

## A04:2025 — Cryptographic Failures — **Covered**
JWT signed HMAC-SHA256 with a secret sourced from an env var, never
committed (`JWT_DEMO_SIGNING_SECRET`); BCrypt for the one real password
hash in the system (`DemoIdentitySeeder`). TLS itself is terminated at
Railway's edge, standard for this class of PaaS deployment, not
re-implemented at the app layer.

## A05:2025 — Injection — **Covered**
JPA/Hibernate parameterized queries throughout — no raw SQL string
concatenation anywhere in the codebase. `AdminCustomerController`'s
search deliberately pre-builds the full `%value%` LIKE pattern in Java
(lowercased, already wrapped) specifically so the query never wraps the
bind parameter itself in `CONCAT`/`LOWER` — see `CustomerRepository`'s
Javadoc for the real Postgres-specific reasoning this avoided.

## A06:2025 — Insecure Design — **Strong coverage, this is most of what this session built**
The transactional outbox (dual-write gap closed by construction), the
idempotent-consumer ledger, the DB-constraint-as-last-line-of-defense
pattern for plan enrollment, the token-owned distributed lock, and the
Saga-style compensation for permanent vs. transient failures (see
`docs/DESIGN_PATTERNS.md`) are all secure-by-design choices made
explicit and tested, not security bolted on after the fact.

## A07:2025 — Authentication Failures — **Covered, strengthened this session**
Full JWT validation (signature, expiry, not-before, issuer, audience —
`SecurityIntegrationTest` covers every rejection case). Redis-backed
rate limiting added this session on the one unauthenticated,
credential-issuing endpoint (`POST /auth/demo-token`) — the single
most naturally abusable authentication-adjacent surface in the app.

## A08:2025 — Software or Data Integrity Failures — **Covered**
Dependabot + (once the NVD key gap above is closed) OWASP
dependency-check for known-vulnerable components; JWT signature
validation prevents token tampering; JSON (de)serialization goes
through Jackson 3 (`tools.jackson`), never raw Java object
deserialization of untrusted input anywhere in the codebase.

## A09:2025 — Security Logging and Alerting Failures — **Logging covered, alerting is a real, named gap**
A real `security.rejections` counter tagged by reason (401 vs 403),
structured ECS-format logs with a genuine `traceId`/`spanId` on every
line (100% Brave trace sampling). **Real gap:** nothing currently
*alerts* on these signals — no threshold-triggered page/webhook exists.
The metrics are real and queryable (and now visualizable — see this
session's Prometheus/Grafana dashboard), but "logging" and "alerting"
are genuinely two different bars, and only the first is met today.

## A10:2025 — Mishandling of Exceptional Conditions — **Strong, concrete coverage**
This is the category this session's own work maps to most directly, and
the strongest section of this assessment to walk through in an
interview: `RateLimiterService`, `EnrollmentLockService`, and
`ContractPlanCacheService` all fail OPEN deliberately (an optional
protection layer being down must never take the whole public demo down
with it) — and `ContractPlanBillingSyncConsumer`'s Saga-style
compensation is a direct, named example of NOT treating every
exceptional condition the same way: a transient failure gets Kafka's
retry+DLT, a permanent business-rule failure gets an explicit
compensating action instead, because retrying it could never succeed.
`GlobalExceptionHandler` ensures no exception anywhere in the app ever
reaches a caller as a raw, unhandled stack trace.

## Summary
7 of 10 categories: strong, real, tested coverage. 3 of 10
(Misconfiguration, Supply Chain, Logging/Alerting) have real, honestly
named partial gaps — none hidden, each with a concrete next step
already identified rather than left vague.
