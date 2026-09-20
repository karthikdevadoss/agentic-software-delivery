# Local Observability Stack

Real Prometheus + Grafana on real metrics the app already exposes at
`/actuator/prometheus` (see `docs/FLAGSHIP_MARKET_COVERAGE.md`'s
Observability row for what's instrumented and why). Not the real
production monitoring setup — Railway hosts this app today with no
Prometheus/Grafana provisioned there; this is a local, runnable
demonstration of the pattern, same honest scope boundary as every other
INFRA_NOT_PROVISIONED feature in this app (Redis, Kafka).

## Run it

```
cd app/observability
docker-compose up
```

- App: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (anonymous viewer access, admin/admin for the admin account)

The **Customer App Overview** dashboard loads automatically (Grafana
provisioning, no manual import) with 9 panels: HTTP request rate/p95
latency, cache hit/miss/redis-unavailable rate, rate-limiter
allowed/rejected, security rejections, circuit-breaker state, outbox
publish success/failure, fan-out consumer processed/compensated counts,
and HikariCP active connections.

## The one real design problem this stack had to solve

`/actuator/prometheus` requires a valid JWT (see `SecurityConfig`), and
this app's demo tokens are deliberately short-lived (900s — see
`DemoJwtIssuer`). A static bearer token pasted into `prometheus.yml`
would scrape successfully for 15 minutes and then silently start
failing every request after that. The `token-refresher` sidecar in
`docker-compose.yml` re-issues a fresh token every 10 minutes (inside
the TTL) and writes it to a shared volume; Prometheus's
`bearer_token_file` re-reads that file on every scrape — real,
documented Prometheus behavior, no restart needed on either side.

## Honest status

Written and reasoned through carefully, but **not locally run-verified**
— Docker isn't installed on this dev machine (see `docs/LESSONS.md`).
Every config file (`docker-compose.yml`, `prometheus.yml`, the Grafana
provisioning YAML, the dashboard JSON) has been syntax-validated
(`python -c "import yaml/json; ..."`), and every Prometheus metric name
each panel queries is a real name already emitted by this app's own
Micrometer counters (grep-confirmed against the source, not guessed) —
but the stack as a whole has not been proven to actually come up and
render live data. First thing to check once Docker is available:
`docker-compose up` and confirm all 9 panels populate.
