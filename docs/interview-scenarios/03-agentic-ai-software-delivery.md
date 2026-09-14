# Interview Scenario: Agentic AI Software Delivery Pipeline

Derived from the actual implementation: `agent/web_server.py`, `agent/demo_execution.py`, `agent/backend_execution.py`, `agent/risk_policy.py`, `agent/demo_catalogue.py`, `agent/mcp_server.py`, `agent/rag_index.py`.

## Business Why

Demonstrate — not just claim — the emerging discipline of building
*reliable* software delivery on top of a *probabilistic* system (an LLM).
The differentiator is not "an AI wrote code." It's a measurable, auditable
process where a human never has to trust the AI's own self-report, every
stage produces independently-checkable evidence, and every real defect
found along the way was turned into a durable process/product improvement
(see docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml).

## Requirement

A natural-language requirement, submitted through a public UI, must:
- never execute an unauthorized/dangerous action, even under adversarial
  phrasing (verified via direct adversarial testing against the live
  endpoint, not just unit tests);
- if eligible, actually reach real production, verified independently —
  never just "the pipeline said it worked";
- fail closed (rejected, not silently ignored or silently broadened) for
  anything outside its bounded, safe scope;
- leave a human able to tell working/waiting/stalled/failed/completed
  apart at every point, live.

## Architecture

```
Requirement (free text)
   |
   v
Deterministic eligibility gate (agent/demo_catalogue.py / backend_catalogue.py)
   |-- length cap -> catalogue anchor-pattern match -> risk_policy.classify()
   |   (defense-in-depth: two independent checks, not one)
   |-- UNAUTHORIZED -> reject BEFORE any expensive work, exact catalogue
   |   examples shown, never silently broadened
   v (eligible)
Context retrieval (agent/mcp_server.py's search_project_context, RAG-backed)
   |-- curated corpus only (10 documents for the backend scenario, never
   |   the whole repo) -- see docs/ai/MODEL_LIMITATIONS.md "context pollution"
   v
LLM impact analysis (real Anthropic API call, claude-sonnet-5)
   |-- advisory only -- checked by a deterministic groundedness checker
   |   that flags any file the model claims but never actually retrieved
   v
Isolated workspace (fresh temp-dir clone of the real public GitHub repo --
   |   NEVER mutates the deployed container's own long-lived checkout,
   |   see docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml AEQ-008)
   v
Real build/test (mvnw compile, mvnw test -- actual subprocess, allowlist-
   |   only, no shell, no arbitrary command execution)
   v
Real git commit (dedicated demo/<run_id> branch, never master)
   v
Real git push attempt (honestly NOT_CONFIGURED if no write credential is
   |   provisioned -- an explicit, logged, non-fabricated state, not a
   |   silently swallowed failure)
   v
Real Railway deploy trigger + timestamp-based deployment-identity
   |   confirmation (createdAt > deploy_triggered_after_iso -- see AEQ-009,
   |   a real bug this project found and fixed in exactly this step)
   v
Bounded-retry production content assertion (distinguishing build SUCCESS
   |   from traffic cutover -- see AEQ-013's third bug)
   v
COMPLETED / NO_CHANGE_NEEDED / FAILED / DEPLOYMENT_STATUS_UNKNOWN
   (exact, unambiguous terminal states -- a failed/unknown run can never
   imply production success)
```

## The Human-Approval Boundary — Architecturally Enforced, Not Just Policy

`approve_edit`/`reject_edit` are **never exposed as an LLM-callable tool
schema and never reachable via the dispatch table by any name** — verified
by exact set-membership checks in tests, not a policy statement in the
system prompt. A real, deliberate test proved a naive substring check
(`'approve' in tool_names`) produces a false positive (see
docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml AEQ-003) — the actual proof uses
exact matching. This is the concrete meaning behind "AI does not certify
its own work": it is a structural property of the tool-calling surface,
not an instruction the model is trusted to follow.

## Real-Time Delivery Visibility (Workbench UI)

Server-Sent Events (SSE) stream every stage/tool/proposal/build/test/
deployment event live to the browser — but SSE alone was proven, via a
real incident (a Cloudflare Quick Tunnel silently dropped an entire stream
with zero bytes, zero error, while the backend genuinely executed to
completion), to be an unreliable sole signal. The fix: an always-on HTTP
poll of the authoritative `GET /api/runs/{id}` state runs alongside SSE as
a permanent safety net, not a failure-triggered fallback (a client cannot
always detect that class of silent transport failure to trigger a
fallback on in the first place).

