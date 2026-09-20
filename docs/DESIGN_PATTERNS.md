# Design Patterns Catalog — Customer App

Every pattern below is real, currently in the app, with a file reference
and a test that proves it — not a list of patterns the app "could" use.
Written so each entry doubles as an interview answer: what the pattern
is, why it was the right call HERE (not generically), and where to point
during a walkthrough. See `docs/FLAGSHIP_MARKET_COVERAGE.md` for the
broader capability matrix this catalog is a companion to.

## Structural / creational

### Strategy + Factory — notification channel dispatch
`notification/NotificationSenderFactory.java`

Spring injects every `NotificationSender` bean present on the classpath
(EMAIL, SMS, NONE) and the factory indexes them by their own declared
`channel()` at startup. Callers never branch on the channel enum or
construct a sender themselves — `getSender(channel)` resolves the right
strategy. Adding a new channel means adding one new `@Component`; the
factory itself never changes.

**Interview answer:** "Open/closed principle in practice — I can add a
push-notification channel tomorrow without touching this factory or any
caller." Test: `NotificationSenderFactoryTest`.

### DTO / anti-corruption boundary
`dto/ContractPlanResponse.java`, `dto/CustomerPreferenceResponse.java`, etc.

Entities (`ContractPlan`, `CustomerPreference`) never serialize directly
to the API. A DTO layer sits between JPA and the wire format, so a
schema change to the persistence model doesn't automatically become an
API breaking change, and JPA lazy-loading quirks never leak into a JSON
response.

**Interview answer:** "This is also why Open Session In View is
disabled — `application.properties` has the real reasoning: no entity is
ever serialized with an unresolved lazy association, by construction."

## Behavioral

### Centralized exception translation (Chain-of-Responsibility-flavored)
`exception/GlobalExceptionHandler.java`

One `@RestControllerAdvice` maps every domain exception to the right
HTTP status and a consistent `{"error": "..."}` JSON shape — currently 6
mappings (404, 400 x2, 403, 401, 409, 429), each added as its own domain
exception was introduced (`EnrollmentInProgressException` →409,
`RateLimitExceededException` →429). No controller ever hand-rolls error
JSON.

**Interview answer:** "Every new failure mode gets one exception class +
one handler method — the error-shaping concern is never duplicated
across controllers."

## Data / integration patterns

### Transactional Outbox
`outbox/OutboxEvent.java`, `outbox/OutboxPublisher.java`

The business write and its event row commit in the SAME database
transaction (see `ContractPlanService.enroll()` and
`CustomerPreferenceService.update()`), closing the classic dual-write
gap where a DB commit succeeds but a direct Kafka publish fails (or vice
versa). A separate `@Scheduled` poller publishes unpublished rows
asynchronously — Kafka being slow or down can never fail or block the
original request. Generalized in this session from one hardcoded topic
to an `eventType -> topic` registry (`KafkaMessagingConfig.EVENT_TYPE_TO_TOPIC`)
so a second event type reuses the same relay.

**Interview answer:** "This is the difference between 'eventually
consistent with a real guarantee' and 'eventually consistent, hopefully'."

### Idempotent Consumer
`outbox/ProcessedEvent.java`

Kafka's outbox/relay pattern only guarantees at-least-once delivery — a
redelivered duplicate must be a safe no-op. A durable ledger (not an
in-memory set, which would forget on restart) records what's already
processed. **Real bug found and fixed this session:** the ledger was
originally keyed by `eventId` alone, correct only when exactly one
consumer processes a given event — see the Fan-out entry below for what
broke and how it was fixed, and Triage Lab Scenario D for a live replay.

### Fan-out (pub/sub via independent consumer groups)
`messaging/ContractPlanNotificationConsumer.java`,
`messaging/ContractPlanBillingSyncConsumer.java`

Two independently-deployable consumers subscribe to the same
`contract-plan-events` topic under different consumer group IDs — Kafka
delivers each group its own full copy of every message, so both process
every event independently, one for customer notification, one for a
billing-system sync. This is what exposed the idempotency-ledger bug
above: `ProcessedEvent` keyed by `eventId` alone meant whichever
consumer wrote its row first made the other see "already processed" and
silently skip real work. Fixed with a composite `(consumerName, eventId)`
key.

