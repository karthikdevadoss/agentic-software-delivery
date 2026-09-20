# Testing & Verification Architecture V1

Built 2026-09-14 (RESUME-AFTER-QUOTA session), after finishing the
interrupted Preferences/Appointment work (see `docs/PROJECT_STATE.json`'s
`preferences_visible_feedback_and_appointment_demo_path`). Governing
principle: **AI can implement. AI does not get to declare its own work
correct. Deterministic evidence is the authority.**

This document is deliberately honest about what is real/implemented today
vs. designed-but-not-yet-automated. Marking something "designed only" is
not a failure to hide — building every section below in one sitting would
itself violate this project's own anti-overengineering rule
(`docs/CONSTITUTION.md` §6/§7) and its explicit usage-efficiency
instruction for this exact task.

## Core lifecycle

```
REQUIREMENT
  -> VERIFICATION CONTRACT
  -> RISK / BLAST-RADIUS CLASSIFICATION
  -> IMPLEMENTATION
  -> CHANGE IMPACT ANALYSIS
  -> SELECTIVE TEST PLAN
  -> DETERMINISTIC TESTS
  -> INDEPENDENT EVALUATION
  -> DEPLOYMENT IDENTITY
  -> PRODUCTION ACCEPTANCE
  -> VERIFIED
```

Deterministic software testing stays a separate concern from
probabilistic AI evals (§O) — this was already true before this task
(`.claude/skills/ai-feature-evaluation/SKILL.md`, `agent/eval_runner.py`)
and is preserved, not rebuilt.

## §A. Verification Contract — IMPLEMENTED (extended, not duplicated)

`agent/acceptance_contract.py`'s `AcceptanceContract` (Architecture V2,
already existed) is extended with the categorized fields this task asked
for, rather than creating a second, parallel schema:

- `verification_categories`: subset of `FUNCTIONAL, SECURITY, DATABASE,
  UI, INTEGRATION, OBSERVABILITY, PRODUCTION`
- `acceptance_criteria`, `negative_cases` (plain-language lists)
- `security_expectations`, `persistence_expectations`, `ui_expectations`,
  `integration_expectations`, `nfrs` (free text, `None` when not
  relevant — never a fabricated NFR number)
- `blast_radius` (mirrors `agent/change_risk.py`'s output once real files
  exist)
- `required_test_categories` (subset of §G's levels below)

`validate()` enforces internal consistency (e.g. `SECURITY` in
`verification_categories` requires `security_expectations` to be
non-empty) without forcing every category to be filled in for every
requirement — most small changes only touch 1-2. 15 tests
(`agent/test_acceptance_contract.py`), all passing.

## §B. Change Risk Classification — IMPLEMENTED

`agent/change_risk.py`. Deterministic, path-pattern based (no ML). Risk:
`LOW < MEDIUM < HIGH < CRITICAL`. Blast radius: `LOCAL < MODULE <
CROSS_MODULE < SYSTEM`. An unrecognized path is `UNKNOWN`/`UNKNOWN`, never
silently `LOW` — and one unrecognized file in a batch forces the whole
batch's overall verdict to `UNKNOWN` (known-safe files must never dilute
an unbounded one). 15 tests (`agent/test_change_risk.py`), including a
literal dogfooding test against this exact session's own real diff
(commit `b908f62`).

Representative real rules (see the module for the full table):

| Path pattern | Risk | Blast radius |
|---|---|---|
| `agent/risk_policy.py` | CRITICAL | SYSTEM |
| `.../security/**` | HIGH | CROSS_MODULE |
| `db/migration/**`, `pom.xml`, `.github/workflows/**`, `Dockerfile` | HIGH | SYSTEM |
| `application*.properties` | HIGH | CROSS_MODULE |
| `.../exception/**` (shared error handling) | MEDIUM | CROSS_MODULE |
| `.../{controller,service,repository,model,dto,integration}/**` | MEDIUM | MODULE |
| `.../messaging/**`, `.../outbox/**` (Kafka) | MEDIUM | MODULE |
| `.../cache/**` (Redis) | MEDIUM | MODULE |
| static frontend, docs, tests, `.gitignore` | LOW | LOCAL |

## §C/§D. Test Impact Analysis + Selective Regression Engine — IMPLEMENTED

`agent/test_impact_analysis.py` (the analysis) + `agent/verify_change.py`
(the CLI, also reachable as `python agent/dev_check.py verify-change`).

