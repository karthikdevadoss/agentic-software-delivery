# Interview Scenario: Observability & a Real Production Incident — Root-Causing From Evidence, Not Guesses

Derived from the actual implementation: `app/src/main/resources/application.properties` (Actuator/Micrometer/tracing config), `app/src/test/java/com/example/customer/ObservabilityIntegrationTest.java`, `app/src/main/java/com/example/customer/security/SecurityConfig.java` (the `security.rejections` counter), and a real production incident this project's own agentic delivery pipeline diagnosed and fixed.

## Business Why

A production incident is only debuggable if the system already emits
real, correlated evidence *before* the incident happens — logs that can
be searched, metrics that can be graphed, and a way to directly inspect
live system state (not just guess from symptoms). This project treats
observability as a prerequisite for incident response, not a nice-to-have
added after the fact — and had to prove it on a real incident, not a
staged one.

## What's Actually Wired

```
management.endpoints.web.exposure.include=health,info,metrics,prometheus
management.endpoint.health.probes.enabled=true
management.endpoint.health.show-details=when-authorized
management.tracing.sampling.probability=1.0
management.observations.key-values.application=customer-app
logging.structured.format.console=ecs
```

- **Actuator**: `/actuator/health` public (liveness/readiness probe
  Railway can poll), `/actuator/metrics` and `/actuator/prometheus`
  require a real authenticated token — raw metrics/env detail should not
  be fully anonymous even though it's not "business data."
- **Structured logging**: ECS-format JSON to console, so every log line
  is machine-parseable (field-searchable in a real log aggregator), not
  a free-text string requiring regex.
- **Distributed tracing**: Micrometer Tracing + Brave, 100% sampling —
  every request gets a real trace/span id for correlation across log
  lines and (if a downstream call happens) across service boundaries.
- **Custom business counters**: `security.rejections{reason=...}`
  (unauthenticated vs. insufficient-scope, see the Security anchor) and
  `cache.requests{result=...}` (hit/miss/redis-unavailable, see the
  Redis anchor) — metrics that answer a real operational question
  ("are we getting attacked, or is the cache actually helping"), not
  generic framework counters alone.
- **Resilience4j metrics bound into the same registry**:
  `resilience4j_circuitbreaker_state` / `resilience4j_retry_calls_total`
  appear in `/actuator/prometheus` because `CircuitBreakerConfig`'s
  registry is explicitly wired with `TaggedCircuitBreakerMetrics`/
  `TaggedRetryMetrics` at construction time — proven by a real test that
  generates real traffic first, then asserts the meter actually appears
  (`ObservabilityIntegrationTest::prometheusEndpoint_withValidToken_exposesRealMetersAfterRealTraffic`),
  not just that the bean exists.

## A Real Production Incident: Root-Caused From Evidence

Shortly after a routine deploy, `/api/dashboard` on this project's own
agentic-delivery backend hung indefinitely — and **every other route on
the same service became simultaneously unreachable**, despite clean
startup logs. This was diagnosed live, not guessed at:

1. **Symptom**: total service unresponsiveness, no obvious error in
   application logs.
2. **Evidence, not assumption**: a direct `pg_stat_activity` query against
   the real Postgres instance (not a log grep, not a restart-and-hope)
   found a connection left **idle-in-transaction for 963 seconds**,
   holding a lock that blocked `ensure_schema()`'s own DDL — and nearly
   every request-serving code path called `ensure_schema()` first.
3. **Root cause, fully explained**: the stuck connection alone would only
   have blocked callers waiting on that lock. The reason it froze *every*
   concurrent request was a second, compounding factor — 4 route handlers
   were running real synchronous database queries directly on the async
   event loop. One stuck call therefore froze the entire event loop, not
   just its own request.
4. **Fix**: `run_in_threadpool` for all 4 synchronous-DB-query handlers
   (so a slow/stuck call can never block the event loop again),
   `statement_timeout` (15s) and `idle_in_transaction_session_timeout`
   (30s) on every database connection — defense-in-depth this
   application's own code cannot provide by itself against an externally
   orphaned connection (e.g. a container killed mid-query during a
   deploy cutover).
5. **Verified, not assumed fixed**: re-tested with real concurrent
   requests confirming they no longer block each other, and
   `ensure_schema()`'s own duration measured back down from a 12-17s
   timeout to ~1.2s.

This incident also plausibly explained an earlier, never-conclusively-
root-caused transient 502 observed during independent QA — the same
mechanism, reasoned about honestly as "plausible, not proven for that
specific earlier date" rather than silently claimed as definitively
solved.

## Diagnostic Discipline This Incident Demonstrates

- Query the real system state (`pg_stat_activity`) before forming a
  hypothesis, not after.
- Distinguish the *triggering* condition (one stuck connection) from the
  *amplifying* condition (synchronous DB calls on the event loop) — a fix
  that only addressed one of the two would have left the system fragile
  to the next stuck connection.
- Re-verify the fix against real, measured behavior (concurrent request
  latency, `ensure_schema()` duration) rather than declaring victory
  because the error stopped appearing once.
- State uncertainty honestly where it exists (the earlier 502's root
  cause is "plausible," explicitly not claimed as proven) rather than
  retroactively over-claiming a clean explanation.

## Testing

`ObservabilityIntegrationTest` (4 real tests: health is public, Prometheus
requires auth, real meters appear after real traffic — HikariCP pool
metrics, Resilience4j state, HTTP server request metrics — and the
security-rejection counter increments on a real 401).

## Design Trade-offs

- **100% trace sampling (chosen)** at current traffic volume: full
  request correlation is worth the overhead at this scale; a real
  next-scale question is a sampling rate reduction once trace-storage
  cost becomes material.
- **`statement_timeout`/`idle_in_transaction_session_timeout` (chosen)**
  as connection-level defense-in-depth vs. relying solely on
  application-level connection-pool discipline: the incident above
  specifically involved an *externally* orphaned connection the
  application's own code could never have detected on its own — the
  database-level timeout is the only layer that can actually recover
  from that class of failure.

## Interview Questions This Answers

- "Tell me about a real production incident you root-caused, not one you
  guessed at."
- "How do you design observability so an incident is actually
  debuggable, before it happens?"
- "Explain the difference between a triggering cause and an amplifying
  cause in an incident — why does the distinction matter for the fix?"
- "Why bind Resilience4j/HikariCP metrics into the same registry as your
  own business counters?"
- "How do you communicate honest uncertainty about a root cause you
  can't fully prove?"

## Live Demo / Evidence Links

- `app/src/main/resources/application.properties` (real Actuator/tracing/logging config)
- `app/src/test/java/com/example/customer/ObservabilityIntegrationTest.java` (4 real tests)
- `app/src/main/java/com/example/customer/security/SecurityConfig.java` (the `security.rejections` counter)
- `docs/ACTION_QUEUE.json`'s `PRODUCTION-TRANSIENT-502-OBSERVATION` entry (the incident record, including the plausible-not-proven reasoning about the earlier 502)
