# Flagship Market Coverage — Energy Customer Platform

Durable roadmap/priority matrix for the Customer App as the flagship
Senior Java Backend portfolio piece, created per the 2026-09-13/14
"MASTER OVERNIGHT ENGINEERING PHASE" task. Priorities (P0/P1/P2) reflect
current Senior Java Backend job-market relevance and interview
importance, not chronological technology history — see that task's
"MARKET-FIRST RULE". This is a priority matrix, not fabricated market
research; no percentages are invented.

Status values: `NOT_STARTED`, `PARTIAL`, `IMPLEMENTED`, `PRODUCTION_VERIFIED`,
`BLOCKED_OWNER_ACTION`.

## Java / Spring core

| Capability | Priority | State | Business scenario | Component | Testing | Production | Observability | Interview concepts | Dependencies |
|---|---|---|---|---|---|---|---|---|---|
| REST API + validation + centralized error handling | P0 | PRODUCTION_VERIFIED | Customer lookup/create | CustomerController/Service/GlobalExceptionHandler | JUnit5 + real-server RestTemplate integration tests | live Railway | none yet | Bean Validation, @RestControllerAdvice, DTO vs entity | none |
| OpenAPI/Swagger documentation | P0 | IMPLEMENTED (2026-09-14) | Any API consumer discovers the real contract without reading source | springdoc-openapi 3.1.1, generated from real annotations | OpenApiIntegrationTest (2 tests, real HTTP) | not yet deployed | n/a | API design/contract-first vs code-first docs | spring-boot-starter-web |
| Domain modeling beyond a single entity | P0 | IMPLEMENTED (2026-09-14) | Preferences + Contract/Plan business modules | CustomerPreference, ContractPlan (unidirectional customerId reference, deliberately no JPA relationship) | 8 unit (Mockito) + 9 integration (RestTemplate) tests | not yet deployed | none yet | aggregate boundaries, DTO isolation, avoiding lazy-serialization pitfalls | spring-data-jpa |
| Open-Session-In-View disabled | P1 | IMPLEMENTED (2026-09-14) | Avoid the classic OSIV anti-pattern (connection held across view rendering) | `spring.jpa.open-in-view=false` | covered incidentally by all integration tests still passing | not yet deployed | n/a | a genuinely common senior-level production-correctness interview topic | none |
| Java 21 language features | P2 | NOT_STARTED | n/a yet | would require bumping `java.version` from 17 | — | — | — | records (already used for DTOs on Java 17), pattern matching, virtual threads | risk: verify Railway/Nixpacks Java 21 support first |

## Data

