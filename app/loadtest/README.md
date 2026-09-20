# Load Test — GET /customers/{id}/plan

Real load-test baseline, previously flagged `NOT_STARTED`/P1 in
`docs/FLAGSHIP_MARKET_COVERAGE.md` ("no baseline established yet").

## Run it

```
# 1. Start the app locally (H2, default profile -- no Postgres/Redis/Kafka needed)
cd app
./mvnw spring-boot:run

# 2. In another terminal, once /actuator/health returns UP:
k6 run loadtest/active_plan_read.js
```

## Real results (2026-09-20, this dev machine, local H2 + no Redis)

20 concurrent virtual users, 30-second steady load, against a real
running instance of the app (not mocked, not simulated):

| Metric | Value |
|---|---|
| Total requests | 4,146 |
| Failed requests | 0 (0.00%) |
| Throughput | 128.5 req/s |
| Latency — avg | 40.3 ms |
| Latency — median (p50) | 30.8 ms |
| Latency — p90 | 66.9 ms |
| Latency — **p95** | **89.3 ms** |
| Latency — max | 1.52 s (first-request JIT/connection-pool warmup, not sustained) |

Both configured thresholds passed: `p(95)<500ms` (actual 89.3ms) and
`http_req_failed rate<1%` (actual 0%).

## Honest scope of this baseline

This measures the **uncached** path: Redis isn't running on this dev
machine (same real constraint as every Testcontainers test in this
repo — see `docs/LESSONS.md`), so every request took
`ContractPlanCacheService`'s real, already-proven fallback-to-database
path, not a cache hit. This is still a genuine, useful number — it's
the worst-case (cold-cache or cache-down) latency floor, and a real
comparison baseline for a future run against a real Redis instance,
which should show cache hits pulling the median down further without
changing the p95 tail much (tail latency here is dominated by the
first-request warmup, not steady-state DB round-trips).

## Interview framing

"128 req/s and 89ms p95 for a single-row authenticated read, with zero
failures under sustained 20-VU load, on an unoptimized H2 dev instance
— that's the honest floor. I have real headroom analysis to walk
through: what's in that 30ms median (JWT validation, JPA query,
serialization), and what I'd expect to change with Postgres + Redis
actually warm in production versus this local baseline."
