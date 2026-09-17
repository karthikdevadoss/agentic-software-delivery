# Interview Scenario: Design Patterns, SOLID, and System Architecture — a Guided Tour of This Codebase

Derived from the actual implementation across `app/src/main/java/com/example/customer/`. Unlike the other interview scenarios, this one is not anchored to a single incident — it is a map of where classic design patterns, SOLID principles, and system-architecture decisions already live in this real, running codebase, so they can be pointed to and explained directly rather than described in the abstract.

## Business Why

A pattern used because a textbook names it is decoration. Every pattern below exists here because it was the smallest correct answer to a real constraint (add a notification channel without touching dispatch code; wrap a flaky downstream without polluting business logic; keep a write and its side-effect event atomic). The interview value isn't "I know the Gang of Four patterns" — it's "I recognize which constraint calls for which pattern, and I can point to the exact line."

## Design Patterns, Mapped to Real Code

**Strategy + Factory — `notification/NotificationSender.java` + `NotificationSenderFactory.java`**
`CustomerPreferenceEventConsumer` needs to dispatch a notification differently per channel (EMAIL/SMS/NONE) without an `if/else` chain that grows every time a channel is added. `NotificationSender` is the Strategy interface; `EmailNotificationSender`/`SmsNotificationSender`/`NoOpNotificationSender` are interchangeable implementations; `NotificationSenderFactory` is the Factory that resolves the right one at runtime by asking Spring for every registered `NotificationSender` bean and indexing them by their own declared channel. Adding a fourth channel means adding one new `@Component` — zero existing code changes (Open/Closed Principle, below).

**Null Object — `NoOpNotificationSender.java`**
A customer whose preference is `NONE` is a real, first-class outcome, not a `null` check or a special-cased branch — it's just another Strategy that correctly does nothing (and still emits its own metric, so "the customer chose no notifications" stays observable rather than invisible).

**Decorator — `AppointmentAvailabilityService.java`**
```java
CircuitBreaker.decorateSupplier(circuitBreaker, Retry.decorateSupplier(retry, raw))
```
Textbook Decorator, applied to a functional `Supplier`: each layer wraps the call with one additional cross-cutting behavior (retry, then circuit-breaking) without the wrapped code knowing it's wrapped. Composition **order** is itself a real design decision — the breaker wraps the retry, not the reverse, so an open circuit fails fast before any retry is even attempted (see `07-appointment-resilience.md`).

**Adapter — `AppointmentAvailabilityClient.java`**
Translates this application's own internal request/response shape to and from a downstream HTTP service's actual wire format, so `AppointmentAvailabilityService` (and everything above it) never depends on the downstream's specific contract — only this one class would change if the real downstream's API shape changed.

**Repository — every `*Repository` interface (Spring Data JPA)**
The persistence-access abstraction GoF's Repository pattern describes, generated from an interface by Spring Data — `CustomerService`/`ContractPlanService`/`CustomerPreferenceService` depend on a repository interface, never on JPA/Hibernate/SQL directly.

**Facade — the `service/` layer itself**
`CustomerService`/`ContractPlanService`/`CustomerPreferenceService` each present one simple, coarse-grained API to their controller, hiding the coordination of repository calls, validation, and (for preferences) outbox-event publication behind it.

**Event-driven / durable Observer — the transactional outbox (`outbox/OutboxPublisher.java`)**
A preference write and its "notify downstream" side effect must both survive — or both roll back — together, without a synchronous call to a message broker inside the database transaction (the dual-write problem). The outbox table **is** the durable Subject; `OutboxPublisher`'s scheduled poll is the durable notification mechanism; `CustomerPreferenceEventConsumer` is the Observer. See `05-kafka-transactional-outbox.md` for the full write-up.

**Builder (implicit) — Java `record`s for every DTO/event**
This codebase uses Java 21 records (`CustomerPreferenceUpdatedEvent`, `ContractPlanResponse`, etc.) rather than a hand-written GoF Builder — the modern JVM answer to the same underlying goal (immutable, validated construction of a value object) with less boilerplate and compiler-enforced immutability GoF's original pattern could not provide.

**Singleton (container-managed) — every `@Component`/`@Service`/`@Repository`**
Spring's default bean scope **is** the Singleton pattern, correctly delegated to a container instead of hand-rolled (a hand-written Singleton with a private constructor and static `getInstance()` is what Spring replaces here — and the container version is trivially mockable/testable, unlike the classic version).

## SOLID, Mapped to Real Code

- **Single Responsibility** — three separate services (`Customer`, `ContractPlan`, `CustomerPreference`), never one God Service; three separate `NotificationSender` implementations, never one class with a channel `switch`.
- **Open/Closed** — `NotificationSenderFactory` again: adding `NotificationChannel.PUSH` tomorrow means one new class, zero edits to the factory or the consumer that uses it.
- **Liskov Substitution** — any `NotificationSender` is interchangeable with any other from the caller's perspective; `NotificationSenderFactoryTest` proves this directly (the factory is constructed with different subsets of senders across tests, behaving correctly regardless of which concrete implementations are present).
- **Interface Segregation** — `NotificationSender` has exactly two methods (`channel()`, `send()`) — no fat interface forcing an implementation to support behavior it doesn't need.
- **Dependency Inversion** — `CustomerPreferenceEventConsumer` depends on `NotificationSenderFactory` (an abstraction over which concrete sender runs), and `AppointmentAvailabilityService` depends on `Retry`/`CircuitBreaker` beans injected in, never constructed inline — every collaborator arrives via constructor injection, which is also what makes every test above able to substitute a real `SimpleMeterRegistry` or a real embedded WireMock server instead of the real production dependency, with zero mocking framework needed.

