# Interview Scenario: Active-Plan Cache — Cache-Aside, Fail-Open Design

Derived from the actual implementation: `app/src/main/java/com/example/customer/cache/ContractPlanCacheService.java`, `app/src/main/java/com/example/customer/cache/RedisCacheConfig.java`, and `app/src/main/java/com/example/customer/controller/ContractPlanController.java`.

## Business Why

A customer's active plan is read on every account-overview page load —
far more often than it changes (only on `enroll()`). That read/write
skew is the actual, motivated reason to cache it, not a decorative
"let's add Redis" exercise. Equally important: this cache is optional
infrastructure — the real customer-facing feature (viewing your plan)
must keep working exactly as before if Redis is slow, down, or simply
not provisioned at all.

## Requirement

- `GET /customers/{id}/plan` should be served from cache when a fresh
  entry exists, and only fall through to Postgres on a miss.
- `POST /customers/{id}/plan` (enroll) must invalidate the cached entry
  so a stale plan is never served past the next real change.
- Any Redis failure — read, write, or eviction — must degrade to "as if
  there were no cache," never a 500, never a stale-forever entry beyond
  its own TTL.

## Architecture

```
GET /customers/{id}/plan
   |
   v
ContractPlanController.getActivePlan
   |-- workspaceAccessGuard.assertAccessible (JWT vs path id)
   v
ContractPlanCacheService.getActivePlan(customerId)
   |-- tryGet(key) --------------- Redis GET, wrapped
   |     hit  -> cache.requests{result=hit}++  -> return cached JSON, deserialized
   |     miss -> cache.requests{result=miss}++
   |     down -> cache.requests{result=redis-unavailable}++, log.warn, return null
   v
ContractPlanService.getActivePlan(customerId)   -- the real DB read, source of truth
   |
   v
tryPut(key, fresh)  -- Redis SETEX, wrapped, TTL=60s -- failure logged & swallowed
```

```
POST /customers/{id}/plan (enroll)
   |
   v
ContractPlanService.enroll(...)     -- the real write (see idempotency scenario)
   |
   v
ContractPlanCacheService.evict(customerId)   -- Redis DEL, wrapped, failure logged & swallowed
```

## Java/Spring Implementation

```java
public ContractPlanResponse getActivePlan(Long customerId) {
    String key = KEY_PREFIX + customerId;
    String cachedJson = tryGet(key);
    if (cachedJson != null) {
        hits.increment();
        return jsonMapper.readValue(cachedJson, ContractPlanResponse.class);
    }

    misses.increment();
    // Not wrapped in try/catch: a genuine 404 must propagate exactly as
    // it does for an uncached read -- caching must never change API
    // error behavior.
    ContractPlanResponse fresh = ContractPlanResponse.from(contractPlanService.getActivePlan(customerId));
    tryPut(key, fresh);
    return fresh;
}

private String tryGet(String key) {
    try {
        return redisTemplate.opsForValue().get(key);
    } catch (Exception redisDown) {
        redisUnavailable.increment();
        log.warn("Redis unavailable for active-plan cache read; falling back to the database directly", redisDown);
        return null;
    }
}
```

Every Redis-touching method (`tryGet`, `tryPut`, `evict`) is individually
wrapped — a design choice, not an oversight: a read failure returns
`null` (indistinguishable from a cache miss to the caller, which is
exactly the desired fallback behavior), a write/eviction failure is
logged and swallowed (the request that triggered it already succeeded
against the database, the real source of truth, so there is nothing left
to roll back).

## Why Programmatic, Not `@Cacheable`

Deliberately NOT annotation-driven. `@Cacheable`/`@CacheEvict` would
require a custom `CacheErrorHandler` to get this exact fail-open
behavior, hides the hit/miss/fallback logic behind annotation
processing, and makes each path (hit, miss, Redis-down) harder to unit
test in isolation. Explicit composition — the same preference already
used for Resilience4j (CORE modules, not the annotation starter, see the
Resilience anchor) — keeps every behavior a plain, directly testable
method.

