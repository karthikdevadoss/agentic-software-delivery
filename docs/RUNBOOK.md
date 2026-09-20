# Incident Runbook — Customer App

Two parts: a real on-call triage checklist for this app, and a real
blameless postmortem for the one genuine production incident this
project has actually had (the Kafka log-flooding incident,
2026-09-14). Written from real prod-support experience, not a
generic template filled with placeholders.

## Part 1 — On-call triage checklist

**1. Is the app actually down, or degraded?**
```
curl https://agentic-delivery-customer-app-production.up.railway.app/actuator/health
```
`{"status":"UP"}` with liveness/readiness both green means the JVM is
up and the DB is reachable. A 5xx or connection failure here is a real
outage — everything below is for the "up but something's wrong" case.

**2. Check the version footer first, always.**
Before debugging anything, confirm what's actually deployed —
`/actuator/info`'s `deploy.commit`/`deploy.time` fields (see the
footer on the live app itself). A "bug" that's already fixed in a
commit that hasn't been deployed yet is not a bug to chase further.

**3. Structured logs, not raw grep.**
Every log line is JSON (ECS format) with a real `traceId`/`spanId`
(Brave tracing, 100% sampled — see `docs/FLAGSHIP_MARKET_COVERAGE.md`'s
Observability row). Filter by `log.level` and correlate by `traceId`
across a single request's full path, not by eyeballing plain text.

**4. Real-time metrics before speculation.**
`/actuator/prometheus` (needs a valid JWT) has real counters for every
failure-prone boundary already instrumented: `security_rejections_total`
(auth problems), `cache_requests_total{result="redis-unavailable"}`
(cache layer degraded, not down), `resilience4j_circuitbreaker_state`
(the Appointment integration tripped), `outbox_events_total{result="publish-failed"}`
(Kafka relay stuck), `rate_limiter_requests_total{result="rejected"}`
(someone's hitting a real limit). Check these BEFORE guessing — they
turn "something feels slow" into "cache is at 40% redis-unavailable,
here's why."

**5. Optional dependencies degrade, they don't take the app down.**
Redis and Kafka are both currently `INFRA_NOT_PROVISIONED` in
production by deliberate scope decision (see `docs/FLAGSHIP_MARKET_COVERAGE.md`)
— every code path that touches either fails open/gracefully (see
`docs/DESIGN_PATTERNS.md`'s Cache-Aside, Distributed Lock, and Rate
Limiter entries). If `/actuator/health` is UP, Redis/Kafka being
unreachable is never the actual outage cause here, by design — don't
spend triage time there first.

**6. New engineer? Practice on the Incident Triage Lab first.**
`/internal/triage/scenario-{a,b,c,d}` are real, isolated replays of
four real historical defects this project actually shipped and fixed
(idempotency, retry/circuit-breaker, N+1-style query issue, Kafka
fan-out idempotency) — `reset` → `reproduce` → `approve` → `reproduce`
again on synthetic data only, never real customer rows. This is the
fastest way to build real intuition for this app's actual failure
modes before a real incident happens.

## Part 2 — Postmortem: Kafka log-flooding incident (2026-09-14)

**Status:** Resolved. **Severity:** Real production impact (log
delivery degraded platform-wide on the hosting provider), no customer
data loss, no downtime to the app's own actual business endpoints.

### Summary
Enabling the Kafka consumer for real (`CustomerPreferenceEventConsumer`,
part of the transactional-outbox rollout) against an environment with
no Kafka broker actually reachable caused the underlying Kafka client's
background reconnect/rebootstrap behavior to fire roughly once per
second, indefinitely. Railway's own log-ingestion pipeline began
dropping messages platform-wide ("rate limit reached for deployment")
once that volume was sustained.

### Impact
Real log messages — including from the app's OTHER, working
functionality — were silently dropped by the hosting platform for the
duration. No business endpoint returned an error because of this
directly, but observability into the app during that window was
degraded exactly when something else might have needed it.

### Timeline (as documented in `docs/FLAGSHIP_MARKET_COVERAGE.md`)
1. Kafka consumer/producer wiring completed and deployed with no real
   broker provisioned yet.
2. `@KafkaListener`'s consumer group join attempts and the AdminClient's
   topic-metadata refresh both retried against an unreachable broker at
   their (near-default) backoff interval.
3. Two targeted property fixes were tried:
   - Raising `spring.kafka.consumer.properties.reconnect.backoff.ms` —
     governs reconnecting to an *already-known* broker node, not
     bootstrap re-resolution when *no* node has ever been reachable.
     Didn't fix it.
   - Disabling `spring.kafka.admin.auto-create` — stopped the
     AdminClient's share of the noise, but not the `@KafkaListener`
     consumer's own independent reconnect loop. Partial fix only.
4. Real root cause confirmed via actual production log inspection: the
   reconnect/rebootstrap loop was firing roughly every second,
   indefinitely, regardless of either property change.

### Root cause
Neither property fix addressed the actual behavior — they governed
different phases of the client lifecycle than the one actually looping.
The real, architectural root cause: **nothing should attempt to connect
to Kafka at all until Kafka is actually provisioned.** A config-tuning
fix was the wrong class of solution for a "this shouldn't be running
yet" problem.

### Resolution
The entire Kafka subsystem (`KafkaMessagingConfig`,
`CustomerPreferenceEventConsumer`, `OutboxPublisher`, and every consumer
added since — see `docs/DESIGN_PATTERNS.md`'s Fan-out entry) is
`@ConditionalOnProperty(app.kafka.enabled)`, defaulting to `false`. None
of these beans are even instantiated, and no listener container starts,
until an operator explicitly provisions a real broker and sets
`KAFKA_ENABLED=true`. Re-deployed and independently re-verified:
production logs returned to a normal volume (50 lines for a full
startup vs. sustained per-second reconnect noise before), the app
remained fully functional throughout (health UP, JWT-protected APIs
working, outbox rows still written transactionally even with Kafka
disabled).

### Lessons learned
1. **Two symptom-level property fixes in a row that each fix "some of
   it" is itself a signal to stop and look for an architectural cause**
   — not keep tuning individual properties hoping the third one is
   the charm.
2. **"Retry connecting in the background" needs an explicit off switch
   for the case where there's deliberately nothing to connect to yet**
   — a library's sensible default resilience behavior (keep trying) is
   the wrong behavior when the *feature itself* isn't meant to be live.
3. This is now a standing pattern in this codebase, not a one-off fix:
   every optional infrastructure dependency added since (Redis caching,
   the enrollment lock, rate limiting) is gated the same way and fails
   open/gracefully rather than assuming its backing service is reachable
   — see `docs/DESIGN_PATTERNS.md`.

### Action items (all done, tracked for completeness)
- [x] Gate the whole Kafka subsystem behind `app.kafka.enabled` (done, this incident's actual fix)
- [x] Re-verify production logs and app functionality post-fix (done)
- [x] Carry the same "fails open, gated by an explicit flag" pattern into every future optional-infra feature (done — Redis cache, lock, rate limiter all follow it)