Input: real changed file paths (`git diff --name-only`, working-tree by
default or `--base <ref>` for a CI/PR-style merge-base diff). Output,
printed **before** anything runs:

1. the real changed files
2. per-file + overall risk/blast-radius classification
3. the selected Java test classes (or "ALL Java tests" when blast radius
   escalates to `CROSS_MODULE`/`SYSTEM`) and exactly why, file by file
4. large unrelated suites explicitly named as skipped, with a reason
   (Kafka/Redis/Postgres suites when nothing touched those packages)
5. `FAIL CLOSED` with a reason when impact cannot be confidently bounded

Explicit file -> Java test class mapping (`JAVA_FILE_TO_TESTS`) is a
literal dict checked against the real files in this repository, not a
guessed naming convention — a guessed name that doesn't exist would
silently select nothing. Cross-cutting `MANDATORY_TRIGGERS` (§F) fire on
a path pattern regardless of blast radius: a security file always pulls
in `SecurityIntegrationTest`; a migration file always pulls in
`PostgresFlywayIntegrationTest`; Kafka/outbox changes pull in
`CustomerPreferenceEventFlowIntegrationTest`; Redis changes pull in
`ContractPlanCacheIntegrationTest`.

**Fails closed** (selects the full regression across Java + Python +
Node, not a partial set) when: a path matches `pom.xml`,
`.github/workflows/**`, `agent/risk_policy.py`, or a `Dockerfile`; or any
path is genuinely unrecognized by `change_risk.py`.

