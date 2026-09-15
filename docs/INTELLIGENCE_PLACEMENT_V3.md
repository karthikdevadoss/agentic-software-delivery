# Intelligence Placement Audit V3

Phase 1 of the Base Architecture V3 directive. Every entry below traces to
real code inspected this session (file:line), not to what PROJECT_STATE.json
or PROJECT_STATUS.md *claim* exists — those docs were used only to find
where to look; every claim here was re-verified directly against the
current repository via Read/Grep before being written down, per this
project's own CLAUDE.md ("actual repository state wins on conflict").

Methodology: for each capability — purpose, current implementation
(file:line), current decision-maker, current source of truth, whether an
LLM participates and whether that's necessary, deterministic alternative,
consequence if wrong, correct owner (DETERMINISTIC / LLM / HUMAN / HYBRID),
existing verification, recommended change, IMPLEMENT/DEFER/REJECT + reason.

## Capabilities

### Requirement intake & normalization (Workbench public demo path)
- **Implementation:** `agent/web_server.py:1099` `_assess_public_demo_requirement()` → `agent/demo_catalogue.py:175` `normalize_requirement()` (pure regex/string matching against a fixed catalogue of supported operations, raises `UnsupportedRequirement`/`InvalidValue`, never a partial/best-guess result).
- **Decision-maker:** DETERMINISTIC. Zero API calls in this path — confirmed no `anthropic`/model import anywhere in `demo_catalogue.py`.
- **LLM involved:** No. **Necessary:** N/A.
- **Consequence if wrong:** an unsupported requirement is rejected with a clear reason; cannot silently misclassify since match is exact-catalogue-only.
- **Owner:** DETERMINISTIC (correct as-is).
- **Verification:** `agent/test_web_server.py` (104 tests, includes this gate), used identically by both the preview endpoint and the real execution gate (`start_trainer_run`, `web_server.py:1189`) so they can't diverge.
- **Recommendation:** REJECT (no change) — already correctly deterministic, already the reference example for how this pattern should look elsewhere.

### Backend requirement routing (RAG/MCP eligibility gate)
- **Implementation:** `agent/backend_planning.py:95` `classify_backend_routing()` — runs `risk_policy.classify()` then `demo_catalogue.normalize_requirement()` on raw text, BEFORE any retrieval exists to poison the decision. Returns `ROUTE_DETERMINISTIC_ONLY` / `ROUTE_USE_RAG_MCP` / `ROUTE_REJECT_UNAUTHORIZED`.
- **Decision-maker:** DETERMINISTIC.
- **Owner:** DETERMINISTIC (correct as-is) — this is the clearest existing example of "decide authority before the LLM sees anything."
- **Verification:** `agent/test_backend_planning.py` (28 tests incl. `SecurityEvalTestCase`'s structural prompt-injection-inertness proof).
- **Recommendation:** REJECT (no change).

### Risk/complexity classification (Workbench text-level authorization gate)
- **Implementation:** `agent/risk_policy.py:78` `classify()` — keyword denylist (`BLOCK_KEYWORDS`, line 28) + word-count heuristic. Explicitly documented as "deliberately simple... a classifier that can't explain why it blocked something is not acceptable for a production-authority gate" (line 16-19).
- **Decision-maker:** DETERMINISTIC. Defense-in-depth: `write_tools.py:42`'s `ALLOWED_WRITE_PREFIXES`/`ALLOWED_WRITE_EXTENSIONS` independently re-checks file scope even if this text gate is wrong (documented real gap closed by 2nd layer: 4/10 adversarial prompts once passed the text layer but were still blocked at the file-scope layer, per docs/PROJECT_STATUS.md's "JOB-SEARCH LIVE DEMO P0" entry).
- **Owner:** DETERMINISTIC (correct as-is).
- **Recommendation:** REJECT (no change) — two independent deterministic layers is the right shape.

