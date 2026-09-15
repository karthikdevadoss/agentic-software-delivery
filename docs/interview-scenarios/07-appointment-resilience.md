# Interview Scenario: Appointment Downstream Resilience — Retry, Circuit Breaker, Error Classification

Derived from the actual implementation: `app/src/main/java/com/example/customer/integration/appointment/*` and, for the deliberately-seeded training variant, `app/src/main/java/com/example/customer/triage/TriageScenarioBService.java` (Incident Triage Lab Scenario B, built 2026-09-15).

## Business Why

Checking technician appointment availability requires calling a real
downstream scheduling service over HTTP — a dependency this application
does not own or control. Downstream services are unreliable in the real
world: slow, briefly down, or returning malformed data. The client must
fail *predictably* (a clear, honest "unavailable" answer) rather than
hang the whole request or silently show wrong data, and it must not
retry a request class that retrying can never fix.

## Requirement

- A downstream timeout must trigger a real client-side timeout, then a
  bounded number of retries, then an honest `SERVICE_UNAVAILABLE` — never
  an unbounded hang.
- A downstream 5xx (server error) is retried, since it may be transient.
- A downstream 4xx (client error) is **never** retried — a malformed
  request will fail identically every time, so retrying only wastes
  calls and delays the answer.
- Sustained failure must open the circuit breaker so the client fails
  fast instead of continuing to hammer an already-down downstream.

## Architecture

```
GET /customers/{id}/appointment-availability?date=...
   |
   v
AppointmentAvailabilityService.checkAvailability
   |
   v
CircuitBreaker.decorateSupplier(breaker, Retry.decorateSupplier(retry, rawCall))
   -- composition order matters: the BREAKER wraps the RETRY, not the
      other way around, so an open circuit fails fast BEFORE any retry
      logic runs at all
   |
   v
AppointmentAvailabilityClient.checkAvailability
   -- real RestClient HTTP call (1000ms connect+read timeout)
   |
   v
DemoAppointmentProviderController (/internal/demo-appointment-provider)
   -- this app's own synthetic downstream, reached over a genuine HTTP
      loopback (never a direct method call) -- see "Synthetic Downstream" below
```

## Java/Spring Implementation

```java
// AppointmentAvailabilityConfig.java -- programmatic composition, CORE
// modules, not the resilience4j-spring-boot3/4 annotation starter (a
// real, documented Spring Boot 4 BOM compatibility gap as of this
// project's dependency versions)
@Bean
public Retry appointmentRetry(RetryRegistry retryRegistry) {
    RetryConfig config = RetryConfig.custom()
            .maxAttempts(3)
            .waitDuration(Duration.ofMillis(50))
            // Deliberately narrow: only retry on connectivity/timeout
            // failures. A 4xx client error is not a transient
            // condition -- retrying it would just waste calls.
            .retryOnException(ex -> ex instanceof ResourceAccessException
                    || ex instanceof HttpServerErrorException)
            .build();
    return retryRegistry.retry("appointmentService", config);
}
```

```java
// AppointmentAvailabilityService.java
Supplier<...> raw = () -> client.checkAvailability(date, scenario);
Supplier<...> decorated =
        CircuitBreaker.decorateSupplier(circuitBreaker, Retry.decorateSupplier(retry, raw));

try {
    var response = decorated.get();
    return response.available()
            ? new AppointmentAvailabilityResult(AVAILABLE, response.slotsOrEmpty())
            : AppointmentAvailabilityResult.withoutSlots(UNAVAILABLE);
} catch (CallNotPermittedException openCircuitException) {
    return AppointmentAvailabilityResult.withoutSlots(SERVICE_UNAVAILABLE);
} catch (Exception downstreamFailure) {
    // connection refused/timeout, 5xx after retries exhausted, 4xx
    // (never retried), or a malformed response body -- all mean "we
    // could not get a real answer," never silently treated as UNAVAILABLE
    log.warn("Appointment availability downstream call failed, reporting SERVICE_UNAVAILABLE: {}", downstreamFailure.toString());
    return AppointmentAvailabilityResult.withoutSlots(SERVICE_UNAVAILABLE);
}
```

`AVAILABLE`/`UNAVAILABLE` are genuine business answers from a real
successful call; `SERVICE_UNAVAILABLE` is the one honest answer for
every failure path — never fabricated as if it were a real "no slots"
result.

## The Synthetic Downstream: a Reusable Isolation Pattern

`DemoAppointmentProviderController` is this app's own internal,
synthetic downstream provider — explicitly not a real scheduling
backend. `AppointmentAvailabilityClient` reaches it over a genuine HTTP
loopback call (never a direct method call), so the entire real
client/timeout/retry/circuit-breaker mechanics are genuinely exercised —
only the data on the other side of the wire is synthetic. It supports
`?scenario=timeout` (a real 2500ms delay, longer than the real 1000ms
client read timeout, so it triggers a genuine timeout exception, not a
simulated one), `?scenario=error` (a real HTTP 500), and — added for
Triage Scenario B — `?scenario=client_error` (a real HTTP 400). This is
the exact template every Incident Triage Lab scenario's live re-demo
copies: a real HTTP round-trip to a synthetic internal endpoint, never a
hardcoded `if (demo) return error` inside real business logic.