Real, dogfooded proof (not simulated): run against `git diff --base
1e2e8ef` (this session's own real Preferences/Appointment commit) — it
correctly classified overall `HIGH/CROSS_MODULE` (SecurityConfig +
application.properties present), correctly escalated to "ALL Java tests,"
ran the always-on smoke class then the full `mvnw test`, both real
invocations succeeding (exit 0), and wrote a machine-readable evidence
JSON to `agent/.verify_change_evidence/` (gitignored, per-run).

18 tests (`agent/test_test_impact_analysis.py`), all passing.

**Honest limitation, not hidden:** this V1 pass implements Java TIA only.
A Python `agent/*.py` change is currently just flagged in `skipped`
("run `python agent/dev_check.py python-regression` explicitly") rather
than auto-selecting specific Python test modules — see `open items`
below.

## §E. Safety floor — always-on smoke — IMPLEMENTED (minimal)

Any `app/**` change (main or test) always runs `CustomerApplicationTests`
(context load) before the selected suite runs, regardless of what else
was selected — genuinely small and fast, per this task's own instruction
not to over-scope the smoke tier.

## §F. Change-aware mandatory rules — IMPLEMENTED for Java; partial elsewhere

Implemented (see §C/D): security -> `SecurityIntegrationTest`; Flyway ->
`PostgresFlywayIntegrationTest`; Kafka/outbox ->
`CustomerPreferenceEventFlowIntegrationTest`; Redis ->
`ContractPlanCacheIntegrationTest`; frontend -> mapped Playwright specs
where one exists (`agent/web/**` -> the matching `e2e/*.spec.js`).

**Partially closed 2026-09-20 (BL-012, following BL-013's real Update Email
work the same day):** the Customer App's own frontend
(`app/src/main/resources/static/index.html`) used to have **no dedicated
Playwright spec at all** — `verify_change.py` used to surface this as a
skip reason every time that file changed. `e2e/customer-app-update-email.spec.js`
(login -> edit email -> save -> reload, added as a real side effect of
proving BL-013's Update Email uniqueness fix works in a real browser) is
now mapped in `agent/test_impact_analysis.py`'s `FRONTEND_PATH_TO_SPECS`,
so the acute "zero coverage, silently unselected" gap is closed. **Still
honestly open:** this one spec covers only the login/edit-email flow, not
every control on the page (customer creation, preferences, admin views) —
broader golden-path coverage for this page remains real, separate future
work, not claimed as done here.

RAG/MCP/prompt changes already route to `agent/eval_runner.py`'s evals
(pre-existing, unchanged by this task) — not yet cross-wired into
`verify_change.py`'s selection logic.

## §G. Test levels — DESIGNED (already substantially real, now named)

| Level | Real example in this repo |
|---|---|
| STATIC | none formalized yet (no linter/type-checker gate) |
| UNIT | `*ServiceTest.java` (Mockito), `agent/test_*.py` |
| SPRING SLICE / COMPONENT | `CustomerApplicationTests` |
| REAL-INFRA INTEGRATION | `PostgresFlywayIntegrationTest`, `ContractPlanCacheIntegrationTest`, `CustomerPreferenceEventFlowIntegrationTest` (all real Testcontainers) |
| CONTRACT | `agent/test_backend_catalogue.py`, `agent/test_demo_catalogue.py` |
| SECURITY | `SecurityIntegrationTest` |
| BROWSER E2E | `e2e/*.spec.js` (Playwright, agentic-platform-backend pages only — see §F gap) |
| PRODUCTION ACCEPTANCE | `agent/dev_check.py production-verify`, `agent/demo_execution.py`'s real acceptance runs, this session's own live curl verification |
| PROPERTY / MUTATION / FUZZ / PERFORMANCE / CHAOS | not implemented; deliberately deep/risk-selected per this task's own instruction, not mandatory for every change |

## §H. Test execution tiers — DESIGNED, partially wired

- **FAST CHANGE GATE** (local dev loop): `python agent/verify_change.py`
  — compile + impacted unit/component + mandatory smoke. Real today.
- **INTEGRATION GATE**: `python agent/dev_check.py customer-app-tests`
  (full `mvnw test`, includes all Testcontainers suites when Docker is
  available — real today, e.g. in CI).
- **RELEASE GATE**: golden journeys (§I) + `production-verify`. Golden
  journeys are only partially built (see §I) — this tier is not yet a
  single command.
- **DEEP/NIGHTLY**: full regression + evals + (future) mutation/property/
  fuzz/performance. Not scheduled anywhere yet — no cron/nightly job
  exists in this repo for it.

## §I. Golden journeys — PARTIAL

Real today, via Playwright (`e2e/*.spec.js`): Learn, Usage, Profile-gone
(privacy), Workbench catalogue (non-mutating) + one real mutating
Workbench acceptance run (`workbench-real-acceptance.spec.js`, gated
behind `RUN_REAL_ACCEPTANCE=1`).

**Not yet built:** a Customer App "recruiter golden journey" (open ->
demo auth -> update email -> visible success -> refresh -> persisted ->
preferences -> visible success -> appointment happy path) as an actual
Playwright spec — this session verified the exact same steps live via
`curl` + a real demo JWT (see `verification_state.
preferences_visible_feedback_and_appointment_demo_path`), proving the
steps themselves work, but that is not the same durable artifact as a
committed browser spec. Recorded as the top follow-up in
`docs/ACTION_QUEUE.json`.

ADMIN journey: correctly out of scope — no ADMIN functionality exists in
this project yet.

## §J. Independent evaluator — ALREADY EXISTS, unchanged by this task

`.claude/agents/qa-evaluator.md` (Architecture V2) already implements
this separation and has real trial evidence
(`verification_state.architecture_v2_shadow_trial_1/2` in
`docs/PROJECT_STATE.json`, including one trial that proved EVALUATOR
USEFULNESS: HIGH by seeding a real defect). Nothing new needed this task
— builder (this session) + at most one independent evaluator when
warranted, never a swarm, per this task's own instruction.

## §K. Test quality — DESIGNED, not newly instrumented

Requirement/boundary/failure-mode/security-role/golden-journey coverage
are tracked narratively today (this document + `docs/
FLAGSHIP_MARKET_COVERAGE.md`'s coverage matrix), not as a single number.
Mutation testing (PIT) is not integrated — no PIT dependency exists in
`app/pom.xml`. Recorded as a deliberately-deferred, not-mandatory-for-
every-change capability per this task's own instruction ("do not run
full mutation testing on every change").

## §L. Test isolation / flakiness — IMPLEMENTED as generalized rules

Directly generalizes the two real bugs this session just fixed getting
the Appointment demo path working (see `docs/LESSONS.md`):

1. **Shared singleton state must be reset per test, not per process.**
   `AppointmentAvailabilityIntegrationTest`'s shared `CircuitBreaker` bean
   leaked `OPEN` state across test methods (same cached Spring context) —
   fixed via `@BeforeEach appointmentCircuitBreaker.reset()`. Rule: any
   `@SpringBootTest`-scoped stateful bean (circuit breakers, in-memory
   caches, counters) must be reset in `@BeforeEach`/`@AfterEach`, not
   assumed fresh.
2. **A test double's own port/URL resolution must account for
   `RANDOM_PORT`.** `${server.port}` resolves to the literal configured
   value (`0` under `RANDOM_PORT`), not the bound port — real client
   configuration pointing at "this same app" must use
   `${local.server.port:${server.port}}` plus `@Lazy` on both the bean
   and its injection point.

Existing, unchanged isolation practices this task did not need to touch:
real Testcontainers (parallel-safe, ephemeral), a durable
`processed_event` idempotency ledger for Kafka consumer tests, and the
event ledger's own idempotent `ON CONFLICT DO NOTHING` inserts.

**Not yet built:** systematic flake/retry-history tracking (a test that
fails once and passes on retry is not currently distinguished from a
clean pass anywhere in this repo).

## §M. Deployment identity — ALREADY EXISTS for Workbench; real new gap found for Customer App direct deploys

The Workbench pipeline already has real deployment-identity proof
(timestamp-filtered `wait_for_new_deployment`, `docs/LESSONS.md`'s
deployment-identity fix). This session found a **new, different**
deployment-identity failure mode doing a *direct* `railway up` (not
through the Workbench pipeline): running it from the wrong working
directory silently built the wrong service's Dockerfile — a real
CRASHED deployment (`ANTHROPIC_API_KEY is not set`), caught only by
checking `railway deployment list --json`'s real status, not the CLI's
upload-time output. Recorded as a new durable lesson in
`docs/LESSONS.md`. **Not yet built:** a `verify_change.py`-adjacent CLI
guard that refuses/warns before a manual `railway up` from a directory
that doesn't match the target service's real build context.

## §N. Production acceptance — ALREADY EXISTS, reused this task

`agent/dev_check.py production-verify` (HTTP-status only) and the
existing `demo_catalogue`/`backend_catalogue` pattern (exact requested
effect, not HTTP 200 alone) both predate this task. This session's own
Priority-1 verification followed the same discipline manually (real demo
JWT -> real weekday/weekend/past-date/timeout appointment checks -> real
email update + re-GET -> real preferences save + re-GET) rather than
trusting deploy success alone.

## §O. Software tests vs. AI evals — unchanged, already correctly separated

`.claude/skills/ai-feature-evaluation/SKILL.md` + `agent/eval_runner.py`
already keep these separate (recall/routing/groundedness/unsafe-rejection
vs. JUnit/Testcontainers/Playwright/etc.). Nothing to add this task.

## §P. AI-harness behavior evals — DESIGNED, not automated

The specific checks this task named (did a UI change get a browser test;
did a schema change get a real Postgres migration test; did a security
change get an auth matrix; did a bug get a regression) are answered
**narratively, per-task, in this document and in commit messages** today
— there is no automated harness that inspects a diff and asserts "the
agent that made this diff also ran the required gate." Building that
would itself require `verify_change.py`'s output to become a hard gate
in the workflow that produces commits, which is exactly the kind of
"changes how the AI development process is gated" decision this
project's own CLAUDE.md reserves for explicit approval rather than
auto-executing.

## §Q. Quality economics — DESIGNED, evidence model started

`verify_change.py`'s evidence JSON (`agent/.verify_change_evidence/*.json`)
is the first real, honestly-measured record of: which suites were
selected vs. skipped and why, classification risk/blast-radius, real
command exit codes, and real wall-clock duration per command — the
concrete building blocks for `FIRST-PASS YIELD`/`VERIFICATION TIME`/
`REWORK` metrics named in this task. **Not yet built:** aggregation
across runs, escaped-defect tracking, or AI-token/rework-cost capture
tied to a specific verify-change run. No historical values are fabricated
— this starts recording only what happens from here forward.

## §R. CI integration — NOT changed this task (deliberately)

`.github/workflows/ci.yml` remains the authoritative gate for every
commit/PR/release today (full `mvnw test`, a scoped Python suite, Node
harnesses) — unchanged. This task deliberately did **not** wire
`verify_change.py` into CI as a gate: doing so would change what gates a
real release, which is exactly the class of decision this project's own
proactive-action policy reserves for explicit approval, not
auto-execution within an already-approved task. `python agent/
verify_change.py`/`python agent/dev_check.py verify-change` is real,
usable, and dogfooded **today** as a fast local dev-loop tool; CI
remains the authoritative full-regression gate until an explicit future
task decides to add it there (as an additive annotation step first, per
this task's own "prefer change-aware execution where technically safe...
ensure there is still a deliberate path for full regression" guidance —
not a replacement).

## §S. Outbound-request-assertion convention (added 2026-09-20, BL-019)

Real defect class this closes (docs/AI_NATIVE_TESTING_RESEARCH.md finding
3b): a mocked/WireMock-based integration test that only asserts on the
*response* (e.g. "did the call return 200/FOUND") structurally cannot
catch a header/credential-propagation bug — a mocked downstream returns
the stubbed response regardless of whether the real caller's
Authorization header, correlation id, or any other required header was
actually forwarded. This is exactly the class of bug BL-007's own real
end-to-end smoke test found (a missing JWT-propagation gap between
billing-service and customer-service) that no WireMock-based test at the
time would have caught.

**Convention, mandatory for every new outbound service-to-service call:**
1. Assert on the *outbound request itself* (`wireMock.verify(n,
   getRequestedFor(...).withHeader("Authorization", equalTo(...)))`),
   never only on the response.
2. Use a distinct, per-call value in the assertion (not a fixed/shared
   constant across tests) to prove the *actual per-call value* is
   propagated, not a hardcoded/stale one.

**Real example**: `services/billing-service/src/test/java/com/example/billingservice/client/BillingCustomerClientIntegrationTest.java`'s
`customerExists_forwardsTheRealCallerBearerToken_onTheOutboundRequest`
and `customerExists_forwardsTheActualPerCallToken_notAHardcodedOne` —
both real, run, passing tests (8/8 in that class as of this commit).

## §T. REAL-TOPOLOGY multi-instance tier — IMPLEMENTED (BL-021, 2026-09-20)

Closes a real, previously-empty gap this document did not have a section
for at all: nothing existed between "one service in isolation" (§G's
UNIT/SPRING SLICE/REAL-INFRA INTEGRATION/CONTRACT levels, all real for
`app/` and now for the `services/` microservices decomposition too) and
production. That gap was not theoretical — a real bug audit the same
night this decomposition was built found that 4 of 7 real defects
(`docs/MICROSERVICES_ARCHITECTURE.md`'s own "Real end-to-end smoke test"
section; full context in `docs/AI_NATIVE_TESTING_RESEARCH.md`) ONLY
manifested with multiple REAL service instances running together against
a REAL Eureka registry — invisible to every unit test, WireMock contract
test, and single-service Testcontainers test, and only caught because a
human manually started all 6 services and poked at them by hand.

`services/real-topology-tests/run_real_topology_test.py` makes that a
real, scripted, repeatable tier instead: starts a real `eureka-server` +
3 real dependent instances (`customer-service`, `billing-service`,
`api-gateway` — the minimum topology that exercises both the
service-discovery bug class and the gateway load-balancing bug class from
the original audit), polls real readiness at three separate real layers
(each service's own health, Eureka's server-side registry, and the
gateway's actual routing capability — see below for why all three are
needed), then runs BL-007's own already-proven real authenticated request
chain (`POST /auth/demo-token` -> `POST /customers` ->
`POST /customers/{id}/plan` -> `GET /customers/{id}/plan`) through the
real gateway, asserting on real, specific response fields, not just
absence of an exception. Full design rationale, usage, and the "what this
deliberately does NOT do" scope boundary: `services/real-topology-tests/
README.md`.

**Real findings from this tier's own first real runs (2026-09-20), not
simulated:**

1. **Server-side Eureka registry convergence does not imply
   client-side readiness.** The Eureka SERVER's `/eureka/apps` registry
   can report an instance UP before that instance's own CLIENT-side
   `DiscoveryClient` (e.g. the gateway's) has actually fetched it into its
   local cache — each client refreshes on its own periodic cycle,
   separate from server-side registration. The harness's own first real
   run caught this live: a real 503 "Unable to find instance for
   customer-service" surfaced as a bare 500 on the very first routed
   call, seconds after the server registry had already shown that
   instance UP. Fixed by adding a real gateway-routing-readiness poll
   (a harmless, side-effect-free real request, retried until it actually
   succeeds) as a distinct third readiness layer, never a fixed sleep.
2. **This same client-side-cache-warm-up race exists independently PER
   downstream service id, at multiple points in the real call graph** —
   proving the gateway could route to `customer-service` did not prove it
   could yet route to `billing-service`, and separately did not prove
   billing-service's OWN internal `BillingCustomerClient` (billing-service
   -> customer-service) was warm either. Each of the 3 real client-side
   LoadBalancer caches involved in the real request chain warmed up
   independently on its own first real use. Fixed with a bounded,
   backed-off retry at the HTTP-call layer, scoped ONLY to the exact
   status codes this race manifests as (500, and the deliberately
   distinct 503 `CustomerLookupOutcome.SERVICE_UNAVAILABLE` "please retry"
   response) — a genuine 4xx auth/validation/not-found failure is never
   retried, so a real bug still fails fast.
3. **A real, serious safety bug in this harness's own first cleanup
   design**, found and fixed during the same session: an early version
   force-killed whatever process was LISTENING on a target port as a
   cleanup fallback. On a machine running multiple git worktrees of this
   same repository concurrently (a real, current condition, not a
   hypothetical — confirmed via `git worktree list`), that fallback
   killed a *different* worktree's real, unrelated, actively-running
   service processes purely because they happened to occupy the same
   fixed default port at that moment. Fixed by walking each started
   process's REAL descendant PID tree (a PowerShell CIM query) and
   killing only verified descendants of PIDs this run itself started —
   the port-based fallback was removed outright, not hardened; a port
   still bound after real cleanup is now only ever reported, never
   touched.
4. **Real port contention with a concurrently active sibling worktree**,
   found and fixed the same session: this tier's first working version
   used each service's fixed default local port
   (8080/8081/8082/8761, matching `services/README.md`'s existing
   convention), and a real run was interrupted mid-flow by a *different*
   git worktree (confirmed via `git worktree list` + live process
   inspection, not assumed) concurrently exercising these same services
   on those same default ports. Fixed with a `--port-offset` CLI option:
   every service already reads its own port and its Eureka URL from the
   environment (`server.port=${PORT:...}`,
   `eureka.client.service-url.defaultZone=${EUREKA_URL:...}`), and every
   inter-service call resolves purely through Eureka service ids, never a
   hardcoded port — so shifting the whole topology onto alternate ports
   (e.g. `--port-offset 10000`) is a safe, zero-code-change way to avoid
   the collision entirely. Verified live: 3 consecutive full real runs at
   `--port-offset 10000`, all PASS, ~103-124s wall-clock each, while the
   sibling worktree remained active on the default ports the whole time.

Runs entirely local, touches no other service's business logic or
`pom.xml` (every service used strictly as a black box, per this item's
own hard constraint), and is not wired into `.github/workflows/ci.yml` —
a separate, deliberate decision for later, same reasoning as §R.

## Open items (tracked in docs/ACTION_QUEUE.json's TESTING-ARCH-V1-GAPS)

1. No dedicated Playwright spec for the Customer App's own frontend — the
   single most valuable next addition (§F/§I). **Partially closed
   2026-09-20** — see docs/BACKLOG.json's BL-012 (BL-013 added the first
   spec, e2e/customer-app-update-email.spec.js, scoped to the Update Email
   flow only). **CLOSED 2026-09-20** — BL-027 added
   e2e/customer-app-frontend.spec.js: 8 real tests covering the login gate
   (anonymous vs. USER vs. ADMIN view), the real USER cards (Overview,
   Account/Profile, Plan, Preferences, Appointments, Activity) actually
   rendering real data, a real Preferences write/read-after-reload flow,
   and real ADMIN list-to-detail navigation + search. Both specs are wired
   into `agent/test_impact_analysis.py`'s `FRONTEND_PATH_TO_SPECS` so a
   future `index.html` change selects the full real coverage. Verified
   live against a real local `mvnw spring-boot:run` instance (8/9 passing
   together with the pre-existing Update Email spec; forced to
   `mode: "serial"` after a real, observed 4-worker contention timeout
   against the single dev Tomcat instance — not an app defect), and the
   new suite was observed genuinely failing once (a deliberately seeded
   wrong expected value in the Preferences reload assertion) before being
   fixed back, per this project's "a new test is not trusted until it has
   been observed failing" rule.
2. Python Test Impact Analysis not yet built (§C) — Python changes are
   flagged, not auto-selected.
3. No CI wiring yet (§R) — deliberate, awaiting explicit approval.
4. No property/fuzz/performance/chaos tooling (§G/§K) — deliberately
   deferred, not mandatory per-change. **Correction 2026-09-20**: mutation
   testing (PIT) specifically is NOT still open — it was added to
   `app/pom.xml` by BL-006 the same night this doc was first written; this
   item's original wording was stale and is corrected here rather than
   left standing.
5. No cross-run economics aggregation yet (§Q) — evidence capture starts
   now; aggregation is future work.
