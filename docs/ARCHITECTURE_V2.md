# Architecture V2 — Skills + Independent QA Evaluator (Foundation)

Status: **FOUNDATION ONLY — no production cutover.** The public Workbench
(`agent/web_server.py`'s `_run_trainer_thread`) is unchanged by this
document and remains the live execution path. This document designs the
next architecture increment and records the evidence behind every choice
made building it. See docs/ARCHITECTURE_V2_KNOWLEDGE_MAP.md (inventory)
and docs/ARCHITECTURE_V2_EVALUATION_PLAN.md (how we'll know if this is
actually better) for the companion documents.

Governing layer: docs/CONSTITUTION.md is unchanged and unreinterpreted by
this work. Nothing here amends purpose, prescribed duty, truth/evidence,
capability≠authority, or any other constitutional rule — this document
only applies them to a new architecture increment.

## Baseline (frozen before this work started)

Git tag `trainer-preview-v1-stable`, commit `b64d535` (2026-09-11).
Verified at tag time:
- Public Workbench (`https://agentic-platform-backend-production.up.railway.app/workbench`) — HTTP 200.
- Public Customer App (`https://agentic-delivery-customer-app-production.up.railway.app/`) — HTTP 200.
- Real modifying acceptance run `trainer-4733d1c0` (Create → Create
  Customer): COMPLETED, commit `12dfbd8`, real 80s production wait,
  `content_verified=true`, independently re-confirmed live.
- Real usage/cost capture: 6 API calls, 37,340 input + 2,821 output
  tokens, $0.10289.
- Event ledger reachable (Railway Postgres) with 1,145+ real events at
  tag time.
- `RAILWAY_TOKEN` confirmed working for the Customer App auto-deploy
  (verified without ever reading its value — see
  docs/PROJECT_STATE.json's `workbench_p0_trainer_readiness_acceptance`).

Rollback point: `git checkout trainer-preview-v1-stable` returns to this
exact, independently-verified-working state if V2 work ever regresses
the live trainer experience.

## 1. Verified current Claude Code capabilities (2026-09-11)

Installed Claude Code version on this machine: **2.1.267** (`claude
--version`). The following was independently verified via the
`claude-code-guide` subagent WebFetching current official docs (not
recalled from training memory) on 2026-09-11:

| Capability | Location / config | Status | Source |
|---|---|---|---|
| Agent Skills (project) | `.claude/skills/<name>/SKILL.md`, frontmatter `name`+`description` required | GA | code.claude.com/docs/en/skills.md |
| Custom subagents | `.claude/agents/<name>.md`, frontmatter `name`+`description` required; `tools`/`disallowedTools`/`model`/`isolation` optional | GA | code.claude.com/docs/en/sub-agents.md |
| Agent Teams | opt-in via `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | **EXPERIMENTAL, disabled by default** | code.claude.com/docs/en/agent-teams.md |
| Auto Mode | `permissions.defaultMode: "auto"` in settings, or `Shift+Tab` at runtime | GA | code.claude.com/docs/en/permission-modes.md, .../auto-mode-config.md |
| Hooks | `~/.claude/settings.json` **only** (project `.claude/settings.local.json` is silently rewritten by the permission-remember mechanism — confirmed by this project's own incident `36fbcbe`) | GA (command/http/prompt); `agent`-type hooks experimental | code.claude.com/docs/en/hooks-guide.md, .../hooks.md |
| Project settings.json | Skills/agents/permissions/MCP/env/model keys | GA | code.claude.com/docs/en/settings-reference.md |

**Decision this evidence supports:** Skills + one focused subagent are
fully GA and require nothing experimental. Agent Teams is explicitly
**NOT enabled** — see §9 for why.

## 2. Deterministic vs. Agentic Classification (§4 of the task)

**A — DETERMINISTIC (stays code, never becomes an LLM judgment call):**

| Responsibility | Real implementation |
|---|---|
| Compile | `agent/build_tools.py` / `run_controlled_compile` |
| Test-applicability fact-check | `agent/web_server.py::_tests_applicable` |
| Secret scan | existing git-workflow discipline (CLAUDE.md's Git Safety Protocol) |
| Git status/commit SHA | `agent/web_server.py`'s `_run_controlled` git calls |
| Deployment state decision | `agent/web_server.py::_decide_deployment_outcome` |
| HTTP/content checks | `agent/web_server.py::_fetch_public_app` + the new content-verification loop |
| Repository-workspace precondition | `agent/web_server.py::_check_repository_workspace_ready` |
| Token accounting | `agent/metrics.py::record_model_usage` (sourced from the real API response, never estimated) |
| Pricing calculation | `agent/pricing_config.py` |
| Risk/complexity gate | `agent/risk_policy.py::classify` |

**B — AGENTIC JUDGMENT (the Skills/subagent's actual job):**

- Understanding a natural-language requirement.
- Investigating the repository to find the right file(s).
- Proposing an implementation.
- Deciding what test scenarios are meaningful (when tests genuinely apply).
- Reasoning about ambiguity in a requirement.
- Root-causing an unexpected failure from evidence.
- Reviewing evidence against acceptance criteria (the `qa-evaluator`'s job).

**Explicit rule (this task, restated from CLAUDE.md/CONSTITUTION.md):** no
row in table A is ever converted into a Skill or subagent prompt merely
because Skills/subagents are the new mechanism. `agent/risk_policy.py` in
particular stays a plain deterministic function — see
docs/ARCHITECTURE_V2_KNOWLEDGE_MAP.md's explicit "DO NOT convert to an
LLM prompt" row.

## 3. Skills created (§6 of the task)

Five project Skills at `.claude/skills/<name>/SKILL.md`, GA format,
`name`+`description` frontmatter:

1. **requirement-contract** — requirement → `AcceptanceContract`.
2. **implement-small-change** — Contract → real applied+compiled change.
3. **test-change** — decide/record the truthful testing terminal state,
   gate commit on it.
4. **production-verify** — independently confirm the requested effect is
   live in real production (never HTTP 200 alone); carries the 11 real
   escaped-defect lessons as its knowledge base.
5. **incident-analysis** — root-cause an unexpected result from real
   evidence (event ledger, `knowledge/sessions/`, `docs/LESSONS.md`).

Each Skill's body states its single prescribed duty, canonical sources
(referenced, never copied), inputs, outputs, evidence required, and an
explicit "Must NOT" section — see each `SKILL.md` for the full text.
None of the five duplicates a deterministic gate's logic; each references
the real code path by name.

## 4. Acceptance Contract (§5 of the task)

Status: **DESIGNED and standalone-tested**, not yet wired into
`agent/web_server.py`'s live pipeline (see §14 below).

`agent/acceptance_contract.py`: a small dataclass
(`requirement_id`, `requirement_text`, `target_application`,
`expected_observable_effect`, `affected_scope`, `risk`,
`required_gates`, `testing_expectation`,
`production_verification_expectation`, `allowed_terminal_outcomes`,
`evidence_requirements`) plus a `validate()` method that checks:
- required text fields are non-empty,
- `expected_observable_effect` is non-empty (a contract with no
  independently-checkable effect reproduces the false-success incident),
- every `required_gates` entry names a real, known deterministic gate,
- every `allowed_terminal_outcomes` entry is one the real runtime can
  actually produce (cross-checked against
  `agent/web_server.py::TERMINAL_RUN_STATES` — `test_acceptance_contract.py`
  proves these two sets stay equal).

Worked example (`example_create_customer_contract()`): the exact real
"Create → Create Customer" requirement this project already executed for
real, expressed as a contract.

7 focused tests in `agent/test_acceptance_contract.py`, all passing.

## 5. Independent QA Evaluator (§7 of the task)

One subagent, `.claude/agents/qa-evaluator.md`, GA subagent format.

- `tools: Read, Glob, Grep, Bash, WebFetch` / `disallowedTools: Write, Edit, NotebookEdit`.
- Non-negotiable rule stated verbatim in its own file: **the
  implementation agent may not certify its own production success.**
- Evaluates independently: re-runs/re-reads real tests, re-fetches real
  production content directly, re-reads the real event ledger — never
  trusts a reported status string.
- Returns PASS / FAIL / UNKNOWN — UNKNOWN is a first-class, honest
  outcome, never forced into PASS or FAIL.
- Explicitly may not modify production code during evaluation. **Known,
  flagged limitation:** `Bash` is granted for read-only verification
  (curl, git inspection, running the test suites) but is not yet
  restricted to a hard-enforced allowlist of exact commands — the
  no-mutation rule is currently enforced by instruction, not by a
  technical block. This is recorded honestly rather than overclaimed;
  tightening it (e.g. per-command Bash allowlisting once that subagent
  syntax is confirmed) is a candidate future action, not silently
  assumed safe.

No large agent team was created — this is the ONE independent evaluator
the task asked for, nothing more.

## 6. Browser / E2E evaluation capability (§8 of the task)

**Current state, verified 2026-09-11:** `claude mcp list` shows no
browser-automation MCP server configured in this environment (only
Google Drive, Microsoft 365, and Vercel connectors — none relevant).
Playwright MCP (`@playwright/mcp`, Microsoft-maintained) is a real,
commonly-used option for this purpose, but **installing it would add new
infrastructure to the environment and was NOT done in this task** — per
the explicit instruction to stop and report rather than silently add
infrastructure.

**Would it verify something current tests cannot?** Yes, partially: real
rendered/interactive behavior (JS-driven UI state, visual layout) that a
raw HTML fetch cannot see. **Would it help for what this project has
actually needed so far?** No — every real requirement executed to date
(footer text, button label) was fully verifiable via a direct HTML fetch
(`curl`/WebFetch), which the `production-verify` Skill and `qa-evaluator`
already use.

**Decision: NOT justified yet.** Cost (a new external dependency,
additional token/time cost per evaluation, a new security surface for a
tool that can navigate arbitrary URLs) is not offset by a real
requirement it would uniquely solve. Revisit when a real requirement
needs to verify rendered/interactive behavior a raw HTML fetch cannot
capture — track that trigger in docs/ACTION_QUEUE.json if/when it
actually occurs, not preemptively.

## 7. Orchestration Model V2 (§9 of the task) — DESIGN ONLY

```
HUMAN OWNER
     |
     v
DELIVERY ORCHESTRATOR   (currently: main Claude session, per-task; not a new persistent process)
     |
Acceptance Contract     (requirement-contract Skill)
     |
     +----------------------+
     |                      |
     v                      v
IMPLEMENTER             QA EVALUATOR       (qa-evaluator subagent — separate context, never shares
     |                      |                the implementer's reasoning trace)
implement-small-change   test-change /
     Skill               production-verify Skills
     |                      |
     +----------+-----------+
                |
                v
        DETERMINISTIC GATES   (unchanged: risk_policy, build_tools, _tests_applicable,
                |               _decide_deployment_outcome, pricing_config, event_ledger)
          PASS / FAIL / UNKNOWN
                |
                v
       DEPLOY / STOP / ESCALATE
```

The "DELIVERY ORCHESTRATOR" is not a new running service in this task —
it is the role a Claude Code session plays when it uses these Skills in
sequence. No new persistent orchestration process was built. Agent Teams
(§1) would be the natural mechanism for the implementer and evaluator to
run as genuinely separate concurrent sessions later — deliberately not
adopted yet (experimental, and no measured need for concurrent/debating
agents established — see §9 of the task and docs/CONSTITUTION.md §10,
non-attachment to a particular architecture).

## 8. Human authority (§10 of the task) — unchanged, restated for this increment

Preserved exactly, not reinterpreted: docs/CONSTITUTION.md §11
(capability ≠ authority) and docs/AI_COLLABORATION.md's existing
Human/ChatGPT/Claude-Code split. The Human Owner in the diagram above
retains authority over purpose, constitutional values, material
ambiguity, high-risk changes, production policy, secrets, irreversible
actions, security-boundary changes, and materially expanded scope — the
`qa-evaluator` does not change who holds that authority; it only adds an
independent evidence-check step before a claim reaches the human. Auto
Mode (§1) is noted as available but is **not** enabled or treated as
standing authorization for anything beyond what it already covers today.

## 9. Continuous learning loop rule (§11 of the task)

Every escaped defect continues to follow: observable failure → preserved
evidence (event ledger, never overwritten) → root cause
(`incident-analysis` Skill) → correction (`implement-small-change`) →
deterministic regression/eval when practical → Skill/lesson update
(`docs/LESSONS.md` + the relevant `SKILL.md`) → future measurement
(docs/ARCHITECTURE_V2_EVALUATION_PLAN.md).

**Review trigger (new, lightweight rule):** before adding to or keeping
any Skill/evaluator/agent from this architecture, periodically ask: does
it still add measurable value over not having it; has a newer Claude
model made a component's judgment reliable enough that the extra
evaluation step is no longer paying for itself; is the cost (tokens,
time, coordination) still justified by the quality improvement it
produces. No component here is exempt from removal if evidence says so —
docs/CONSTITUTION.md §10, non-attachment, applies to this architecture
itself.

## 10. Event ledger (§13 of the task)

**No schema migration performed or needed.** `infra/event-ledger/schema.sql`
already has a `payload JSONB` column used pervasively for event-specific
data (e.g. `risk_assessment`'s embedded `estimate`, `deployment`'s
`content_verified` field added this session). The following event
*types* are designed to ride the existing envelope additively, the same
way `run_usage_summary` and `repository_workspace_check` were added in
prior tasks — **not implemented in this task** (no orchestrator exists
yet to emit them; implementing unused event types would be exactly the
"unnecessary activity" docs/CONSTITUTION.md §1/§7 warns against):

- `acceptance_contract_created`
- `implementer_started` / `implementer_completed` / `implementer_failed`
- `evaluator_started`
- `evaluator_verdict` (PASS/FAIL/UNKNOWN + evidence summary)
- `deterministic_gate_result` (gate name + real result — reuses gate
  names from `agent/acceptance_contract.py::KNOWN_DETERMINISTIC_GATES`)
- `human_intervention` (already partially covered by
  `authorization_decision` with a human `decided_by`; a dedicated type
  would let future Usage/Dashboard queries distinguish this class without
  string-matching `decided_by`)

All prior events remain untouched; no failed run's evidence is
overwritten by this design.

## 11. No production cutover (§14 of the task)

The live Workbench execution path (`agent/web_server.py::_run_trainer_thread`)
is **unmodified** by this task. Skills/evaluator/contract exist as
foundation artifacts, verified in isolation (their own tests pass,
formats are GA-verified), not yet wired into the public-facing pipeline.
Cutover happens only after docs/ARCHITECTURE_V2_EVALUATION_PLAN.md's
comparison produces real data favoring V2.

## 12. Why we are introducing Skills and an independent evaluator (§16 of the task)

**Why Skills:** this project's engineering knowledge (production-
verification rules, testing truthfulness, incident lessons) was
accumulating correctly in docs/LESSONS.md and code, but nothing
organized it into a reusable, on-demand form a future session could load
without re-deriving it from scratch each time. Skills are the
GA-supported, lowest-overhead mechanism for that — they reference
existing canonical sources rather than duplicating them.

**Why an independent evaluator exists:** this project has a real,
documented incident (`trainer-7769757e`) where the implementer's own
success report was wrong, and the wrongness was only caught by a human
manually checking production. `docs/CONSTITUTION.md` §11 already
establishes "a reviewer doesn't approve itself where independence
matters" as a standing principle; the `qa-evaluator` subagent is the
first concrete architecture component built specifically to enforce that
for this project's own production-verification claims.

**Why full Agent Teams are NOT enabled yet:** the feature is
experimental (disabled by default, requires an explicit opt-in env var),
has documented limitations (no session-resumption for in-process
teammates, no nested teams), and — per docs/CONSTITUTION.md §10/§7 —
this project only adopts new architecture when a measured need exists.
A single independent evaluator subagent already provides the
"independent judgment" property this task asked for without the added
cost/complexity/experimental-feature risk of full concurrent teams.

## What remains unchanged

- The live public Workbench, its risk policy, its security/write
  boundary, its approval boundary, its event ledger schema, its pricing
  table, its testing/deployment gate logic.
- docs/CONSTITUTION.md, CLAUDE.md, docs/AI_COLLABORATION.md, and every
  other Layer-0/operating document — none were rewritten or reinterpreted.
- All existing regression tests — none were deleted or weakened.
