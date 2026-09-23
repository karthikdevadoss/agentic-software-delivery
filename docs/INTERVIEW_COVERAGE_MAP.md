# Interview coverage map: every mechanism, where it lives, where it is shown

Status: DRAFT for Owner review, 2026-09-23. Not yet the source of any page.

## 1. The rule this document enforces

Every piece of work in this repository has a stated reason and is shown in
one of three places, each with a GitHub-level code reference:

1. **Dashboard capability matrix** (live): generated from
   `docs/PORTFOLIO_CAPABILITIES.yaml`. One row per capability with problem,
   technology, modules, evidence links, interview topics.
2. **Role showcase pages** (`/api/showcase/<slug>`, live): a role-specific
   subset of the same registry plus narrative. Today one showcase exists
   (`senior-java-ai-transformation`, 13 capabilities).
3. **Technical mechanisms page** (PLANNED, first Sprint 7 item): one entry
   per mechanism, built for reading: problem, exact code path, the test
   that proves it, how to run it, how to break it. Generated from the same
   registry so nothing is maintained twice.

The Usage page keeps its own job: the economics of the AI-assisted work
(tokens, cost, time, retries, human intervention). It does not list
mechanisms.

Definition of done for every backlog item from Sprint 7 on: code in the
shape it had at the real employer + a test observed failing first + a
registry entry with code references and interview topics + the row it
produces on the mechanisms page. An item without a registry entry is not
done.

**The app is a technical replica of the Owner's real work at three real
employers, not a product optimized on its own terms** (Owner directive,
2026-09-23). The design goal is never "what would make this app better" --
it is "does this row genuinely reflect a real tool, technology or
technical situation the Owner handled at NRG, BCBSA or Marsh." Nothing
real should be missing from this map for lack of looking; nothing should
be added because it would be a nicer architecture choice in the abstract.