| Capability | Priority | State | Business scenario | Component | Testing | Production | Observability | Interview concepts | Dependencies |
|---|---|---|---|---|---|---|---|---|---|
| PostgreSQL + Spring Data JPA | P0 | PRODUCTION_VERIFIED (2026-09-14) | Real relational persistence instead of ephemeral H2 | `postgres` Spring profile, `org.postgresql:postgresql`, dedicated Railway Postgres service in the `agentic-delivery-customer-app` project (separate from the event-ledger Postgres) | see Testcontainers row | LIVE: SPRING_PROFILES_ACTIVE=postgres active in production since 2026-09-14; real API smoke test (create/read customer, preferences, contract-plan enroll) verified against the live DB, persistence independently confirmed to survive a container restart | none yet | connection pooling (HikariCP already in use), dialect, profiles, private-network service-to-service Postgres access | none — the real env-var activation gap this row used to flag is now closed; see docs/LESSONS.md for a real, separate finding hit during the cutover (the customer-app service doesn't auto-deploy on git push, so a rebuild via `railway up` was required first) |
| Flyway migrations | P0 | PRODUCTION_VERIFIED (2026-09-14) | Schema owned by version-controlled SQL, not Hibernate auto-DDL, in the target production profile | V1-V3 under `db/migration/`, `ddl-auto=validate` in the postgres profile | validated by PostgresFlywayIntegrationTest (schema + table existence) | LIVE: real deploy logs show all 3 migrations applied from `<< Empty Schema >>` to v3 against the real production Postgres | n/a | migration-first schema ownership, validate vs auto-generate | flyway-core, flyway-database-postgresql |
| Testcontainers-based DB integration testing | P0 | IMPLEMENTED (2026-09-14), locally SKIPPED (no Docker on this dev machine), CI-verified | Prove the app genuinely works against real Postgres, not just H2 | `PostgresFlywayIntegrationTest` (`@Testcontainers(disabledWithoutDocker = true)`) | 5 tests: schema, full API flow, preferences, **DB-level** one-active-plan constraint via a raw bypass insert, enroll-twice history | see `.github/workflows/ci.yml` real run (linked in the session's final report) | n/a | real vs H2-approximated integration testing, disabledWithoutDocker pattern | Docker (present on GitHub Actions runners; absent on this Windows dev machine — a real, disclosed constraint) |
| Business-rule enforcement at the DB layer (partial unique index) | P1 | IMPLEMENTED (2026-09-14) | "One ACTIVE plan per customer" must hold even under a service-layer bug or a concurrent race | `uq_contract_plan_one_active_per_customer` partial unique index (Postgres-only; H2's create-drop schema does not have it) | PostgresFlywayIntegrationTest proves a raw bypass insert is rejected | not yet active | n/a | defense-in-depth, DB constraints as the last line of defense, concurrency | Postgres |
| Query tuning / index strategy at scale | P2 | NOT_STARTED | No real query-volume problem exists yet to justify it | — | — | — | — | EXPLAIN ANALYZE, N+1 detection | real data volume |
| Pagination | P2 | NOT_STARTED | No list endpoint returns unbounded results yet (single-customer lookups only) | — | — | — | — | Spring Data `Pageable` | a real multi-result endpoint |

## Cache

| Capability | Priority | State | Business scenario | Notes |
|---|---|---|---|---|
| Redis (cache-aside for Customer Profile/Contract read) | P1 | NOT_STARTED | Not attempted this session — sequenced after Postgres per the task's own slice order | Requires either Owner-approved Redis provisioning or Testcontainers-only local proof; record BLOCKED_OWNER_ACTION for any production instance |

## Eventing

| Capability | Priority | State | Business scenario | Notes |
|---|---|---|---|---|
| Kafka (CustomerPreferenceUpdated / CustomerProfileUpdated) | P1 | NOT_STARTED | Not attempted this session | Real candidate now exists (PUT /customers/{id}/preferences) once this slice is picked up; must address the transactional-outbox problem explicitly, not a naive dual write |

## Security

| Capability | Priority | State | Business scenario | Notes |
|---|---|---|---|---|
| Spring Security + JWT resource-server | P0 | PRODUCTION_VERIFIED (2026-09-14) | Every business endpoint (customers, preferences, contract plans, appointment availability) now requires a real signed JWT with scope-based authorization | `security/SecurityConfig.java` (NimbusJwtDecoder, HS256, validates signature+expiry+issuer+audience), `security/DemoJwtIssuer.java` (portfolio demo token issuer, explicitly NOT an enterprise IdP, fixed scope set only), `POST /auth/demo-token` (public). 12 SecurityIntegrationTest cases (no/malformed/wrong-signature/expired/wrong-issuer/wrong-audience/wrong-scope all rejected; valid token allowed) + 2 AppointmentController tests. Production signing secret is a freshly generated random value set only as a Railway env var (JWT_DEMO_SIGNING_SECRET), never committed. Live-verified: 401 no/malformed token, 200 valid token, 404 through auth (proves authz passed), 201 create with write scope — all against real production, not just tests. |

## Integrations / Resilience

| Capability | Priority | State | Business scenario | Notes |
|---|---|---|---|---|
| Downstream HTTP client + timeout/retry/circuit breaker (Resilience4j) + WireMock tests | P0 | IMPLEMENTED (2026-09-14) | A real "Appointment Availability" downstream call (`GET /customers/{id}/appointment-availability?date=...`) | `AppointmentAvailabilityClient` (Spring `RestClient`) + `AppointmentAvailabilityConfig`/`Service` (Resilience4j core circuitbreaker+retry, composed programmatically -- the `resilience4j-spring-boot3/4` annotation starter has a real, documented Spring Boot 4 BOM gap as of this session, verified via WebSearch/WebFetch). SERVICE_UNAVAILABLE is a distinct, never-fabricated outcome. 7 real WireMock tests (`AppointmentAvailabilityIntegrationTest`): success, 5xx retried 3x, 4xx never retried (exactly 1 call), real connect/read timeout, malformed JSON body, sustained-failure circuit-breaker behavior -- all against the real RestClient/CircuitBreaker/Retry stack over real loopback HTTP, zero mocked client. No real production downstream service exists (by design -- this demonstrates the pattern, not a real third-party integration) |

## Testing (cross-cutting)

| Capability | Priority | State | Notes |
|---|---|---|---|
| JUnit 5 + Mockito unit tests | P0 | IMPLEMENTED | CustomerServiceTest + new CustomerPreferenceServiceTest/ContractPlanServiceTest |
| Real-server integration tests (RestTemplate, not MockMvc) | P0 | IMPLEMENTED | MockMvc confirmed NOT on this Spring Boot 4.1.1 project's classpath (module split moved Jackson to `tools.jackson`) — RestTemplate + `@SpringBootTest(RANDOM_PORT)` is this project's real, working pattern |
| Testcontainers DB integration | P0 | IMPLEMENTED, CI-verified | See Data section above |
| WireMock downstream-contract tests | P0 | IMPLEMENTED (2026-09-14) | `AppointmentAvailabilityIntegrationTest`, 7 tests |
| Security tests (missing/malformed/expired token, wrong scope) | P0 | IMPLEMENTED (2026-09-14), PRODUCTION_VERIFIED | `SecurityIntegrationTest` (12 tests) + live curl verification against real production |
| Performance/load tests (k6/Gatling/JMeter) | P1 | NOT_STARTED | No baseline established yet |
| CI pipeline running the above | P0 | PARTIAL (2026-09-14) | `.github/workflows/ci.yml` runs Java tests (incl. real Testcontainers Postgres), a scoped offline subset of the Python AI-platform tests + evals, and Node frontend tests. Does NOT yet run the full Python suite (several existing tests need live production credentials this CI job intentionally does not have) — a real, disclosed gap |

## Observability

| Capability | Priority | State | Notes |
|---|---|---|---|
| Actuator, Micrometer, structured logs, correlation IDs, OpenTelemetry | P0/P1 | NOT_STARTED | Not attempted this session |

## Delivery / Platform

| Capability | Priority | State | Notes |
|---|---|---|---|
| CI (GitHub Actions) | P0 | IMPLEMENTED (2026-09-14) | See Testing section |
| Dependabot | P1 | IMPLEMENTED (2026-09-14) | `.github/dependabot.yml` — maven/pip/npm/github-actions, weekly |
| Dockerfile for the Customer app itself | P1 | NOT_STARTED | Currently deployed via Railway's Nixpacks auto-detection, not Docker — the platform-backend Python service has its own separate Dockerfile, unrelated to this app |
| Kubernetes-ready artifacts (labeled as such, not as current production) | P2 | NOT_STARTED | Railway remains the real current production platform |
| OWASP dependency-check / SAST | P1 | NOT_STARTED | Dependabot (above) is a lighter first step; a Maven OWASP plugin run was judged too heavy/slow to add reliably in one overnight session without first checking it doesn't break CI |

## AI Software Delivery Layer (separate track, see docs/DECISIONS.md for full detail)

| Capability | Priority | State | Notes |
|---|---|---|---|
| RAG (curated backend corpus) | done prior session | IMPLEMENTED, internal-only | agent/backend_rag_corpus.py + agent/backend_rag_index.py |
| Embeddings (fastembed, local) | done prior session | IMPLEMENTED | BAAI/bge-small-en-v1.5, 384-dim |
| MCP (search_project_context, read-only) | done prior session | IMPLEMENTED | agent/mcp_server.py |
| Evals (retrieval + routing) | done prior session | IMPLEMENTED | agent/eval_runner.py, baseline recall@3=1.0, mrr=0.903, routing=14/14 |
| Real end-to-end AI backend run (genuine LLM call in the full pipeline) | P0 for this track | NOT ATTEMPTED THIS SESSION | Deliberately deferred — see the overnight session's final report for why (risk of compounding a real production AI-driven change with a same-night persistence-layer refactor of the same app) |

## Recommended next-session order (not a commitment, a priority queue)

1. Observability (Actuator/Micrometer/correlation IDs) — cheap, high interview value, unblocks meaningful performance work later.
2. The real end-to-end AI backend run (genuine LLM call), attempted in ISOLATION from any concurrent persistence-layer change.
3. Redis, then Kafka — both explicitly sequenced last per the original task's own slice order, and both have real external-infrastructure decisions attached.
4. Java 21 assessment (P2) — not yet attempted; verify Railway/Railpack Java 21 support first.

(Slice 4 — downstream integration + Resilience4j + WireMock — completed 2026-09-14, see Integrations/Resilience above. Postgres/Flyway production cutover — completed and PRODUCTION_VERIFIED 2026-09-14, see Data section above. Spring Security + JWT resource-server — completed and PRODUCTION_VERIFIED 2026-09-14, see Security section above.)
