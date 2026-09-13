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
| PostgreSQL + Spring Data JPA | P0 | IMPLEMENTED (code), BLOCKED_OWNER_ACTION (production cutover) | Real relational persistence instead of ephemeral H2 | `postgres` Spring profile, `org.postgresql:postgresql` | see Testcontainers row | H2 still active in production; Postgres profile inert until cutover | none yet | connection pooling (HikariCP already in use), dialect, profiles | none new for code; a provisioned Postgres instance for the cutover |
| Flyway migrations | P0 | IMPLEMENTED (2026-09-14) | Schema owned by version-controlled SQL, not Hibernate auto-DDL, in the target production profile | V1-V3 under `db/migration/`, `ddl-auto=validate` in the postgres profile | validated by PostgresFlywayIntegrationTest (schema + table existence) | not yet active in production (H2 profile still uses ddl-auto=create-drop, unchanged) | n/a | migration-first schema ownership, validate vs auto-generate | flyway-core, flyway-database-postgresql |
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
| Spring Security + JWT resource-server | P0 | NOT_STARTED | Not attempted this session | High market priority for next session — sequenced after data foundation per the task's own slice order |

## Integrations / Resilience

| Capability | Priority | State | Business scenario | Notes |
|---|---|---|---|---|
| Downstream HTTP client + timeout/retry/circuit breaker (Resilience4j) + WireMock tests | P0 | NOT_STARTED | A believable "Appointment Availability" or "Plan Pricing" downstream call | Notably does NOT require Docker/Postgres/any paid infra — fully locally testable with WireMock; a strong next-session candidate precisely because it has zero external blockers |

## Testing (cross-cutting)

| Capability | Priority | State | Notes |
|---|---|---|---|
| JUnit 5 + Mockito unit tests | P0 | IMPLEMENTED | CustomerServiceTest + new CustomerPreferenceServiceTest/ContractPlanServiceTest |
| Real-server integration tests (RestTemplate, not MockMvc) | P0 | IMPLEMENTED | MockMvc confirmed NOT on this Spring Boot 4.1.1 project's classpath (module split moved Jackson to `tools.jackson`) — RestTemplate + `@SpringBootTest(RANDOM_PORT)` is this project's real, working pattern |
| Testcontainers DB integration | P0 | IMPLEMENTED, CI-verified | See Data section above |
| WireMock downstream-contract tests | P0 | NOT_STARTED | Tied to the downstream-integration slice |
| Security tests (missing/malformed/expired token, wrong scope) | P0 | NOT_STARTED | Tied to the Security slice |
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

1. Downstream integration + Resilience4j + WireMock (Slice 4) — zero external infra blockers, fully testable tonight-style in any environment.
2. Spring Security + JWT resource-server (Slice 3).
3. Observability (Actuator/Micrometer/correlation IDs) — cheap, high interview value, unblocks meaningful performance work later.
4. The real end-to-end AI backend run (genuine LLM call), attempted in ISOLATION from any concurrent persistence-layer change.
5. Redis, then Kafka — both explicitly sequenced last per the original task's own slice order, and both have real external-infrastructure decisions attached.