## System Architecture, at a Glance

```
Client
  |
  v
Controller layer   (validation, HTTP concerns only)
  |
  v
Service layer      (business rules, transaction boundaries, orchestration)
  |
  +--> Repository layer (Spring Data JPA)      --> PostgreSQL
  +--> Outbox table (same transaction)          --> OutboxPublisher --> Kafka --> Consumer
  +--> Cache-aside (ContractPlanCacheService)   --> Redis (fail-open on Redis being down)
  +--> Resilience4j-wrapped client              --> downstream HTTP service (Appointment Availability)
```

**Why layered, not a single fat controller-does-everything class:** each layer has one reason to change — a validation-rule change touches the controller/DTO layer, a business-rule change touches the service layer, a schema change touches the repository/migration layer — the same reasoning as SRP, applied at the architecture level rather than the class level.

**Why the outbox instead of a direct synchronous call to Kafka inside the request:** a request thread should never block on a message broker's availability, and a broker publish must never be allowed to "succeed" in a way that's inconsistent with whether the database transaction that produced it actually committed. The outbox row and the business row commit atomically in one transaction; publishing is a separate, retryable, at-least-once concern handled entirely asynchronously (see `05-kafka-transactional-outbox.md`).

**Why cache-aside over `@Cacheable`:** a `@Cacheable` annotation hides the hit/miss/fallback/invalidation logic behind Spring AOP, making each path individually untestable and un-observable. `ContractPlanCacheService` makes each path an explicit, separately-testable method — including the fail-open behavior on a Redis outage, which is exactly the kind of behavior an annotation-based cache would make hard to verify (see `06-redis-cache-aside.md`).

**Why defense-in-depth security, not one authorization check:** JWT signature/expiry validation (Spring's resource-server layer) + RBAC (`@PreAuthorize`-style role checks) + workspace isolation (`WorkspaceAccessGuard`, an explicit ownership check independent of the role check) are three separate, independently-testable layers — a bug in any one does not by itself grant unauthorized access (see `01-rbac-and-workspace-isolation.md` and `08-security-attack-matrix.md`).

## What Changes at 10x / 100x Scale

- **Service decomposition boundary:** today's single Spring Boot deployable already has clean internal seams (`security`/`integration`/`messaging`/`outbox`/`cache` as distinct packages with narrow dependencies on each other) — at real multi-team scale, the Appointment-integration slice and the Preference/notification slice are the two most natural first extraction points into their own deployables, since they already communicate only through an HTTP client and an event topic, never a shared in-process call.
- **Kafka partitioning:** the outbox topic is currently a single logical stream; at high volume, partitioning by `customerId` (already the message key) preserves per-customer ordering while allowing horizontal consumer scale-out — the code changes needed are zero, since the key is already set correctly today.
- **Read/write separation:** `ContractPlanCacheService`'s cache-aside layer is already a lightweight CQRS-style read path distinct from the write path (`ContractPlanService.enroll()`) — at much higher read volume, this is the natural seam to add read replicas behind, without touching the write path's transactional guarantees.
- **API Gateway / BFF:** today's clients call this service's REST API directly; at real multi-client (web + mobile + partner) scale, a gateway would centralize rate limiting, auth-token translation, and request aggregation — none of which this single-service portfolio scope currently needs, so it's honestly not built, not silently assumed away.
- **Database:** a single PostgreSQL instance is correct at this scale; sharding or read-replica promotion would only be justified by a real, measured bottleneck, never speculatively — the same "don't provision what isn't needed yet" discipline already applied to Kafka/Redis in this project (see `docs/PROJECT_STATE.json`'s `KNOWN_LIMITATIONS`).

## Interview Questions This Answers

- "Walk me through a design pattern you've used recently and why it was the right choice, not just a familiar name."
- "How do you decide when to introduce a new abstraction (interface + factory) versus an `if/else`?"
- "Explain SOLID with real examples from a codebase you've actually written, not a diagram."
- "What's the difference between a layered monolith and a poorly-organized one — how do you know which one you're looking at?"
- "How would this system's architecture need to change at 10x the current scale, and what would deliberately *not* change?"
- "Why cache-aside instead of an annotation-based cache — what does the annotation hide that matters?"

## Live Demo / Evidence Links

- `app/src/main/java/com/example/customer/notification/` (Strategy + Factory + Null Object, real source)
- `app/src/test/java/com/example/customer/notification/NotificationSenderFactoryTest.java` (real, non-mocked tests)
- `app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityService.java` (Decorator)
- `app/src/main/java/com/example/customer/outbox/` (durable Observer / event-driven architecture)
- `app/src/main/java/com/example/customer/cache/ContractPlanCacheService.java` (explicit cache-aside, not `@Cacheable`)
- `docs/interview-scenarios/05-kafka-transactional-outbox.md`, `06-redis-cache-aside.md`, `07-appointment-resilience.md`, `01-rbac-and-workspace-isolation.md` (the deeper write-ups each pattern above points back to)