**Selection rule when more than one employer touched the same general
technical situation**: NRG takes priority, since it is the deepest and
most current evidence. A different employer's version of the SAME
situation is only added as a SEPARATE build item when NRG never covered
that situation at all, or when the other employer's real implementation
is genuinely distinct in mechanism (a different real technology, pattern,
or constraint), not merely the same idea restated. Two concrete examples
this rule already produced: the Marsh/pre-serverless SQS worker-queue
pattern is real but stays a TALKING POINT, not a build item, because
NRG's BL-045 (Lambda + SQS + DLQ) already covers queue-based background
processing more completely; the HMAC+AES partner-payload security row
(BL-054) is tagged Marsh only, since that is the one employer with
confirmed evidence so far -- BCBSA gets added to it, or gets its own
separate row, only once BCBSA's own real evidence is reviewed and found
to be a genuinely different mechanism, never combined speculatively ahead
of that. This rule applies to sections 2-9 and 12 below (real domain/
architecture mechanisms mapped to employer experience). It does not apply
to section 10 (this project's own testing discipline) or section 11
(this project's own AI-delivery platform), which describe how this
project builds itself, not what the Owner did at an employer.

Status vocabulary used below:

- **BUILT**: in the code, tested, listed in the registry.
- **BUILT, UNLISTED**: in the code and tested, but no registry entry yet,
  so not visible on any page. Fix: registry entry only.
- **PLANNED BL-nnn**: sized or to be sized in `docs/BACKLOG.json`.
- **NEW**: found by this map, not in the backlog yet. Needs sizing.
- **TALKING POINT**: deliberately not built; the interview answer comes
  from real experience, and the reason it is not built is stated.
- **EXCLUDED**: needs a corporate-scale setup that is too costly or
  pointless to recreate; the reason is stated.

## 2. Core Java and Spring

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| REST API with validation, central exception handling, OpenAPI | BUILT | `app/.../CustomerController.java`, `GlobalExceptionHandler.java`, springdoc | Marsh |
| RFC 9457 ProblemDetail error responses | NEW | Spring 6 `ProblemDetail`; replace ad-hoc error JSON on one service | Marsh |
| Pagination, sorting, filtering with JPA Specifications | NEW | `Pageable` exists in 2 files; no filter/spec example yet | Marsh |
| `@Transactional` boundaries, propagation, rollback rules | BUILT, UNLISTED | 12 files; needs one registry entry plus a test showing rollback on a checked vs unchecked exception | Marsh |
| Optimistic locking with `@Version`, two-thread conflict test | PLANNED BL-064 | plan swap | NRG |
| Pessimistic locking and isolation levels (`SELECT FOR UPDATE`, REPEATABLE READ) | NEW | one deliberate example next to BL-064 so both can be compared | NRG |
| Java 21 features in use: records, sealed interfaces, pattern matching | BUILT, UNLISTED | `LegacyPlanPricingOutcome` (sealed), records across services | Marsh |
| Virtual threads for blocking I/O fan-out | NEW | switch the BFF executor to virtual threads behind a property, measure | NRG |
| `CompletableFuture` composition with timeouts | BUILT | `DashboardAggregationService` (BL-039) | NRG |
| Scheduled jobs with a controllable clock | PLANNED BL-067 | prepay alerts | NRG |
| Distributed scheduling lock (ShedLock) so a job runs once across instances | NEW | pairs with BL-067; a real multi-instance question | NRG |
| Spring Batch style file import/export job | NEW | monthly usage file import; decide if worth it (NRG had batch via SAP, not Spring Batch) | NRG |
| Bean lifecycle, proxies, why `@Transactional` self-invocation fails | TALKING POINT | explained from code already present; a small failing test could be added cheaply | Marsh |

## 3. Data

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| PostgreSQL + JPA + Flyway versioned migrations (10 scripts) | BUILT | `app/src/main/resources/db/migration` | Marsh |
| Testcontainers Postgres in CI | BUILT | 10 test files, CI job | Marsh |
| N+1 detection and fix (fetch join, `@EntityGraph`, projections) | NEW | one documented N+1 with a Hibernate statement-count assertion | Marsh |
| Index and explain-plan reasoning on one slow query | NEW | migration adding an index plus a note with the real plan before/after | Marsh |
| HikariCP pool sizing and pool-exhaustion incident reproduced | NEW | test that holds connections and shows the timeout; ties to the real idle-in-transaction incident in LESSONS.md | Marsh |
| Oracle-style stored procedure call over JDBC | NEW | `SimpleJdbcCall` against a Postgres function standing in for an Oracle procedure (NRG Oracle usage was JDBC + procedures) | NRG |
| JPA auditing (created/modified by/at) and an audit trail table | NEW | pairs with BL-068 opt-in audit | Marsh |
| Append-only ledger with a projected balance (event-sourcing shape) | PLANNED BL-069 | loyalty points | NRG |
| MongoDB as a secondary store | PLANNED BL-053 | Marsh | Marsh |
| DynamoDB single-table access from Lambda | PLANNED BL-045 | NRG 2025 | NRG |
| Search index (Lucene) | PLANNED BL-050 | low priority | NRG |
| Relational DB Views, Sequences and Triggers, managed by a DB admin team (RazorSQL) | NEW | real Marsh mechanism (JobDuties doc); exact RDBMS product not personally confirmed by name -- do not guess Oracle | Marsh |
| Sharding, read replicas, multi-region data | EXCLUDED | needs real load and infra; answered from design knowledge | — |

## 4. Security

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| BCrypt passwords, JWT login, USER/ADMIN roles, workspace isolation | BUILT | `security-jwt-rbac` | Marsh |
| RS256 JWT, JWKS, `kid` rotation, foreign-key rejection tests | BUILT | `asymmetric-jwt-jwks` (Sprint 6) | NRG |
| Method-level authorisation (`@PreAuthorize`) | NEW | none found; add on one admin endpoint with a negative test | Marsh |
| CORS policy | NEW | none found; one explicit config with a test, a very common question | Marsh |
| CSRF stance for a stateless API, stated and tested | BUILT, UNLISTED | 5 files; registry entry | Marsh |
| IDOR fix: opaque encoded identifiers for documents | PLANNED BL-048 | the real invoice-encoding incident | NRG |
| PCI boundary: tokenised card data, PAN never stored or logged | PLANNED BL-066 | autopay | NRG |
| HMAC request signing + AES field encryption for a partner API | PLANNED BL-054 | confirmed real at Marsh (AES-256 + HMAC payload signing, JobDuties doc); BCBSA not yet reviewed -- add BCBSA only if its own evidence shows a genuinely distinct mechanism, per the NRG-priority rule in section 1 | Marsh |
| PII masking in logs | BUILT, UNLISTED | 3 files; registry entry plus a log-capture test | Marsh |
| Secrets handling: env-injected keys, registry of names, never values | BUILT | `docs/SECRETS_REGISTRY.md`, `JWT_PRIVATE_KEY` env | Marsh |
| OWASP dependency check in CI | BUILT, UNLISTED | CI step (informational) | Marsh |
| Custom authorizer on API Gateway (Lambda) | PLANNED BL-045 | NRG 2025 | NRG |
| OIDC login with an identity provider (Cognito / FusionAuth / Keycloak) | TALKING POINT | validating their RS256 tokens is built; running an IdP locally adds a container but no new mechanism. Revisit if a role asks for OAuth2 login flows | NRG |
| Rate limiting at the gateway | PLANNED BL-075 | | Marsh |

## 5. Messaging and events

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| Transactional outbox, publisher, partition key by aggregate | BUILT | `kafka-outbox` | BCBSA |
| Two consumer groups on one event, per-consumer idempotency table | BUILT | `ProcessedEvent`, `ContractPlanEnrollmentEventFlowIntegrationTest` | BCBSA |
| Dead-letter topic for poison messages | BUILT, UNLISTED | `DefaultErrorHandler` + DLT test; registry entry | BCBSA |
| In-app compensation on a permanent business failure | BUILT, UNLISTED | `BillingSyncCompensation`; registry entry | BCBSA |
| Cross-service orchestrated saga with a state machine and compensating step | PLANNED BL-062 | DPP | NRG + BCBSA |
| Scheduled job publishing events | PLANNED BL-067 | | NRG |
| Ordering guarantees, rebalancing, consumer lag, exactly-once semantics | TALKING POINT | partly demonstrable: add one test showing ordering per key; lag monitoring needs a real broker under load | BCBSA |
| Schema registry / Avro contracts | TALKING POINT | JSON envelopes are the real NRG/BCBSA shape; add only if a JD asks | BCBSA |
| SQS with DLQ and redrive | PLANNED BL-045 | | NRG |

## 6. Caching and concurrency

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| Redis cache-aside with TTL and eviction on write | BUILT | `redis-cache`, `ContractPlanCacheIntegrationTest` | Marsh |
| Redis distributed lock for concurrent enrolment, clean 409 not 500 | BUILT, UNLISTED | `EnrollmentLockService`, concurrency test; registry entry | NRG |
| Cache stampede protection (single-flight / lock on miss) | NEW | small addition to the cache service with a concurrent test | Marsh |
| Slow stable data cached (usage, projected bill) | PLANNED BL-065 | | NRG |
| Idempotency keys on retried writes | PLANNED BL-063 | Transfer of Service | NRG |
| Optimistic vs pessimistic locking | PLANNED BL-064 + NEW | see section 2 | NRG |

## 7. Resilience and integration

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| Timeout + retry + circuit breaker around a downstream HTTP call | BUILT | `downstream-resilience` | NRG |
| Legacy system facade with honest Confirmed / NotRecognized / Unavailable outcomes | BUILT | `LegacyBillingSystemClient` (ACT-013), stub service (BL-038) | NRG |
| BFF parallel fan-out with per-call timeouts and partial results | BUILT | `bff-aggregator-fan-out` | NRG |
| Bulkheads and gateway rate limiting | PLANNED BL-075 | | Marsh |
| Feature flags and a read-only maintenance mode | PLANNED BL-047, BL-073 | the SAP monthly window | NRG |
| Outbound-request assertion convention (headers, credentials on the real request) | BUILT | WireMock in 15 test files | Marsh |
| SOAP client over WSDL with fault handling | PLANNED BL-043 | the daily NRG debugging path; highest-priority gap | NRG |
| GraphQL schema + resolvers + data loader over the BFF | PLANNED BL-044 | | NRG |
| Apache Camel route | PLANNED BL-052 | Marsh | Marsh |
| ACORD-standard carrier-data normalization layer (canonical model, adapter per carrier) | PLANNED BL-076 | the real distinctive Marsh mechanism (M2Broker/Bluestream); own bounded context, no collision with NRG code | Marsh |
| HL7 FHIR facade | PLANNED BL-051 | BCBSA | BCBSA |
| Fire-and-forget analytics client | PLANNED BL-049 | low priority | NRG |
| Email/SMS provider stand-in with retries | BUILT, UNLISTED (partly) | notification-service; confirm what exists before listing | NRG |
| Webhook receiver with signature verification | NEW | pairs with BL-054; common partner-integration question | Marsh |
| API versioning and deprecation headers | PLANNED BL-074 | | NRG |
| Correlation id propagated across services and into logs (MDC) | NEW | traceId exists via Brave; add an explicit `X-Correlation-Id` filter and a propagation test | Marsh |

## 8. Cloud, serverless, containers

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| Java Lambda handlers, custom authorizer, SQS + DLQ, DynamoDB, SES, Secrets Manager, SAM template, local run with SAM CLI | PLANNED BL-045 | needs SAM CLI + Docker Desktop | NRG |
| AWS SQS worker-queue pattern for background job processing (pre-serverless, EC2-based) | TALKING POINT | real at Marsh (2018-19) too, but NRG's BL-045 (Lambda + SQS + DLQ) already covers the general scenario more completely -- per the NRG-priority rule in section 1, do not build this separately; mention the earlier, simpler Marsh version from real experience only | NRG + Marsh |
| Docker image per service, Swarm-style stack file, per-profile config | PLANNED BL-055 | `app/Dockerfile` exists; services do not | NRG |
| Multi-brand context propagated gateway to services | PLANNED BL-070 | NRG core shape | NRG |
| Spring profiles and config-drift gate | BUILT | `deterministic-static-gates` | Marsh |
| Externalised config server / parameter store | TALKING POINT | env + profiles are the real NRG shape; a config server adds infra without a new idea | Marsh |
| Kubernetes deployment, HPA, probes | TALKING POINT | NRG ran Swarm and ECS Fargate, not Kubernetes; readiness/liveness probes are built. Revisit only for a Kubernetes-heavy JD | Marsh |
| Blue-green / canary release | TALKING POINT | Railway offers no traffic split; the deployment-identity verification pipeline is the demonstrable part | Marsh |
| Terraform / infrastructure as code | TALKING POINT | SAM template (BL-045) covers IaC; Terraform only if a JD asks | NRG |

## 9. Observability and operations

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| Structured ECS logs, health probes, Micrometer metrics | BUILT, UNLISTED | 29 files with metrics; registry entry | Marsh |
| Distributed tracing with the same traceId across three services | BUILT, UNLISTED | hand-wired Brave (LESSONS.md); registry entry | Marsh |
| Cache hit/miss counters | BUILT | `cache.requests` meter | Marsh |
| Correlation id in logs | NEW | see section 7 | Marsh |
| Production incident write-ups with root cause | BUILT | `docs/LESSONS.md`, six on the showcase page | — |
| Runbook / on-call procedure for one scenario | NEW | one `docs/runbooks/` entry (maintenance window) mirroring the NRG on-call KT | NRG |
| JVM diagnostics: thread dump on pool exhaustion, heap growth reproduced | NEW | one test-driven reproduction each; cheap and frequently asked | Marsh |
| Dashboards, alerting, SLOs (Dynatrace / Uptime Kuma / Cabot) | TALKING POINT | metrics are exported; a real alerting stack is infra, not code | NRG |
| Log aggregation (Splunk / CloudWatch) | EXCLUDED | infra only | — |

## 10. Testing and quality

| Mechanism | Status | Where in code / evidence | Real client project |
|---|---|---|---|
| Unit, integration (Testcontainers), WireMock, security negative tests | BUILT | across app and services | Marsh |
| Real multi-process topology tier, gating in CI | BUILT | `real-topology-gating-tier` | Marsh + NRG |
| Coverage floor enforced (JaCoCo 0.80, actual 0.90) | BUILT | `app/pom.xml` | Marsh |
| Test observed failing before trusted | BUILT (rule) | CLAUDE.md, RETRO_LOG evidence | Marsh |
| Slice tests (`@WebMvcTest`, `@DataJpaTest`) | NEW | none found; add one of each so the testing-pyramid answer has code | Marsh |
| Contract tests between services (Spring Cloud Contract or Pact) | NEW | Marsh partner APIs (confirmed); one consumer-driven contract | Marsh |
| Architecture tests (ArchUnit) | NEW | layer rules; cheap, often asked | Marsh |
| Mutation testing (PIT) on one module | NEW | proves "coverage is not fault detection", the research point already cited | Marsh |
| Load test with numbers (k6 or Gatling) against the BFF | NEW (4 grep hits, verify) | one script, one recorded result | NRG |
| Playwright end-to-end spec | BUILT, UNLISTED | Sprint 4; registry entry | Marsh |
| Static gates, config-drift gate | BUILT | | Marsh |
| Source-control governance: Git/Bitbucket + Jira integration, 2FA, IP whitelisting | TALKING POINT | real Marsh SDLC practice; no code planned | Marsh |

## 11. AI-engineering delivery (already the strongest section)

| Mechanism | Status |
|---|---|
| Agentic pipeline with approval bound to sha256(path, content) | BUILT |
| RAG + embeddings + MCP with measured evals | BUILT |
| Independent QA evaluator with tool-level restrictions | BUILT |
| Test impact analysis and selective regression | BUILT |
| Durable event ledger, dev-session telemetry, cost transparency | BUILT |
| Deployment-identity-verified production checks | BUILT |
| Scrum-for-AI calibration loop with six sprints of data | BUILT |
| Cost per verified outcome on the Usage page | PLANNED BL-058 |
| Workbench vs direct-session usage share | PLANNED BL-059 |
| Model-neutral run against a non-Claude model | NEW | the one asserted-but-untested claim on the showcase page |

## 12. Design-level questions and how each is answered

| Question type | Answer source |
|---|---|
| "Design a billing/enrolment system" | the services topology, saga, outbox, idempotency, locking, all in code |
| "How do you handle a slow or dead dependency" | facade outcomes, breaker, BFF partial results, maintenance mode |
| "How did one deployment serve several brands" | BL-070 context propagation |
| "How do you keep card data out of scope" | BL-066 tokenisation |
| "How do you integrate a legacy SOAP/SAP system" | BL-043 SOAP hop + facade |
| "How do you migrate to serverless" | BL-045 plus the real 2025 story |
| "How do you evolve an API without breaking mobile" | BL-074 |
| "Consistency vs availability, CAP" | TALKING POINT, illustrated by outbox vs synchronous call choices in DECISIONS.md |
| "Scale to 10x traffic, sharding, multi-region" | EXCLUDED as code; answered from design knowledge |
| "Walk me through a production incident" | six real incidents in LESSONS.md, plus the NRG offer outage / e-disconnect / IDOR stories in the private record |
| Architecture decision records | BUILT: `docs/DECISIONS.md` |
| Threat model for the platform | NEW: one short STRIDE-style table for the Workbench approval boundary |

## 13. Deliberately not recreated, with the reason

- Kubernetes cluster, service mesh: not used at NRG (Swarm, Fargate); only if a JD demands it.
- Real IdP (Cognito/FusionAuth) running locally: token validation is built; the IdP adds infra, not a mechanism.
- Log aggregation, APM, alerting stack: infra and licences; metrics and traces are exported and can be pointed at any backend.
- Multi-region, sharding, read replicas: need real load to mean anything.
- Schema registry, Avro: not the real NRG/BCBSA shape.
- SAP itself: the SOAP stand-in (BL-043) reproduces the boundary, which is what interviews ask about.

## 14. Counts

- BUILT and listed: 17 registry entries.
- BUILT but unlisted: 12 mechanisms (registry entries only, one SMALL item).
- PLANNED in backlog: 24 items (BL-043 to BL-075 minus descoped talking points).
- NEW from this map: about 20, most SMALL, a few MEDIUM.
- TALKING POINT / EXCLUDED: 14, each with a stated reason.