## Failure Cases (real, evidenced)

- **Auth boundary drift** (AEQ-013 bug 1): an internal script predated a
  later JWT security rollout and never attached a bearer token — caught
  cleanly by the fail-closed baseline check, before anything was cloned,
  committed, or deployed.
- **Local clock skew** (AEQ-013 bug 2): the dev machine's system clock ran
  ~6.5 minutes ahead of true UTC, making every genuinely-new deployment
  look older than its own trigger time — two consecutive real runs falsely
  reported TIMEOUT even though the real deploys succeeded in under 3
  minutes. Fixed by reading a real HTTP `Date` header from a live URL
  instead of trusting the local clock.
- **No cutover retry window** (AEQ-013 bug 3): a real, transient HTTP 502
  during Railway's traffic cutover was reported as a false FAILED for a
  deploy that, independently re-verified moments later, was already
  correct.
- **Deployment-identity by ID difference, not recency** (AEQ-009): matched
  an unrelated, genuinely-failed deployment from 46 minutes earlier,
  reporting the whole pipeline FAILED while the real new deployment had
  succeeded. Fixed by timestamp-filtering (`createdAt > trigger_time`)
  instead of ID inequality.

All four were found only by **actually running the previously
unit-tested-only pipeline end to end for the first time** and
independently cross-checking the result via `curl`/`railway logs`/
`railway deployment list` — none were hypothetical or found by code
inspection alone. See docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml's AEQ-013
for the full account.

## Testing

Layered: deterministic-policy unit tests (catalogue/risk_policy), a real
local-git-repo-as-origin integration suite (`test_demo_execution.py`,
`test_backend_execution.py` — using a REAL git repo, not mocks, for exactly
the class of bug that mocks would hide), and Playwright E2E gated behind
`RUN_REAL_ACCEPTANCE=1` for the genuine mutating journey against real
production.

## Production Observability

Every stage/tool/model-call/build/test/deploy event is write-through
persisted to a durable remote Postgres event ledger (`agent/event_ledger.py`)
the moment it happens — not batched at run end — with outage-safe local
spooling and idempotent retry (`ON CONFLICT DO NOTHING`). A crash mid-run
loses nothing.

## Design Trade-offs

- Deterministic catalogue match (zero LLM calls) for the bounded public
  demo path, vs. LLM-mediated interpretation for open-ended requirements:
  the bounded path is both cheaper and strictly safer (no prompt-injection
  surface at all, since the model is never called), at the cost of only
  supporting a fixed, small set of pre-approved operations publicly.
- Isolated disposable clone per run vs. mutating a long-lived checkout:
  higher per-run overhead (a real `git clone`), but eliminates an entire
  class of state-leakage bugs between runs and between the orchestrator's
  own container state and the actual deploy target (see AEQ-008).

## What Changes at 10x Scale

- The single in-process run registry (`Run` objects) would need to become
  a real persisted job queue (the event ledger already provides durable
  history; a live run's in-flight coordination state does not yet survive
  a process restart).
- A single-operator approval registry ("one run at a time") would need a
  real multi-tenant approval queue.
- Isolated workspace cloning per run is fine at low request volume; at high
  concurrent volume it would need either a workspace pool or a more
  aggressive shallow-clone/cache strategy to keep per-run latency down.

## Interview Questions This Answers

- "How do you make an AI code-generation pipeline trustworthy in production, not just fast?"
- "What's the difference between an LLM proposing a change and a system verifying it actually happened?"
- "Describe a time you found a bug only by actually running something end-to-end for the first time, that no unit test could have caught."
- "How do you design a human-approval boundary that the AI itself cannot route around?"
- "Why is a live SSE stream not sufficient for a delivery UI, and what's your fallback design?"

## Live Demo / Evidence Links

- https://agentic-platform-backend-production.up.railway.app/workbench (submit a real, safe requirement and watch it live)
- docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml — AEQ-003, AEQ-008, AEQ-009, AEQ-013
- `agent/web_server.py`, `agent/demo_execution.py`, `agent/backend_execution.py` (real source)