### Change risk / blast-radius classification (post-implementation, drives test selection)
- **Implementation:** `agent/change_risk.py:55` `RULES` — ordered regex-to-(risk,blast_radius) table over changed file paths, first-match-wins. `classify_change()` (line 115) takes the MAX risk across all touched files, and fails closed to `UNKNOWN` if any path is unrecognized (line 134-138) rather than diluting a real risk with unrelated safe files.
- **Decision-maker:** DETERMINISTIC.
- **Owner:** DETERMINISTIC (correct as-is).
- **Gap:** `agent/verify_change.py` (the consumer of this classification) is NOT wired into `.github/workflows/ci.yml` — confirmed: CI (`ci.yml:1-40`) runs `./mvnw test -B` unconditionally, with no reference to `verify_change`/`change_risk`/`test_impact_analysis` anywhere in the workflow file. Already tracked honestly as open item (3) under `TESTING-ARCH-V1-GAPS` in `docs/ACTION_QUEUE.json`.
- **Recommendation:** IMPLEMENT (Phase 6/10) — wire `verify_change.py` as an *additive* annotation step in CI first, per that action item's own stated plan, before ever making it an authoritative gate.

### Repository navigation / symbol resolution / dependency analysis
- **Implementation:** `agent/tools.py` (read-only `list_repository_files`/`read_file`/`search_code`, path-security via `_resolve_safe_path`), `agent/rag_index.py` (fastembed + numpy cosine similarity, local JSON index), `agent/backend_rag_index.py` (curated corpus, chunked at logical boundaries).
- **Decision-maker:** DETERMINISTIC for path resolution/security; retrieval ranking is a real embedding model but is explicitly non-authoritative — `backend_planning.py:299` `check_groundedness()` independently verifies every file the LLM's analysis claims to have used was actually retrieved (not merely plausible-sounding), and this check "NEVER gates authorization" (comment, line 303) since `backend_catalogue.py` already decided the one permitted file independently.
- **Owner:** HYBRID (retrieval = LLM-adjacent/embeddings, correctness-of-claims-against-retrieval = DETERMINISTIC) — already correctly split.
- **Missing deterministic layer:** no AST/symbol-graph tool (JavaParser/OpenRewrite-class) exists — all code understanding is either grep/regex (`tools.py`) or semantic embedding similarity (`rag_index.py`). "Callers of changed method" / "authorization-boundary reachability" / "dangerous source→sink path" questions have no deterministic answer today; an LLM reading grep results is the only current path.
- **Recommendation:** DEFER — Phase 8 candidate, evaluate JavaParser (Java-only, project is 90% one Spring Boot module) against real project questions before adopting; current grep+RAG combination has caused zero observed defects tied to this specific gap.

### Test planning/selection/execution/pass-fail
- **Implementation:** `agent/test_impact_analysis.py` (Java file→test-module mapping table), `agent/build_tools.py` (allowlist-only `compile`/`test`, no shell — `subprocess` called with an argv list, not `shell=True`), `agent/verify_change.py` (selective regression engine + fail-closed fallback).
- **Decision-maker:** DETERMINISTIC.
- **Gap (confirmed real, not hypothetical):** `agent/triage_execution.py:321` `_isolated_compile_java_candidate()` — the AI-generated Triage candidate-patch verification path — runs `mvnw -q compile` only (line 362), never `mvnw test`. `agent/web_server.py:1614` treats `status == "COMPILE_VERIFIED"` as sufficient to call `triage_promotion.record_verified_candidate()` (line 1615), which is the exact gate that makes a candidate eligible for the human "Promote to Production" action. **A patch that compiles but does not actually fix the reproduced defect (or breaks something else covered by `TriageScenarioAIntegrationTest`) can reach the human-approval stage carrying a label ("COMPILE_VERIFIED") that sounds stronger than what was actually checked.**
- **Owner:** DETERMINISTIC compile check is correct as far as it goes; the missing piece (running the real Scenario test class against the candidate in the same isolated workspace) is also DETERMINISTIC, not LLM — this is a coverage gap, not a misplaced-authority gap.
- **Recommendation:** IMPLEMENT (HIGH priority) — extend `_isolated_compile_java_candidate()` to also run the specific `TriageScenarioXIntegrationTest` class against the isolated copy and require both compile AND that test to pass before `record_verified_candidate()` is called. The human approver still has final authority either way, but today the machine-readable status they see overstates verification depth.