## A Deliberately-Seeded Defect, Safely Isolated (Triage Scenario B)

Unlike the plan-enrollment and Postgres-search scenarios (real historical
incidents), this codepath has no known real production bug — it is
already correct and covered by 7 real WireMock tests. To still teach
this exact defect class live, Incident Triage Lab Scenario B seeds a
**deliberately wrong retry predicate** — but isolated so it can never
touch the real production path:

```java
// TriageScenarioBService.java -- private, UNREGISTERED Retry instance,
// never added to the shared RetryRegistry, structurally unreachable
// from AppointmentAvailabilityService
private final Retry buggyRetry = Retry.of("triageScenarioBBuggyRetry",
        RetryConfig.custom()
                .maxAttempts(3)
                .waitDuration(Duration.ofMillis(50))
                .retryOnException(ex -> true)   // BUG: retries everything, including 4xx
                .build());
```

`reproduce()` wraps a real call to `?scenario=client_error` in either
`buggyRetry` or the real production `appointmentRetry` bean (injected via
constructor, the SAME bean `AppointmentAvailabilityService` itself uses),
depending on whether the scenario has been "fixed" — live-verified: the
buggy path makes exactly 3 real HTTP attempts against a genuine 400; the
fixed path (delegating to the real bean, never a second copy of the fix)
makes exactly 1.

## Failure Cases (real, WireMock-tested)

- Success → `AVAILABLE` with real slots.
- 5xx → retried up to 3 attempts, verified via WireMock request count,
  then `SERVICE_UNAVAILABLE` if still failing.
- 4xx → exactly 1 call, never retried.
- Connect/read timeout → genuine timeout exception, not simulated.
- Malformed response body → deserialization failure, honestly reported
  as `SERVICE_UNAVAILABLE`, never crashed or misreported as `UNAVAILABLE`.
- Sustained failure → circuit breaker opens, subsequent calls fail fast
  (`CallNotPermittedException`) without even attempting the downstream.

## Testing

`AppointmentAvailabilityIntegrationTest` (7 real WireMock cases, no
mocked Resilience4j behavior — the real CircuitBreaker/Retry stack runs
against a real embedded HTTP server). `TriageScenarioBIntegrationTest` (4
tests, real Spring context, real HTTP loopback, not WireMock) proves the
isolated buggy/fixed predicate behavior end to end.

## Design Trade-offs

- **CORE Resilience4j modules, programmatic composition (chosen)** vs.
  the `resilience4j-spring-boot3/4` annotation starter: the annotation
  starter has a real, verified Spring Boot 4 BOM compatibility gap as of
  this project's dependency versions — programmatic composition produces
  identical runtime behavior with zero dependency risk, at the cost of a
  few more lines of explicit wiring.
- **Breaker wraps retry (chosen)**, not the reverse: an open circuit must
  fail fast before any retry attempt, not retry into an already-known-bad
  downstream.
- **`SERVICE_UNAVAILABLE` as a genuine third state**, not folded into
  `UNAVAILABLE`: conflating "the downstream said no slots" with "we
  couldn't reach the downstream" would be a real, misleading business
  answer.

## What Changes at 10x Scale

- Circuit breaker configuration (sliding window 10, 50% failure rate,
  10s open-state wait) is tuned for today's traffic; at much higher
  volume the sliding window and half-open probe count would need
  re-tuning against real observed failure patterns, not left at
  defaults.
- A real downstream replacing the synthetic one would need its own
  latency/error-rate SLOs feeding back into retry/breaker tuning — this
  design's isolation (client -> service -> config, one bean per concern)
  already supports that without a rewrite.

## Interview Questions This Answers

- "Design resilient handling for a flaky downstream dependency."
- "Why does retry predicate design matter — what happens if you retry a
  4xx?"
- "Explain circuit breaker vs retry, and why composition order matters."
- "How do you safely demonstrate a resilience bug without risking the
  real production path it resembles?"
- "What's the difference between 'the answer is no' and 'we don't know
  the answer' in a downstream-integration API design?"

## Live Demo / Evidence Links

- `app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityService.java` (real source)
- `app/src/main/java/com/example/customer/integration/appointment/AppointmentAvailabilityConfig.java` (real source)
- `app/src/main/java/com/example/customer/integration/appointment/demo/DemoAppointmentProviderController.java` (real source)
- `app/src/test/java/com/example/customer/integration/appointment/AppointmentAvailabilityIntegrationTest.java` (7 real tests)
- Live at `/triage/scenario-b` -- Incident Triage Lab Scenario B, the full reproduce→diagnose→AI-candidate-patch→verify→approve→resolved lifecycle
- `app/src/main/java/com/example/customer/triage/TriageScenarioBService.java` (real source, the isolated seeded defect)
