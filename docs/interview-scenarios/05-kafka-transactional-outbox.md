# Interview Scenario: Kafka — Transactional Outbox, At-Least-Once, Idempotent Consumer

Derived from the actual implementation: `app/src/main/java/com/example/customer/outbox/*`, `app/src/main/java/com/example/customer/messaging/*`, and two real production incidents (see docs/LESSONS.md and `verification_state.flagship_kafka_transactional_outbox`/`flagship_java21_and_kafka_log_flood_incident` in docs/PROJECT_STATE.json).

## Business Why

When a customer updates their preferences (paperless billing,
notification channel), other systems (billing, notifications) need to
know — but the preference write itself must never fail or block because
a downstream message broker is briefly unavailable, and a subscriber
must never see the same update applied twice.

## Requirement

- The preference write and the fact "an event about this should be
  published" must be atomic — no window where one happens without the
  other (the classic **dual-write problem**: writing to a database and
  publishing to a broker as two separate operations can never be made
  perfectly atomic across two different systems).
- Delivery is **at-least-once** (Kafka's real guarantee) — the consumer,
  not the transport, is responsible for idempotency.
- A malformed/poison message must not loop forever; it must land on a
  dead-letter topic after bounded retries.

## Architecture

```
CustomerPreferenceService.update(...)         [ONE @Transactional method]
   |-- save the CustomerPreference row (JPA)
   |-- save an OutboxEvent row (JPA)            <-- same transaction, same commit
   v
(transaction commits -- both rows exist, or neither does)

OutboxPublisher (@Scheduled, fixedDelay=2000ms)
   |-- SELECT ... WHERE published_at IS NULL ORDER BY created_at LIMIT 20
   |-- for each: kafkaTemplate.send(...).get(5, SECONDS)
   |-- on success: markPublished() + save()      <-- only NOW marked done
   |-- on failure: leave unpublished, log, next poll retries it
   v
Kafka topic: customer-preference-events

CustomerPreferenceEventConsumer (@KafkaListener, @ConditionalOnProperty app.kafka.enabled)
   |-- existsById(envelope.eventId()) in processed_event (durable table)?
   |      yes -> skip, increment duplicate-skipped counter, return
   |-- else: process, then save ProcessedEvent(eventId)     <-- same @Transactional method
   v
(malformed message) -> DefaultErrorHandler retries twice -> DeadLetterPublishingRecoverer -> DLT topic
```

## Java/Spring Implementation

The two correctness-critical lines are easy to get subtly wrong:

```java
// OutboxPublisher — publish, THEN mark published (never the reverse)
kafkaTemplate.send(TOPIC, key, json).get(5, TimeUnit.SECONDS);
event.markPublished();
outboxEventRepository.save(event);
```
If this were reordered (mark published, then send), a crash between the
two lines would permanently lose the event — it would look published but
never actually reach Kafka.

```java
// Consumer — check the DURABLE idempotency ledger, not an in-memory Set
if (processedEventRepository.existsById(envelope.eventId())) {
    duplicatesSkipped.increment();
    return;   // safe no-op
}
```
An in-memory `Set<String>` would forget every processed id on the very
next application restart — exactly when a broker redelivery after a
rebalance is most likely to happen. `ProcessedEvent` is a real database
row, so idempotency survives a restart.

## Two Real Incidents (both genuinely production, both root-caused with evidence, not guessed)

1. **Missing autoconfiguration module (Spring Boot 4 split)** —
   `org.springframework.kafka:spring-kafka` is the Kafka *library*;
   Spring Boot 4 moved its autoconfiguration into a separate
   `spring-boot-starter-kafka` module. Without it, `@KafkaListener`
   methods are never registered as real listeners at all — the producer
   side worked fine (this app declares its own `KafkaTemplate` bean
   explicitly), which made the symptom look like "consumer logic is
   wrong" when the real cause was "the consumer was never wired up by
   Spring at all." The exact same defect class as an earlier Flyway
   incident in this same codebase (see docs/LESSONS.md) — Spring Boot 4
   splitting a library from its autoconfiguration glue is a recurring
   trap, not a one-off.
2. **Log-flooding production incident** — once Kafka support was added
   but no broker was actually provisioned, the consumer's background
   reconnect/rebootstrap loop fired roughly once per second, forever —
   severely enough that Railway itself began dropping log lines
   (`Messages dropped: 621`). Two plausible-looking property fixes
   (`reconnect.backoff.ms`, `admin.auto-create=false`) were tried and
   **independently re-verified against real logs**, and neither actually
   stopped the loop. The real fix: gate the entire Kafka subsystem behind
   `@ConditionalOnProperty(app.kafka.enabled)`, defaulting to `false` — a
   component that is never instantiated cannot leak a reconnect loop.
   **Lesson generalized:** an optional infrastructure dependency that
   isn't provisioned yet must be structurally absent (conditional
   bean/component), not merely configured to retry politely — polite
   retry still means *some* background activity forever, which is itself
   a production risk at scale.