### Authorization / security policy (production)
- **Implementation:** `app/src/main/java/com/example/customer/security/SecurityConfig.java:80-118` — explicit per-route `hasAuthority("SCOPE_...")` matrix (admin-only Triage approve routes, admin-only customer list, scoped preference/contract/appointment/customer read/write). `WorkspaceAccessGuard.java:25` enforces per-customer data isolation.
- **Decision-maker:** DETERMINISTIC (Spring Security, compiled route matchers — cannot be talked around by prompt text).
- **Owner:** DETERMINISTIC (correct as-is) — real, structurally enforced, not policy-in-a-prompt.
- **Recommendation:** REJECT (no change) — this is exactly Phase 13's target shape already.

### Database correctness / business invariants
- **Implementation:** `ContractPlanService.java:45` — explicit idempotency no-op check on duplicate enrollment (the real AEQ-family defect fix, commit `2155a8a`). Flyway versioned migrations (`app/src/main/resources/db/migration/`).
- **Decision-maker:** DETERMINISTIC (compiled Java + DB constraints + Flyway version history).
- **Verification:** `TriageScenarioAIntegrationTest` (5 tests) reproduces the historical bug and proves the fix; CI runs real Postgres via Testcontainers (`ci.yml:20-26`), not H2-only (closes the exact class of gap that caused AEQ-012, the JPQL LOWER/CONCAT-on-nullable-bind Postgres-only bug per showcase.yaml's own talking points).
- **Recommendation:** REJECT (no change) — correct owner, real regression coverage.

### Retry classification / timeouts
- **Implementation:** `AppointmentAvailabilityClient.java` (Resilience4j circuit breaker + retry, composed programmatically — 7 real WireMock tests per `docs/PORTFOLIO_CAPABILITIES.yaml:73`). `agent/event_ledger.py:162` sets real server-enforced `statement_timeout=15000`/`idle_in_transaction_session_timeout=30000` on every Postgres connection (the actual AEQ-010 incident fix — an idle-in-transaction connection had frozen the whole async service).
- **Decision-maker:** DETERMINISTIC.
- **Recommendation:** REJECT (no change) — already the project's strongest example of "root-caused an incident into an executable, server-enforced timeout, not a policy doc."

### Workflow transitions (Workbench/Triage run lifecycle)
- **Implementation:** `agent/web_server.py:315` `class Run` — `self.status` (line 319) is a **plain string attribute**, set directly at ~15+ call sites throughout the file (`run.status = "DEPLOYMENT_STATUS_UNKNOWN"` at line 1027 is one example). `TERMINAL_RUN_STATES` (line 114) is a frozenset used only to decide when SSE streaming should stop — there is no `VALID_TRANSITIONS` table anywhere in the file (confirmed: no such identifier exists via grep) and nothing prevents a future code path from setting `.status` to an illegal value or skipping a required evidence check before a "later" stage.
- **Decision-maker:** Implicit — whatever the current call site's author intended, not a validated state machine. In practice this has not caused an observed defect (every status-setting call site is small and reviewed), but there is no structural guarantee.
- **Owner:** DETERMINISTIC (a real state machine, not an LLM concern either way).
- **Consequence if wrong:** a future change (including an AI-generated one) could set an illegal status transition, silently corrupting the run's displayed state, with nothing to catch it.
- **Recommendation:** IMPLEMENT (Phase 5, MEDIUM-HIGH) — introduce an explicit `RunState` enum + a `VALID_TRANSITIONS: dict[str, set[str]]` table, with `Run.set_status()` as the only mutator, raising on an illegal transition. This is the single most concrete, safe, mechanical Phase 5 starting point in the whole codebase — bounded blast radius (one class), directly testable, and closes a real (if not-yet-triggered) structural gap.

### Git / candidate identity / promotion
- **Implementation:** `agent/triage_promotion.py` — `record_verified_candidate()`/`promote_verified_candidate()` bind a SHA256 hash of the exact reviewed candidate at approval time (TOCTOU-safe per its own docstring, mirroring the same pattern already proven in `agent/write_tools.py`'s approve/apply hash binding).
- **Decision-maker:** DETERMINISTIC (hash equality, not LLM judgment).
- **Verification:** `agent/test_triage_promotion.py` (8/8, real local git repo standing in for origin).
- **Recommendation:** REJECT (no change) — this IS Phase 14's provenance/identity-chain requirement, already built correctly at the candidate-hash level; the remaining provenance gap is the full chain from requirement→deployed artifact, not this specific link.

### Deployment eligibility/state, production correctness
- **Implementation:** `agent/demo_execution.py`'s `wait_for_new_deployment()` (timestamp-parsed, not raw-string-compared, per the AEQ/ACT-008 fix already recorded), `agent/backend_execution.py`/`agent/backend_catalogue.py` (targeted production assertions via a JSON-field extractor, never whole-file substring checks).
- **Decision-maker:** DETERMINISTIC (real HTTP GET against the live production endpoint is the primary evidence; Railway CLI status only corroborates — `_decide_deployment_outcome()` per PROJECT_STATUS.md's documented design).
- **Recommendation:** REJECT (no change) — already matches Phase 19's evidence-authority-hierarchy principle (direct runtime observation > CLI status polling).

### Route validity / browser correctness
- **Implementation:** `agent/web_server.py:1896-1964` `routes` list (Starlette `Route`/`Mount`). Until this session: **no deterministic check that every rendered link on a public page actually resolves to a registered route** — this was exactly the AEQ-022 defect (see the Quality Ledger entry, and `agent/test_showcase_data.py`, fixed this session).
- **Decision-maker:** now DETERMINISTIC for Showcase (Starlette's own `Route.matches()`, not string comparison) — `agent/test_showcase_data.py:30` `_internal_path_is_routable()`.
- **Remaining gap:** the same class of check does not yet exist for the top nav / hardcoded links inside `agent/web/*.html` templates themselves (only Showcase's *manifest-driven* links are covered) — Learn/Usage/Workbench have Playwright coverage of their own internal drill-down links (`e2e/*.spec.js`) but no single generalized "every link on every public page resolves" sweep exists.
- **Recommendation:** IMPLEMENT (MEDIUM) — a single Playwright spec that crawls every public route's rendered `<a href>` set and asserts each either 200s (internal) or is a well-formed absolute URL (external), generalizing AEQ-022's fix beyond just Showcase.

### RAG retrieval & corpus completeness
- **Implementation:** `agent/backend_rag_corpus.py`/`agent/backend_rag_index.py` (curated ~80-chunk corpus, not whole-repo), `agent/eval_runner.py` (recorded thresholds: `recall_at_3=1.0`, `recall_at_5=1.0`, `mrr=0.903` on 12 hand-labeled cases per `docs/ACTION_QUEUE.json`'s `RAG-MCP-EVALS-P0`).
- **Decision-maker:** HYBRID — retrieval ranking is model-adjacent (embeddings), but authorization/routing is fully deterministic and precedes it (see `classify_backend_routing` above), and groundedness is independently checked after (see `check_groundedness` above).
- **Recommendation:** REJECT (no change) — already dogfooded with real evals, already the project's reference example for "LLM output independently checked, never trusted."

### MCP execution
- **Implementation:** `agent/mcp_server.py:1-30` — explicit docstring: "Read-only, no write/build/deploy tools are exposed here by design" (line 29). Confirmed by inspection: zero write/build tool registrations in the file.
- **Decision-maker:** DETERMINISTIC (tool exposure is a fixed, auditable list, not runtime-negotiated).
- **Recommendation:** REJECT (no change).

### Model selection / token accounting / cost arithmetic
- **Implementation:** `agent/pricing_config.py` (versioned fixed pricing table, verified against live Anthropic pricing docs, not model-estimated), `agent/estimation.py` (historical-comparable heuristic, clearly confidence-labeled LOW/MEDIUM/HIGH), `agent/metrics.py` (real token counts from `response.usage`, never invented).
- **Decision-maker:** DETERMINISTIC (arithmetic over real API response fields).
- **Recommendation:** REJECT (no change) — this is Phase 24's exact target shape ("model authority explicitly prohibited over... cost calculations").

### Quality/incident diagnosis, root-cause reasoning, candidate repair generation (Triage Lab)
- **Implementation:** `agent/triage_execution.py:382` `diagnose()` — one on-demand Claude call given real evidence, returns JSON `{hypothesis, root_cause, affected_component, confidence}`. **Never gates any action** — confirmed by tracing every caller: it's displayed in the UI only, no downstream code branches on `diagnose()`'s output. Malformed JSON is handled honestly (line 405-409: reported as `explanation`, never silently trusted/guessed).
- `generate_candidate_patch()` (line 216) — a SECOND Claude call writes an actual fix. Authority is correctly bounded: applied only in an isolated temp copy (line 347 `tempfile.mkdtemp`), never the real repository, and requires human ADMIN approval (`triage_approve`, `web_server.py:1625`, verified server-to-server against real `/auth/login`) before promotion. The one real gap here is the compile-only verification already flagged above under "Test planning."
- **Decision-maker for diagnosis:** LLM, correctly ADVISORY-ONLY (no code trusts it for anything but display).
- **Decision-maker for candidate generation:** LLM proposes, DETERMINISTIC compile gate + HUMAN approval decide — correctly bounded, modulo the test-execution gap above.
- **Recommendation:** REJECT for `diagnose()` (already correctly advisory) / see "Test planning" entry above for the one real fix needed in this path.

### Rollback/restore
- **Implementation:** `agent/event_ledger_backup.py` — manual, on-demand `pg_dump`-based export, proven live (59/59 rows exported per `docs/RESOURCE_REGISTRY.md`). **Restore has never been tested** (explicitly documented as an open gap, not fabricated as done).
- **Decision-maker:** N/A (human-triggered operational tool, no LLM).
- **Recommendation:** DEFER — a real restore drill is valuable but is an operational exercise, not an architecture decision; track in ACTION_QUEUE (already effectively is, via the honest "not yet tested" language in RESOURCE_REGISTRY.md).

### Agent permissions / human approval
- **Implementation:** `agent/execution_tools.py:202-211` `_EXECUTION_DISPATCH` — exactly 4 keys (`propose_source_change`, `apply_approved_source_change`, `run_controlled_compile`, `run_controlled_tests`); `approve_edit`/`reject_edit` are confirmed absent from both the dispatch dict and `EXECUTION_TOOL_SCHEMAS` (line 200) — verified by direct inspection, not by trusting the docstring claim.
- **Decision-maker:** DETERMINISTIC (Python dict membership — structurally impossible for the model to self-approve, not merely instructed not to).
- **Recommendation:** REJECT (no change) — this is Phase 13's exact target shape, already real.

### CI
- **Implementation:** `.github/workflows/ci.yml` — real `mvn test -B` against GitHub-hosted runners with a real Docker daemon (so `PostgresFlywayIntegrationTest`'s Testcontainers Postgres actually runs, unlike local dev on this Windows machine with no Docker — confirmed via the workflow's own comment, line 20-23).
- **Gap:** `verify_change.py`/`change_risk.py`/`test_impact_analysis.py` are NOT wired in (see "Change risk" entry above) — CI always runs the full suite regardless of blast radius, which is safe but doesn't yet use the selective-regression engine that was built.
- **Recommendation:** IMPLEMENT (see Change risk entry) — additive annotation first.

### Provenance / event ledger / quality ledger
- **Implementation:** `agent/event_ledger.py` (786 lines — write-through Postgres event store, outage-spooling, idempotent `ON CONFLICT DO NOTHING`, real per-connection timeouts). `docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml` (23 defects as of this audit, structured schema, `recurrence_status` tracked honestly).
- **Decision-maker:** DETERMINISTIC for storage/idempotency/ordering; ledger *content* (root cause narrative) is human/AI-authored prose, explicitly labeled `EXACT` vs `INFERRED` confidence per entry rather than presented uniformly as fact.
- **Recommendation:** REJECT (no change) — already the project's reference implementation for Phase 12's escaped-defect compiler concept, just not yet formalized as a required step-by-step pipeline with enforced `recurrence_status` progression away from `DOCUMENT_ONLY`.

---

## MISPLACED_LLM_DECISIONS

None found at CRITICAL or HIGH. This codebase already consistently applies "LLM proposes, deterministic code verifies, human approves" — every write/deploy/promote path traced during this audit (Workbench execution, Triage candidate generation, MCP tool exposure) has a real structural (not prompt-only) boundary preventing the model from certifying its own work or bypassing approval.

- **MEDIUM — Triage candidate "COMPILE_VERIFIED" label overstates what was checked.** `agent/web_server.py:1614` and `agent/triage_execution.py:321` mark a candidate as verified/promotable after a successful `mvnw compile` only, never running the actual regression test that proves the reproduced defect is fixed. The label itself isn't LLM output, but it *represents* the LLM's candidate as more verified than it is to the human approver. See "Test planning" entry for the fix. Not CRITICAL because a human still reviews the diff before promotion and no promotion has ever actually been exercised (`TRIAGE-CANDIDATE-PROMOTION-PIPELINE` remains `READY_FOR_HUMAN_APPROVAL`, never fired).
- **LOW — `risk_policy.looks_already_satisfied()` keyword-matches the LLM's own free-text run summary** (`agent/risk_policy.py:138`) to help label a run outcome (ALREADY_SATISFIED vs FAILED). Explicitly documented as never gating write/deploy authority either way (comment, line 120-127) — this is a display/labeling nuance, not an authority gap.

## MISSING_DETERMINISTIC_INTELLIGENCE

- **HIGH — No test-execution step in the Triage candidate-verification path** (`agent/triage_execution.py:321` `_isolated_compile_java_candidate()`). Compile-only verification is a real, closeable gap: extend to run the scenario's own integration test class in the same isolated workspace before `record_verified_candidate()` is called.
- **MEDIUM-HIGH — No explicit workflow state machine for Workbench/Triage runs.** `Run.status` (`agent/web_server.py:319`) is an unvalidated string set at 15+ call sites with no `VALID_TRANSITIONS` table. No observed defect yet, but no structural guard either — the cleanest, most bounded Phase 5 starting point in the repo.
- **MEDIUM — `verify_change.py`/`change_risk.py`/`test_impact_analysis.py` built but not wired into CI.** Real selective-regression engine exists and is tested, but `.github/workflows/ci.yml` doesn't use it (confirmed: zero references in the workflow file). Already tracked as `TESTING-ARCH-V1-GAPS` item 3 in `docs/ACTION_QUEUE.json`; this audit confirms it's still true.
- **MEDIUM — No generalized "every public page's rendered links resolve" sweep**, only per-page Playwright coverage (Learn/Usage/Workbench) plus the newly-added Showcase-manifest-specific check (`agent/test_showcase_data.py`). AEQ-022's fix was scoped to the one page that broke; the same defect class could recur on a hardcoded nav link elsewhere.
- **LOW-MEDIUM — No deterministic AST/symbol-graph code intelligence tool.** All "what calls X" / "what does Y depend on" questions today resolve via grep (`tools.py`) or semantic embedding similarity (`rag_index.py`), never a real symbol graph. Zero observed defects tied to this gap so far; Phase 8 candidate, evaluate before building (JavaParser is the most plausible fit given this is a single-module Java project).
- **LOW — No mutation/property testing anywhere in the Java or Python suites.** `test_state: TESTED`/`INTEGRATION_TESTED` labels throughout `docs/PORTFOLIO_CAPABILITIES.yaml` measure test *existence*, never test *effectiveness* (would a seeded defect actually be caught). No PIT dependency exists in `app/pom.xml` (confirmed via grep — zero matches). Phase 11 candidate.
