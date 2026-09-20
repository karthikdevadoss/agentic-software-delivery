# Real-Topology Multi-Instance Test Tier (BL-021)

A new, scripted, repeatable test tier that sits between "one service in
isolation" (unit / Testcontainers-backed single-service integration /
WireMock contract tests, all real and already working elsewhere in this
repo) and production. It does what a human had to do manually the night
this was built: start several real service instances together against a
real Eureka registry and prove a real cross-service call chain actually
works. See `docs/TESTING_ARCHITECTURE_V1.md`'s "REAL-TOPOLOGY" section and
`docs/AI_NATIVE_TESTING_RESEARCH.md` for why this tier exists — 4 of 7 real
defects found building `services/`'s microservices decomposition were
invisible to every other test tier and only manifested with multiple real
instances running together.

## What it does

`run_real_topology_test.py`:

1. Starts a real `eureka-server` (port 8761).
2. Starts 3 real, independent Spring Boot instances that depend on each
   other via real REST calls through real Eureka discovery:
   `customer-service` (8081), `billing-service` (8082), `api-gateway`
   (8080) — the minimum topology that exercises the actual bug classes
   found tonight (service-to-service discovery AND gateway load-balancing).
3. Polls each service's real `/actuator/health`, then polls Eureka's real
   `/eureka/apps` registry until all 3 report `UP`, then polls the
   api-gateway itself with a real harmless request until it actually
   routes successfully — never a fixed sleep at any step. (This 3-step
   readiness chain exists because the harness's own first real run
   caught a genuine race: the Eureka **server's** registry can report an
   instance UP before that instance's own **client-side** DiscoveryClient
   cache, e.g. the gateway's, has actually ingested it — each client
   fetches on its own periodic cycle, separate from server-side
   registration. See the docstring on `wait_for_gateway_routing_ready`
   in the script.)
4. Runs the exact real, already-proven request chain from this project's
   BL-007 smoke test, through the real gateway:
   `POST /auth/demo-token` -> `POST /customers` ->
   `POST /customers/{id}/plan` -> `GET /customers/{id}/plan`.
5. Asserts on real, specific response fields (status codes, `customerId`,
   `planName`, `ratePerKwh`), not just "no exception."
6. Always cleans up every process it started, in a `finally` block —
   success or failure. `taskkill /T /F` alone does not reliably cascade to
   the separate JVM Spring Boot's Maven plugin forks for the real running
   application in this dev environment (confirmed live during this
   harness's own development), so cleanup instead walks each started
   process's real descendant PID tree (via a PowerShell CIM query) and
   kills every verified descendant individually. It deliberately does
   **not** fall back to "kill whatever is listening on the port" — an
   earlier version did exactly that and, with multiple git worktrees of
   this repo running concurrently on the same machine, killed a
   *different* worktree's real, unrelated running services. That fallback
   was removed outright rather than hardened; a port still bound after
   real cleanup is now only ever reported, never touched.

## Usage

```
python services/real-topology-tests/run_real_topology_test.py
```

Optional: `--startup-timeout <seconds>` (default 90, per-service health
wait), `--registry-timeout <seconds>` (default 90 — Eureka's own
full-registry response cache refreshes on a real ~30s default cycle, so
this stays generous rather than tight), and `--port-offset <N>` (default
0) to shift every service onto alternate ports (e.g. `--port-offset
10000` runs eureka-server on 18761, customer-service on 18081,
billing-service on 18082, api-gateway on 18080) — every service already
reads its own port and Eureka URL from the environment, and inter-service
calls resolve purely through Eureka service ids, so this is a safe,
zero-code-change way to avoid colliding with another worktree/session
exercising these same services on their default ports on the same
machine (a real condition this harness hit during its own development).

Exit code `0` = PASS. Exit code `1` = FAIL, with the real failing step and
evidence printed (also see `logs/<service>.log`, gitignored, for the real
per-service Spring Boot log of a given run).

Requires nothing beyond what this repo's dev environment already has:
Java (per each service's own `mvnw`) and Python's `requests` (already an
`agent/requirements.txt` dependency). No Docker/Redis/Kafka required —
`billing-service`'s Redis lock and Kafka publishing are both real,
already-designed fail-open/disabled-by-default paths (see
`EnrollmentLockService`'s Javadoc and `app.kafka.enabled=false`), so this
tier runs on a plain dev machine with none of those running.

## What this deliberately does NOT do

- Does not touch `metering-service` or `notification-service` — not part
  of the real request chain being proven here (kept LARGE-but-bounded per
  this item's own sizing, not an oversight).
- Does not touch any service's business logic or `pom.xml` — every
  service is used strictly as a real black box.
- Does not deploy anywhere — entirely local processes on the dev machine.

## CI (BL-025, 2026-09-20)

Wired into `.github/workflows/ci.yml` as its own `real-topology` job,
run with `--port-offset 10000` (the same value proven locally above) —
but deliberately INFORMATIONAL ONLY (`continue-on-error: true`), not
gating, same convention this workflow already uses for the OWASP scan
and `verify_change.py`'s dry-run. Real reason, not a generic disclaimer:
a real local re-run done immediately before this CI wiring found this
harness no longer reaches PASS — see `docs/TESTING_ARCHITECTURE_V1.md`'s
§T section and `docs/ACTION_QUEUE.json`'s ACT-015 for the full real
finding (ACT-013's legacy-billing-system dependency, added after this
tier's own proof, is never started by this harness). Fix that first,
re-verify, then remove `continue-on-error` as its own deliberate step.
