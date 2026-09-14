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
| Java 21 (LTS) | P2 | PRODUCTION_VERIFIED (2026-09-14) | Current LTS, a genuinely common Senior Java interview topic | `pom.xml`'s `java.version=21` (Spring Boot derives `maven.compiler.release` automatically); CI's `setup-java` bumped to match, so CI genuinely builds/runs on real JDK 21, not just compile-targeted from a different local JDK | full suite unaffected by the version bump alone | real Railway deploy confirms `Java 21.0.2` in the startup banner | records (already used for DTOs before this migration); pattern matching/virtual threads not yet adopted in source, a real future opportunity, not claimed as done | Railway's Railpack/mise-based build auto-detected Java 21 from `pom.xml` with zero build-config changes needed |

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
| Redis (cache-aside for active contract plan reads) | P1 | IMPLEMENTED (2026-09-14), CODE PRODUCTION_VERIFIED, INFRA NOT_PROVISIONED | Active plan is read on every customer-overview page load, changed only on enroll() | `cache/ContractPlanCacheService.java` (programmatic cache-aside, 60s TTL, real `cache.requests` Micrometer counter tagged hit/miss/redis-unavailable), `cache/RedisCacheConfig.java`. `ContractPlanCacheIntegrationTest` (3 tests, real Redis via Testcontainers, disabledWithoutDocker=true — skips locally, runs for real in CI) proves genuine miss-then-fill+TTL, a real hit, and eviction-after-enroll. Production Redis was deliberately NOT provisioned this session (only the one Postgres resource was Owner-approved) — this is proven, not assumed, to be safe: production is live-verified to start cleanly and serve real cache-fallback traffic correctly with no Redis reachable at all (`/actuator/prometheus` shows `cache_requests_total{result="redis-unavailable"}` incrementing on real traffic, `/actuator/health` stays UP with the Redis health indicator deliberately disabled so an intentionally-absent optional dependency can't misreport overall health). |

## Eventing

| Capability | Priority | State | Business scenario | Notes |
|---|---|---|---|---|
| Kafka (CustomerPreferenceUpdated, transactional outbox) | P1 | IMPLEMENTED (2026-09-14), CI-VERIFIED (real Testcontainers Kafka), PRODUCTION-VERIFIED SAFE-WHEN-DISABLED, INFRA NOT_PROVISIONED | PUT /customers/{id}/preferences publishes a CustomerPreferenceUpdated event | `outbox/` (OutboxEvent/OutboxEventRepository/OutboxPublisher, transactional outbox: the preference write and its event row commit atomically in one @Transactional method; a separate @Scheduled poller actually publishes to Kafka) + `messaging/` (KafkaMessagingConfig: topics + dead-letter topic + DefaultErrorHandler w/ 2-retry-then-DLT; CustomerPreferenceEventConsumer: durable processed_event idempotency ledger, not in-memory). `CustomerPreferenceEventFlowIntegrationTest` (3 tests, real Kafka via Testcontainers, disabledWithoutDocker=true) proves genuine publish-consume, a hand-crafted duplicate redelivery being a real no-op, and a poison message actually landing on the real DLT — all GREEN on GitHub Actions' real Docker runner. THREE real, previously-unknown production-blocking bugs were found and fixed getting here, all via this session's own new CI failure-annotation diagnostics (raw job logs need repo-admin auth this session didn't have) and real production log inspection: (1) `org.springframework.kafka:spring-kafka` alone is the Kafka *library*, not Spring Boot's autoconfiguration glue — Boot 4 split it into `spring-boot-kafka`, the same class of defect as the earlier Flyway incident; without it `@KafkaListener` silently never registered as a real listener at all. (2) `@Lob` on the outbox payload `String` field validates as CLOB/`oid` on Postgres, not `TEXT` — fixed via `@JdbcTypeCode(SqlTypes.LONGVARCHAR)`. (3) A REAL PRODUCTION INCIDENT: once the listener genuinely worked, its background reconnect attempts against no reachable broker flooded production logs badly enough that Railway started dropping messages ("rate limit reached for deployment"). Two targeted property fixes each solved one symptom but not the root behavior (see docs/LESSONS.md) — the actual fix is architectural: the whole Kafka subsystem is now `@ConditionalOnProperty(app.kafka.enabled)`, defaulting to `false`, so nothing attempts to connect at all until an operator explicitly sets `KAFKA_ENABLED=true` alongside a real broker. Re-deployed and independently re-verified: production logs are now clean (50 lines total for a full startup vs. Railway actively dropping messages before), the app is still fully functional (health UP, JWT-protected APIs, a real preference update still writes its outbox row transactionally even with Kafka disabled). Production Kafka infrastructure was deliberately NOT provisioned this session (same "only the one Postgres resource is Owner-approved" scope decision as Redis). |

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
| Testcontainers DB/cache/broker integration | P0 | IMPLEMENTED, CI-verified | Postgres (see Data section), Redis (`ContractPlanCacheIntegrationTest`, 3 tests), Kafka (`CustomerPreferenceEventFlowIntegrationTest`, 3 tests) — all GREEN on GitHub Actions' real Docker runner, all skip cleanly on this Docker-less dev machine |
| WireMock downstream-contract tests | P0 | IMPLEMENTED (2026-09-14) | `AppointmentAvailabilityIntegrationTest`, 7 tests |
| Security tests (missing/malformed/expired token, wrong scope) | P0 | IMPLEMENTED (2026-09-14), PRODUCTION_VERIFIED | `SecurityIntegrationTest` (12 tests) + live curl verification against real production |
| Performance/load tests (k6/Gatling/JMeter) | P1 | NOT_STARTED | No baseline established yet |
| CI pipeline running the above | P0 | PARTIAL (2026-09-14) | `.github/workflows/ci.yml` runs Java tests (incl. real Testcontainers Postgres/Redis/Kafka), a scoped offline subset of the Python AI-platform tests + evals, and Node frontend tests. A new failure-annotation step (added this session, see docs/LESSONS.md) surfaces real surefire failure detail via the public Checks API, since raw job logs need repo-admin auth this session didn't have — used to real-diagnose and fix 2 genuine Kafka/Postgres bugs live during this session. Does NOT yet run the full Python suite (several existing tests need live production credentials this CI job intentionally does not have) — a real, disclosed gap |

## Observability

| Capability | Priority | State | Notes |
|---|---|---|---|
| Actuator, Micrometer, structured logs, correlation IDs | P0/P1 | PRODUCTION_VERIFIED (2026-09-14) | `/actuator/health` public (liveness+readiness probes), `/actuator/metrics`+`/actuator/prometheus` require a valid JWT. Console logs are structured JSON (ECS format via `logging.structured.format.console=ecs`). In-process Brave tracing (`micrometer-tracing-bridge-brave`, no external collector) gives every log line a real traceId/spanId. Resilience4j circuit breaker/retry refactored to registry-backed instances so `TaggedCircuitBreakerMetrics`/`TaggedRetryMetrics` expose real state. A real `security.rejections` counter (401 vs 403, tagged by reason) was added alongside the existing JSON error handlers. `ObservabilityIntegrationTest` (4 tests) proves real meter data appears after real traffic, not just endpoint existence — live-verified against production: health public/UP, prometheus 401 without token, prometheus 200 with token showing http_server_requests/hikaricp_connections/resilience4j_circuitbreaker_state/resilience4j_retry_calls_total/security_rejections_total all present with real counts. |

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

1. The real end-to-end AI backend run (genuine LLM call), attempted in ISOLATION from any further Customer-app code change — this session made 6 substantial changes to the Customer app (Postgres, Security, Observability, Redis, Kafka, Java 21), each individually verified; avoid compounding an autonomous production-mutating AI run on top of all of them in the same session.
2. Performance baseline (k6/Gatling) once a real bottleneck-worthy scenario exists.
3. Kubernetes-ready artifacts (P2) — labeled as such, not as current production (Railway remains real production).
4. Java 21 language-feature adoption (pattern matching, virtual threads where genuinely useful) — the LTS migration itself is done; using the new features in source is a separate, smaller follow-up.

(Slice 4 — downstream integration + Resilience4j + WireMock — completed 2026-09-14, see Integrations/Resilience above. Postgres/Flyway production cutover, Spring Security + JWT resource-server, Observability, Redis cache-aside, Kafka transactional-outbox eventing, and the Java 17->21 migration — all completed and CI/production-verified 2026-09-14, see their respective sections above.)
