# Architecture V2 — Knowledge Inventory

Companion to docs/ARCHITECTURE_V2.md (design) and
docs/ARCHITECTURE_V2_EVALUATION_PLAN.md (benchmark). This file is an
**inventory/mapping**, not a rewrite of existing docs — see
docs/CONSTITUTION.md §17: no important knowledge may be duplicated across
several canonical files, so this map points AT sources rather than
copying them. Written before any Skill/subagent was created, so migration
decisions are made deliberately rather than by default.

Baseline this inventory was taken against: git tag
`trainer-preview-v1-stable` (commit `b64d535`, 2026-09-11) — see
docs/ARCHITECTURE_V2.md §Baseline for the full freeze evidence.

## Format

| Knowledge / Rule | Current Source | Current User | Future Owner | Migration Action | Keep Original? |
|---|---|---|---|---|---|

## Inventory

| Knowledge / Rule | Current Source | Current User | Future Owner | Migration Action | Keep Original? |
|---|---|---|---|---|---|
| Production verification rules (HTTP 200 ≠ success; requested-content check; deployment-activation wait) | docs/LESSONS.md (the `trainer-7769757e` entry) + `agent/web_server.py::_decide_deployment_outcome`/`_check_repository_workspace_ready` + `agent/test_web_server.py`'s `DeploymentOutcomeDecisionTestCase`/`ContentVerificationTestCase` | main Claude (ad hoc, per task) | `production-verify` Skill + `qa-evaluator` subagent | Skill/evaluator **reference** these files by path; do not restate the rule as new prose that could drift from the code | YES |
| Testing-truthfulness rules (explicit PASSED/NOT_APPLICABLE/FAILED, never ambiguous-pending, commit gated on verification policy) | docs/LESSONS.md + `agent/web_server.py::_tests_applicable` + `agent/web/workbench.js`'s `testingChecklistState` + `test_web_server.py::TestApplicabilityGateTestCase` | main Claude | `test-change` Skill + `qa-evaluator` | Reference/reuse; the deterministic check (`_tests_applicable`) is never re-implemented in a Skill | YES |
| Repository-workspace-readiness precondition (fail before mutating source) | `agent/web_server.py::_check_repository_workspace_ready` + `test_web_server.py::RepositoryWorkspaceReadyTestCase` + docs/LESSONS.md (`trainer-6aedf022`) | main Claude / runtime | `implement-small-change` Skill (references it as a precondition to check) | Reference only — the check itself stays a Python function, never becomes an LLM judgment call | YES |
| Terminal-timing correctness (client-clock-only durations, freeze on terminal) | docs/LESSONS.md + `agent/web/workbench.js` (`tick()`, `applyEvent`'s stage case) + `test_trainer_frontend.js` (`testL_terminalTimingFreezesAndNeverGrows`) | frontend runtime | `qa-evaluator` (checks this class of defect when evaluating a UI-visible change) | Reference; no Skill needed to *produce* this — it's already fixed runtime code | YES |
| Risk/complexity classification (auto-execute vs. requires-authorization) | `agent/risk_policy.py` (deterministic keyword/length heuristic) | `agent/web_server.py`'s trainer route | unchanged — **deterministic runtime, never an LLM prompt** | **DO NOT** convert to an LLM judgment call; a Skill may *reference* the decision it already produced, never re-derive it | YES |
| Pre-run token/cost estimation | `agent/estimation.py` (historical-average + heuristic, versioned `ESTIMATE_METHOD_VERSION`) | `agent/web_server.py` assess/start routes | unchanged — deterministic | No Skill; already a deterministic function with its own tests (`test_estimation.py`) | YES |
| Actual usage/cost calculation | `agent/pricing_config.py` (versioned pricing table) + `agent/web_server.py::_build_usage_summary` | `agent/web_server.py` | unchanged — deterministic | No Skill; `qa-evaluator` reads its output as evidence, never recomputes it | YES |
| Event ledger schema/semantics (canonical envelope, `source`/`activity_class`, idempotent inserts, secret redaction, backfill provenance) | `infra/event-ledger/schema.sql` + `agent/event_ledger.py` | all runtime producers (Workbench, Claude Code hooks) | unchanged — canonical evidence layer | **NONE** — additive event *types* only if truly needed (see docs/ARCHITECTURE_V2.md §Event Ledger); no schema migration | YES |
| Write/build security boundary (path traversal, symlink, secret-filename rejection, scope-restricted writes, controlled-subprocess discipline) | `agent/tools.py` + `agent/write_tools.py` + `agent/build_tools.py` | `agent/execution_tools.py` (the model-facing tool surface) | unchanged — deterministic security code | **DO NOT** let any Skill or subagent describe these as "guidelines" — they are hard boundaries enforced in code regardless of what any agent is told | YES |
| Approval boundary (approve/reject never model-callable, fails closed with no human present) | `agent/execution_tools.py` + `agent/execution_agent.py` + `test_execution_tools.py` (exact set-membership tests) | `agent/web_server.py`'s human/trainer approval prompts | unchanged | No migration; `qa-evaluator` never gets this authority either (§7/§10 of this task — QA never mutates production) | YES |
| Historical incident narratives (real root causes, what was tried, what worked) | `knowledge/sessions/*.md` + docs/LESSONS.md | main Claude (read at session start per CLAUDE.md when relevant) | `incident-analysis` Skill | Skill references the directory + file naming convention; does not copy incident text into the Skill body | YES |
| Session-startup discipline (read state → verify against reality → report → don't modify until asked) | CLAUDE.md §"Session startup" | main Claude, every session | unchanged — this is the operating contract for *any* Claude session, Skill-augmented or not | No migration — Skills operate *within* this discipline, they don't replace it | YES |
| Proactive-action / stability-discipline policy (fix-in-scope-and-verify vs. queue-in-ACTION_QUEUE) | CLAUDE.md §"Proactive action policy"/"Stability / Execution Discipline" | main Claude | unchanged | Referenced by `implement-small-change` Skill's "must NOT" section | YES |
| Constitution (purpose, prescribed duty, truth/evidence, capability≠authority, non-attachment, etc.) | docs/CONSTITUTION.md | every agent/role in this project | unchanged — Layer 0, no lower layer may override | Skills/`qa-evaluator` reference relevant sections (§4 truth, §9 success/failure, §11 capability≠authority); the document itself is never restated or reinterpreted | YES |
| Human/AI role split (Owner/ChatGPT/Claude Code responsibilities) | docs/AI_COLLABORATION.md | project-wide | unchanged | Orchestrator design (docs/ARCHITECTURE_V2.md §9) explicitly maps onto this existing split — HUMAN OWNER row is not a new concept | YES |
| Product/company vision, public-surface decisions | docs/COMPANY_VISION.md | project-wide | unchanged | Not touched by this task | YES |
| Architecture decisions + why | docs/DECISIONS.md | project-wide | unchanged | This task's own decisions (Skills format chosen, why no Agent Teams yet, etc.) are additive entries here, not a rewrite | YES |
| Verified project state / evidence | docs/PROJECT_STATE.json | project-wide | unchanged | This task adds new `verification_state`/`completed_capabilities` entries additively | YES |
| Recovery procedure (fresh-machine bootstrap) | docs/RECOVERY.md | new session / new machine | unchanged | Not touched; Skills don't change how a fresh session recovers state | YES |
| Non-secret resource registry (URLs, providers) | docs/RESOURCE_REGISTRY.md | project-wide | unchanged | Not touched this task | YES |
| Secrets registry (names/purposes only) | docs/SECRETS_REGISTRY.md | project-wide | unchanged | Not touched; RAILWAY_TOKEN's *existence* is already recorded there — no value ever appears anywhere | YES |
| Open smaller action items (ACT-001/002/005) | docs/ACTION_QUEUE.json | project-wide | unchanged | Not touched — none relate to this task's scope | YES |

## What this inventory deliberately does NOT do

- It does not copy risk_policy.py's keyword list, the pricing table, the event schema, or any test assertions into a Skill body — Skills **reference** file paths so the single source of truth never drifts.
- It does not propose converting any deterministic gate (risk policy, pricing, estimation, security boundary, approval boundary) into an LLM-judged Skill — see docs/ARCHITECTURE_V2.md §Deterministic vs. Agentic Classification for the explicit rule and reasoning.
- It does not touch CLAUDE.md, docs/CONSTITUTION.md, or any other Layer-0/operating document — Skills operate *inside* those rules, they do not amend them.