## Failure Cases (real, tested)

- Broker unreachable when the poller runs → publish fails, row stays
  unpublished, retried on the next 2-second poll — no event lost, no
  crash.
- Duplicate delivery (hand-crafted in tests) → second delivery is a
  real, verified no-op (`duplicatesSkipped` counter increments).
- Malformed message → retried twice, then routed to the real dead-letter
  topic via `DeadLetterPublishingRecoverer` — never an infinite
  poison-message loop.
- Kafka not provisioned at all (`app.kafka.enabled=false`, real
  production's current state) → zero background connection attempts,
  zero log noise, outbox rows still accumulate correctly and would
  publish in order the first time the flag is ever turned on.

## Testing

`CustomerPreferenceEventFlowIntegrationTest` (3 tests, real Kafka via
Testcontainers `ConfluentKafkaContainer`, `disabledWithoutDocker=true` —
skips on this dev machine, runs for real on GitHub Actions): genuine
outbox-publish-consume end-to-end, a hand-crafted duplicate redelivery
proven to be a real no-op, and a poison message proven to actually land
on the real dead-letter topic. All green on GitHub Actions' real Docker
runner (confirmed via the public Checks API, not assumed).

## Design Trade-offs

- **Poll-based relay (chosen)** vs. Debezium/CDC-based outbox (reading
  the database's own write-ahead log): polling is simpler to operate and
  entirely adequate at this data volume; CDC removes polling latency and
  load but adds a real operational dependency (a CDC connector,
  Kafka Connect) not justified at this scale.
- **`@ConditionalOnProperty` full subsystem gating (chosen)** vs. a
  circuit-breaker/backoff around the existing always-on beans: gating
  is a stronger guarantee (zero activity, not just *reduced* activity)
  and was chosen specifically because the log-flood incident proved that
  "less frequent retry" still isn't "no activity."

## What Changes at 10x Scale

- `BATCH_SIZE = 20` and `fixedDelay = 2000ms` are tuned for today's low
  event volume; at real scale this becomes a genuine backlog/throughput
  concern — a CDC-based outbox reader removes the polling-interval
  latency floor entirely.
- A single consumer group / single partition key (`aggregateId`) is
  fine at current volume; partition count and consumer group scaling
  become real capacity-planning questions once event volume grows.

## Interview Questions This Answers

- "What's the dual-write problem, and how does the transactional outbox
  pattern solve it?"
- "Kafka gives you at-least-once delivery — where does exactly-once
  processing actually get implemented, and why there?"
- "Tell me about a real Spring Boot 4 migration surprise you hit."
- "Describe a real production incident you caused, found, and fixed —
  what was the actual fix, and why did two earlier attempted fixes not
  work?"
- "When would you choose Debezium/CDC over a polling-based outbox relay?"

## Live Demo / Evidence Links

- `app/src/main/java/com/example/customer/outbox/OutboxPublisher.java`, `ProcessedEvent*.java` (real source)
- `app/src/test/java/com/example/customer/messaging/CustomerPreferenceEventFlowIntegrationTest.java`
- `docs/PROJECT_STATE.json`'s `flagship_kafka_transactional_outbox` / `flagship_java21_and_kafka_log_flood_incident` verification_state entries (full incident evidence)
- Commits `8428568` (outbox implementation), `c2eac1b` (log-flood fix)
- Kafka is deliberately NOT provisioned in real production today (`app.kafka.enabled=false`) — an honest, current scope boundary, not a hidden gap.
