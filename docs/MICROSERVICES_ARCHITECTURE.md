# Microservices Architecture — Design Decisions

Real design decisions, made before any code, per this project's own
"Task contract before substantial work" policy. Every choice below is
labeled: confirmed from the Owner's real NRG experience, or a defensible
architectural choice made where the Owner was unsure/unavailable to
confirm — never presented as a claim about NRG's actual system when it
isn't one.

## What this is, and what it deliberately is NOT

This is a genuine multi-service decomposition of the same domain the
existing `app/` (the monolithic Customer App) already models —
**built alongside it, not replacing it**. `app/` stays exactly as it
is: live, deployed, CI-verified, untouched. This new work lives under
`services/`. Whether/when to actually migrate production traffic is a
real, separate decision for later — building this is not itself a
commitment to cut over.

## Source of each decision

| Decision | Source |
|---|---|
| 4 domain services: Customer, Billing, Notification, Metering | **Confirmed** — Owner's real NRG service boundaries |
| REST for synchronous inter-service calls | **Confirmed** — Owner's real recollection |
| API Gateway present | **Confirmed** |
| Service discovery present | **Confirmed** |
| Owner designed service boundaries, reviewed by lead | **Confirmed** — informs how this is described (a real design responsibility, not just implementation) |
| Whether NRG also used async messaging between services | **Unconfirmed** — Owner wasn't sure and went to sleep before answering. Not assumed either way for the NRG claim itself. |
| Kafka used for the Notification service specifically, in THIS build | **Claude's architectural choice**, not a claim about NRG — notifications are a textbook async use case, and this codebase already has real, tested Kafka eventing (`ContractPlanEnrolled` -> fan-out consumers) to build on rather than re-invent. If the Owner confirms NRG used REST-only, this one integration point can be switched to a REST call with no other redesign needed. |
| Spring Cloud Gateway + Netflix Eureka specifically | Claude's choice — the standard, real Spring Cloud tools for this (not the only valid choice; Consul/Kubernetes-native discovery are real alternatives, Eureka is the most common Spring-ecosystem default and keeps this consistent with the app's existing all-Spring stack) |

## Service boundaries

| Service | Port (local) | Owns | Real endpoints |
|---|---|---|---|
| **customer-service** | 8081 | `Customer`, `CustomerPreference`, auth/JWT issuance (`DemoIdentity`) | `POST /customers`, `GET/PUT /customers/{id}`, `GET/PUT /customers/{id}/preferences`, `POST /auth/login`, `POST /auth/demo-token`, `GET /auth/personas` |
| **billing-service** | 8082 | `ContractPlan`, enrollment logic, the Redis distributed lock | `GET/POST /customers/{id}/plan` |
| **notification-service** | 8083 | Notification senders (EMAIL/SMS), Kafka consumers | `POST /notifications/send` (direct/manual trigger) + Kafka consumption of `ContractPlanEnrolled`/`CustomerPreferenceUpdated` |
| **metering-service** | 8084 | **NEW domain** — `MeterReading` (usage/consumption) | `POST /customers/{id}/meter-readings`, `GET /customers/{id}/meter-readings`, `GET /customers/{id}/usage-summary` |
| **api-gateway** | 8080 | Routing only, no business logic | Single public entry point, routes by path to the above via Eureka-discovered instances |
| **eureka-server** | 8761 | Service registry only | Standard Eureka dashboard |

Why Customer Service owns auth: identity is the natural home for
credential issuance in this domain, and it avoids inventing a 6th
"auth service" with no other real responsibility.

## Real inter-service communication

- **Billing -> Customer** (real REST call, not assumed to exist):
  Billing needs to confirm a customer exists before enrolling them in
  a plan. Reuses the EXACT pattern already proven in this codebase
  (`AppointmentAvailabilityClient`) — Spring `RestClient` + Resilience4j
  circuit breaker + retry, resolved via Eureka's `DiscoveryClient`
  instead of a hardcoded URL. `SERVICE_UNAVAILABLE` stays a distinct,
  never-fabricated outcome, same as today.
- **Billing -> Kafka -> Notification** (async, existing pattern reused):
  `ContractPlanEnrolled` published via the same transactional-outbox
  pattern already in `app/`, consumed independently by Notification
  Service.

## Auth pattern

Every service independently validates JWTs as its own OAuth2 resource
server (same `NimbusJwtDecoder` config as `app/`'s `SecurityConfig`,
same shared HMAC signing secret via env var). **Deliberate choice**:
no central session, no single point of trust failure beyond the shared
key itself — the Gateway passes the `Authorization` header straight
through untouched; it does not re-issue or strip it. This is a real,
defensible pattern (stateless validation at every service) versus the
alternative (gateway validates once, passes a trusted header downstream)
— the trade-off is worth naming explicitly in an interview: this
choice trades a little redundant validation work for zero shared-trust
surface between services.

## Data

Each service gets its **own** database (H2 in-memory locally, matching
`app/`'s existing local-dev pattern — a real production version would
mean 4 separate provisioned Postgres instances, a real cost/infra
decision left for later, same as Redis/Kafka in `app/` today). No
shared schema, no cross-service foreign keys — a service that needs
another service's data asks for it over the network (see Billing ->
Customer above), never reaches into another service's tables directly.
This is the actual point of the exercise: real service independence,
not a monolith with extra network hops.

## Build/deploy

Each service is a fully independent Spring Boot Maven project (its own
`pom.xml`, own `mvnw`), not modules of one parent reactor build — matches
how they'd actually be deployed independently (4+ separate Railway
services eventually, a real cost decision for the Owner, not made here).
Spring Cloud version: `2025.1.2` (verified compatible with Spring Boot
4.1 via Spring's own release notes before committing to it), managed via
the Spring Cloud BOM in each service needing it (Gateway, Eureka client)
rather than pinning individual artifact versions by hand.

## What's explicitly deferred

- Metering data feeding into real billing calculations (a real future
  integration point, not built this pass — scope discipline, not an
  oversight)
- Distributed tracing ACROSS services (each service already has Brave
  tracing internally; correlating a traceId across a real service-to-
  service call chain is real, valuable, and a genuine next step once
  the services exist to correlate)
- Actually deploying any of this to Railway — stays local/CI only
  until the Owner reviews, same standing instruction as the rest of
  tonight's work