**Interview answer:** "Fan-out is where a lot of teams' idempotency
design quietly breaks — it works fine with one consumer and fails
silently the moment you add a second one reading the same topic, because
nobody re-examined the 'already processed' check's scope."

### Dead Letter Queue + Saga-style compensation (the retry-vs-compensate distinction)
`messaging/KafkaMessagingConfig.java` (DLT), `messaging/ContractPlanBillingSyncConsumer.java` (compensation)

Two genuinely different failure classes, handled two genuinely different
ways:
- **Transient/technical failure** (malformed message, momentary
  connection drop) → Kafka's `DefaultErrorHandler` retries twice
  (200ms apart) then routes to a `.DLT` topic. Retrying might actually
  succeed.
- **Permanent business-rule failure** (a real external billing system
  would reject these terms every time — simulated here via a
  documented trigger, since no real billing provider is provisioned) →
  retrying can never help. The consumer catches this explicitly, writes
  a `BillingSyncCompensation` row (what needs manual reconciliation),
  sends an operations notification, and marks the event **processed** —
  never thrown back into the retry/DLT path meant for the other failure
  class.

**Interview answer:** "Treating every consumer-side failure as 'retry it'
is a real, common mistake — a permanent business rejection just burns
your retry budget and eventually dead-letters a message that was never
going to succeed. The fix isn't a smarter retry policy, it's recognizing
these are two different problems."

### Cache-Aside
`cache/ContractPlanCacheService.java`

Chosen because active-plan reads vastly outnumber writes (every
customer-overview load vs. only on `enroll()`). Deliberately
programmatic, not `@Cacheable` — hit/miss/fallback/invalidation are each
explicit, individually testable code paths. Every Redis operation is
wrapped: a read failure falls through to the database, a write/eviction
failure is logged and swallowed. Proven live in real production: no
Redis is actually provisioned there, so every production read already
takes the real fallback path today.

### Distributed Lock (token-owned, transaction-timed release)
`cache/EnrollmentLockService.java`

Layered defense-in-depth over `uq_contract_plan_one_active_per_customer`
(the DB constraint, the real correctness guarantee) — a short-TTL Redis
lock (`SETNX` + a Lua script for atomic compare-and-delete on release)
turns a losing concurrent request's outcome from a raw 500 into a clean
409. Two real design details worth naming explicitly:
1. **Token-owned release** — a lock is deleted only if the caller
   presents the exact token it was granted, via a Lua script (atomic
   GET-compare-DELETE). Without this, a slow request whose lock already
   expired could delete a *different*, later request's now-active lock
   on the same key.
2. **Release timing** — the lock is released via
   `TransactionSynchronizationManager.registerSynchronization(...afterCompletion(...))`,
   not a plain `finally`. Releasing before the transaction actually
   commits would reopen the exact race the lock exists to close.

**Interview answer:** "The DB constraint alone is already correct —
this lock doesn't add correctness, it adds a *better failure mode* for
the loser of a real race. That's a legitimate distinction worth making
explicit rather than conflating 'correct' with 'nice UX under load'."

### Rate Limiter (fixed-window, fail-open)
`security/RateLimiterService.java`

Redis `INCR` + `EXPIRE`, the simplest correct building block — chosen
explicitly over a sliding-window/token-bucket algorithm, with the
trade-off named rather than hidden: fixed-window is O(1) per request but
allows up to 2x the nominal limit across a window boundary. Fails open
on Redis unavailability, same philosophy as the cache and the lock above
— an optional protection layer being down must never take the whole
public demo offline with it.

### Circuit Breaker + Retry
`integration/appointment/AppointmentAvailabilityConfig.java`

Resilience4j core circuit-breaker + retry, composed programmatically
(not the annotation starter — a real, documented Spring Boot 4 BOM gap
at the time this was built). `SERVICE_UNAVAILABLE` is a distinct, never-
fabricated outcome from a real timeout/5xx/malformed-response, proven
against a real WireMock stub over real loopback HTTP.

## Where this list is deliberately incomplete

Not every pattern in the codebase is listed here — only the ones with a
real business motivation worth explaining in an interview, not a
checklist of GoF names for their own sake. `docs/FLAGSHIP_MARKET_COVERAGE.md`
has the full capability matrix (testing, observability, security,
delivery) this catalog doesn't duplicate.
