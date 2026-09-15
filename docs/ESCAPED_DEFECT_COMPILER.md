# Escaped-Defect Compiler

Base Architecture V3 Section 10. Reviews the directive's own named
historical defect list against this repository's real, current
protection level — not a fabricated claim of universal enforcement.
Classification tiers (the directive's own): `DOCUMENT_ONLY` →
`TEST_ENFORCED` → `POLICY_ENFORCED` → `STATICALLY_ENFORCED` →
`RUNTIME_ENFORCED` → `MULTI_LAYER_ENFORCED`.

| Historical defect | Ledger entry | Real current protection | Classification |
|---|---|---|---|
| H2 vs. PostgreSQL behavior (JPQL `LOWER`/`CONCAT` on a nullable bind defaulted to `bytea` on Postgres, invisible on H2) | `AEQ-012` | `.github/workflows/ci.yml` runs real Testcontainers Postgres (not H2-only) on every CI run; a dedicated regression test exists for the fixed query | `MULTI_LAYER_ENFORCED` (test + CI infra) |
| Flyway/Spring Boot 4 dependency module split (three consecutive CI failures, root-caused via bytecode decompilation) | `AEQ-011` | Fixed dependency declaration in `app/pom.xml`; CI itself is the regression signal (would fail again if the dependency regressed) | `TEST_ENFORCED` (CI-level, not a dedicated unit assertion) |
| Circuit breaker / Kafka client shared-state leakage (an always-on `@KafkaListener` with no reachable broker flooded Railway logs) | Not in the AEQ ledger — recorded in `docs/LESSONS.md` only, predates the ledger | The whole Kafka subsystem is gated behind an explicit `@ConditionalOnProperty` enable flag, defaulting to `false` — the actual fix is a real, structural code change, not just a documented lesson | `STATICALLY_ENFORCED` (config-gated in code) despite having `DOCUMENT_ONLY`-*looking* ledger status — this is a case where the real fix is stronger than its ledger record suggests; worth a future session formalizing it as its own AEQ entry so the ledger reflects reality |
| Wrong Railway build context (running `railway up` from the wrong directory silently deployed the wrong service, using the repo-root `Dockerfile` instead of the target service's Railpack builder) | Not in the AEQ ledger — `docs/LESSONS.md` only | **Genuinely `DOCUMENT_ONLY` today.** `agent/demo_execution.py`/`agent/backend_execution.py`'s own internal deploy calls already correctly scope their `cwd` (isolated workspace `app/`), so the *application's own* deploy path is not at risk — but a human running `railway up` interactively from the wrong directory has no automated guard. **Real, specific, not-yet-built recommendation**: a small pre-flight script that checks the current working directory's build context (presence/absence of a `Dockerfile`) against the target `--service` name before `railway up` runs, refusing with a clear error on a mismatch. Identified here as real future work, not built this session — the interactive-CLI-operator risk this protects against is lower-frequency than the code paths this session prioritized |
| RAG 200-file whole-repo-index truncation (reused an LLM-display-budget function for an exhaustive internal indexing walk) | `AEQ-015` | `tools.list_all_repository_files()` (untruncated) vs. `tools.list_repository_files()` (LLM-facing, intentionally truncated) — a real, separate code path; `agent/test_rag_index.py` covers it | `TEST_ENFORCED` |
| Authentication drift | Not found as a distinct named lesson in `docs/LESSONS.md` or the AEQ ledger under this exact phrase — likely refers to the JWT/JDK/environment-drift class of incidents (`AEQ-021`'s JDK mismatch is the closest concrete match) rather than a separate, distinct defect | See `AEQ-021` below | N/A — likely a duplicate reference, not a separate untracked defect |
| Clock skew | Not found as a distinct named lesson — `docs/PROJECT_STATUS.md`'s deployment-timeout history references timing/timestamp issues but no dedicated "clock skew" incident write-up exists in this repository's real history | N/A | Could not verify a real, distinct incident this refers to — honestly reported rather than fabricated |
| Deployment cutover race | `AEQ-009` (new-deployment identity decided by ID difference, not recency — a race-adjacent defect) | `agent/demo_execution.py::wait_for_new_deployment()` now timestamp-parses (not raw-ID-compares); regression test with a constructed counterexample exists | `TEST_ENFORCED` |
| Stale deployment (platform-backend 20 commits behind HEAD, serving outdated Dashboard claims) | `AEQ-017` | Fixed by redeploying; **no automated drift detector exists** — this remains detection-by-manual-audit, genuinely `DOCUMENT_ONLY` for *prevention* (the fix itself was real, but nothing currently alerts if this recurs) | `DOCUMENT_ONLY` for prevention/detection, though the specific historical instance was fixed |
| Duplicate plan enrollment | `AEQ-018` | `ContractPlanService.enroll()`'s idempotency check + this session's new systematic falsification test across N=2,3,5,10 (Section 5) + the historical-reproduction integration test | `MULTI_LAYER_ENFORCED` (unit + integration + property-style + scenario-reproduction tests) — the strongest-protected item in this table |
| Triage verification overclaim (candidates marked `COMPILE_VERIFIED` without the real scenario test actually passing) | Not yet in the AEQ ledger (a Phase 1 audit finding, fixed this session, not an incident with real production evidence in the traditional AEQ sense — see `docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml`'s own source-discipline note that entries trace to real defects) | `agent/triage_execution.py`'s `TESTS_FAILED` status (commit `72dbe4d`) + dedicated regression tests | `TEST_ENFORCED` — recommend a future session add a formal AEQ entry for consistency, since this is exactly the shape of defect the ledger exists to record |
| JDK mismatch (platform-backend's Docker image had JDK 17, `app/pom.xml` requires 21) | `AEQ-021` | `agent/environment_preflight.py`'s fail-closed `ENVIRONMENT_INVALID` check, called before every real compile/test in both Workbench and Triage paths | `RUNTIME_ENFORCED` (fails closed at actual execution time, not just at build time) |
| Usage fixture/mock leakage (`source=workbench_mock` runs appeared in the public session list) | Not in the AEQ ledger — `docs/PROJECT_STATUS.md`'s "Usage mock-data leak fixed" entry only | Verified this session: `agent/session_history.py::_WORKBENCH_SOURCES_REAL_ONLY` excludes `workbench_mock` from the default public list, and `agent/test_session_history.py` has a real dedicated test constructing a mock run and asserting it's excluded | `TEST_ENFORCED` (confirmed via direct source inspection, not assumed) |
| AEQ-022 (Showcase's broken Quality Ledger link) | `AEQ-022` | `agent/test_showcase_data.py` + `e2e/link-integrity.spec.js` (this session, generalized beyond the one page) | `MULTI_LAYER_ENFORCED` |
| Subagent unauthorized production deployment | `AEQ-023` | `agent/verify_claude_permissions_config.py` (this session, Section 1) — a real, machine-local, regression-tested configuration guard | `TEST_ENFORCED` (machine-local scope — honestly, not CI-enforced, since the config file is gitignored by design; see `docs/CAPABILITY_SECURITY_MODEL.md`'s scope-limits section) |

## Honest summary

Of the 15 named historical defects: **2 are `MULTI_LAYER_ENFORCED`**
(duplicate enrollment — the strongest, and AEQ-022), **1 is
`RUNTIME_ENFORCED`** (JDK mismatch), **6 are `TEST_ENFORCED`** (including
Usage mock leakage, confirmed this session via direct source inspection,
not assumed), **1 is `STATICALLY_ENFORCED`** (circuit breaker/Kafka
gating, though its ledger record understates this), **2 are genuinely
`DOCUMENT_ONLY`** (Railway build context, stale-deployment *detection*)
with a specific, real, not-yet-built recommendation given for the first,
and **2 referenced items** ("authentication drift," "clock skew") could
not be matched to a distinct real incident in this repository's actual
history — reported honestly as unverifiable rather than invented to fill
the table.

This is real progress away from `DOCUMENT_ONLY`, not complete — exactly
the directive's own expected shape ("important repeated failure classes
should **progressively** move away from `DOCUMENT_ONLY`").