## Serialization: A Real, Inspected Gap Avoided

`RedisCacheConfig` uses a plain `StringRedisSerializer` for both key and
value, with `ContractPlanCacheService` manually serializing to/from JSON
via this project's own real Jackson 3 `JsonMapper` bean — deliberately
NOT Spring Data Redis's `GenericJackson2JsonRedisSerializer`. That class
is built against classic Jackson 2 (`com.fasterxml.jackson.databind`);
this project's actual JSON provider is Jackson 3 (`tools.jackson`),
confirmed via `mvn dependency:tree` — classic Jackson 2 databind is
present only transitively through springdoc/swagger's own internal use,
never this app's real serialization path. Relying on that incidental
transitive dependency for cache serialization would be fragile — a
future springdoc version bump or removal could silently break
deserialization with no compile-time warning.

## Metrics: Proving the Fail-Open Path With Evidence, Not Assumption

Three Micrometer counters (`cache.requests{cache=active-plan,result=...}`)
tagged `hit`/`miss`/`redis-unavailable` are incremented on every real
call — not because the design *should* fail open, but so that behavior
can be verified from real production evidence. As of this writing, real
production shows `hit=0, miss=1, redis-unavailable=1` on every request:
an honest reflection that Redis is genuinely not provisioned there yet
(a deliberate scope decision, not a bug), and every real customer read
is quietly taking the fallback path already, proven by the metric, not
assumed from the code.

## Testing

`ContractPlanCacheIntegrationTest` (4 tests, real Redis via
Testcontainers) covers: a cache hit returning the cached value without
touching the database a second time, a cache miss populating the cache
from a real database read, and — the two tests that actually matter for
this design — a Redis-unavailable read falling through to the database
correctly, and a Redis-unavailable write/eviction not breaking the
triggering request.

## Design Trade-offs

- **Cache-aside (chosen)** vs. **write-through**: write-through would
  keep the cache always warm, but adds Redis to the write path's own
  latency/failure surface for a value that's read far more than
  written — cache-aside keeps the write path's correctness fully
  independent of cache health.
- **60-second TTL**: short enough that a Redis-unavailable eviction (the
  one genuine staleness risk this design accepts) self-heals quickly,
  long enough to meaningfully reduce database load for a page that's
  reloaded often within a session.
- **Programmatic over `@Cacheable` (chosen)**: more code, but every
  failure mode is an explicit, separately testable branch instead of
  annotation-processing behavior a reader has to already know by heart.

## What Changes at 10x Scale

- A single logical key per customer (`contract-plan:active:{id}`) is
  fine at today's scale; at very high cardinality, a shared Redis
  instance would need real capacity planning (eviction policy, memory
  budget) rather than assuming TTL alone bounds memory use.
  `redis-unavailable` climbing under real load would be the first real
  signal to actually provision and monitor Redis, rather than guessing
  it's needed.
- The current fail-open design already scales to "Redis is down" without
  a code change — the interesting next question is cache *stampede*
  protection (many simultaneous misses for the same hot key racing to
  repopulate it), not yet needed at current traffic.

## Interview Questions This Answers

- "Design a cache for a read-heavy, write-light resource — what pattern
  and why?"
- "How do you make sure a cache being down never becomes a customer-facing
  outage?"
- "Why would you choose programmatic cache logic over `@Cacheable`?"
- "How do you *prove* a fallback path actually works in production,
  rather than just trusting the code?"
- "What's a real serialization compatibility trap you've hit or avoided
  (Jackson 2 vs 3, here)?"

## Live Demo / Evidence Links

- `app/src/main/java/com/example/customer/cache/ContractPlanCacheService.java` (real source)
- `app/src/main/java/com/example/customer/cache/RedisCacheConfig.java` (real source)
- `app/src/test/java/com/example/customer/cache/ContractPlanCacheIntegrationTest.java` (4 real Testcontainers-backed tests)
- `docs/interview/SOURCE_CODE_CONCEPT_MAP.yaml`'s "Cache-aside with fail-open fallback" entry
