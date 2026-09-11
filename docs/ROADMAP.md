# Roadmap (future direction — sections below vary in implementation status; check docs/PROJECT_STATE.json for what's actually true now)

Long-horizon direction, kept separate from PROJECT_STATUS.md (verified
progress) and DECISIONS.md (why choices were made). This file is vision/
reference, not a build plan for the current session. See docs/CONSTITUTION.md
for the operating principles that govern how all of this should be pursued
(smallest useful step, real verification, no scope drift, no fabricated
maturity). See docs/COMPANY_VISION.md for the durable "why" and public
product structure this roadmap executes toward.

## Near-term ordered roadmap (directional, not scheduled — order may be revisited)

1. **Durability / no data loss** — this organizational continuity
   checkpoint, then a durable remote event ledger so new runs/sessions
   are never lost (see "Data as a strategic asset" below).
2. **Live Dashboard + Usage** — same durable evidence source, continuously
   improving the intelligence surfaced.
3. **Stable public infrastructure / canonical URLs** —
   `agentic.karthikdevadoss.com`, `app.karthikdevadoss.com`; no resume
   dependency on an ephemeral laptop Cloudflare Quick Tunnel.
4. **Operator notification + safe autonomy** — notify when human
   approval/input is actually required; reduce unnecessary approvals
   without bypassing any safety boundary.
5. **Independent credibility audit** — a sanitized evidence package,
   reviewed by a fresh Claude/ChatGPT session with no prior context,
   later an external-model audit — establishing a capability credibility
   baseline instead of self-assessment alone.
6. **Resume-ready checkpoint** — only evidence-backed claims, a stable
   flagship URL.
7. **Workbench product cleanup** — rename Trainer → Workbench, remove the
   public Control Plane as a competing page, implement the two
   requirement tiers (below), link to the production app only after a
   verified deployment.
8. **Learn foundation** (see topic index below).
9. **Requirement catalogue + enterprise app expansion** (see target
   application growth below).

## Two-tier Workbench product model (accepted direction, not implemented)

**Tier 1 — Open demo:** anyone may execute bounded tiny/small, low-risk,
reversible, inexpensive changes — the Workbench should proactively offer
several safe suggested requirements, and offer safe alternatives if a
visitor enters something larger/riskier (this part already exists in
spirit — see `agent/risk_policy.py`'s deterministic classifier).

**Tier 2 — Owner-authorized build:** larger functional requirements
require a short-lived owner authorization. Preferred initial semantics:
**one code = one requirement.** The code is short-lived, validated
server-side, hashed at rest, rate-limited, never sent to the LLM, and
never logged in plaintext. The owner receives it via transactional email
(SMS optionally later). Authorization **never** bypasses security,
verification, destructive-operation protection, or engineering quality
gates — it only grants scope, never trust. Not implemented in the current
codebase.

## Target application growth (accepted direction)

Continuously grow the current Customer application into a clean-room
enterprise customer/utility-style platform, purely to create increasingly
realistic software-engineering scenarios for the Workbench to operate on
— see "Enterprise benchmark roadmap" below for the existing ladder this
extends. Possible future business areas, entering only when a real
requirement justifies them (never merely to look sophisticated):
customer/account/profile, contact information, addresses, preferences,
plans/contracts, billing, payments, notifications, appointments,
documents, auth/authorization, audit, integrations, caching, async/event
processing, distributed services, schema migrations, backward
compatibility, production incidents, cross-service changes. Never copy
proprietary third-party code, data, or confidential internal designs from
any real company.

## Learn — AI-only living interview book (accepted direction, not built)

Explicitly **not** a general Java/Spring textbook — backend technologies
appear only where needed to explain how an AI capability interacts with
this project's actual code. Initial topic index:

AI Foundations (LLMs, tokens, context window, inference, transformers,
attention, embeddings) · Prompting/Context Engineering · RAG (retrieval,
chunking, vector search, hybrid search, reranking) · Tool Calling/Function
Calling/MCP · Agents (agent loop, planning, state, memory,
self-correction, multi-agent systems) · Agentic Software Delivery ·
Evals/Quality · AI Security (prompt injection, tool authorization,
sandboxing, human authority) · Observability (tokens, latency, cost,
model routing) · Models/Training (fine-tuning, preference data,
evaluation data, proprietary models).

Each topic can carry: definition, why, mechanics, subtopics, alternatives,
failure modes, current industry state, how this project actually uses it,
real project evidence, lessons, interview questions (30-second / 2-minute
/ deep answers), related topics. **Knowledge availability ≠ project
implementation** — e.g. "Multi-Agent Systems: knowledge AVAILABLE,
project NOT IMPLEMENTED" must be shown as exactly that, never blurred.
Not built yet; UI and content generation are future work.

## Two immediate MVP outcomes + one ultimate purpose

1. **Career/portfolio evidence** — real, verifiable AI engineering knowledge
   and artifacts (code, tests, traces, benchmarks) covering LLM APIs, context
   engineering, embeddings, RAG, MCP, tools, agents, multi-agent systems,
   memory, evals, reliability, security, observability, FinOps, model
   routing, agentic SDLC, human+AI delivery, business value. Never fabricate
   expertise — evidence must come from actual implementation.
2. **Sellable product** — a narrow, genuinely valuable software-delivery
   workflow (requirement → understand repo → retrieve evidence → grounded
   plan → safe code change → compile/build → test → diagnose → self-correct
   → review/security → runtime verify → reviewed change/PR → human approval
   only where judgment/risk requires it) that a real engineering team could
   pay for.
3. **Ultimate company purpose** — repeatedly create substantial genuine
   customer value through reliable agentic software delivery, and
   sustainably capture part of that value as revenue. Technology, agents,
   and complexity are not the purpose.

At every stage ask: does it actually work? does it increase career value?
does it increase real customer/commercial value?

## Future control plane — two audiences (not built yet)

- **Creator/Owner cockpit** (private): session intelligence ("was this
  session worth it, and why"), AI engineering maturity, architecture/RAG/MCP/
  agents/memory/evals/reliability/security/observability/FinOps, standards
  freshness, learning/corrections, career readiness, product/commercial
  readiness, company metrics, next highest-value action.
- **External/interviewer/customer view** (permission-filtered): what the
  system is, what it does, capabilities, agents, autonomy level, accuracy/
  reliability, security posture, cost, benchmarks, evidence, human
  intervention remaining, customer value. Never expose secrets, hidden
  chain-of-thought, private prompts, private customer source, cross-tenant
  data, private sales details.

## Project Intelligence Chat (not built yet)

A conversational assistant answering questions like "why was X decided",
"what did agent Y do", "why did Z fail", "what evidence supports this",
grounded in real project evidence (code, Git, docs, decisions, lessons, RAG,
traces, metrics, tests, benchmarks) — never hidden chain-of-thought.

## Session Intelligence (not built yet)

Track (only with trustworthy instrumentation — never invent unavailable
telemetry): time (elapsed/AI/human/approval-wait), AI usage (calls, tokens,
cache hits, model, cost, tool calls), output (files/tests/commits/
capabilities advanced), quality (outcome, verification strength, failures,
retries, regressions, unsupported claims), learning (mistakes found/
corrected, recurrence, lessons reused), efficiency (redundant reads/
research/embeddings/calls), value (career, technical, product, commercial).

## AI Engineering Intelligence maturity model (conceptual, not scored yet)

0 not present · 1 designed · 2 implemented · 3 unit tested · 4 runtime
verified · 5 benchmark/eval proven · 6 production-like/enterprise validated.
Never fabricate a level; keep evidence confidence separate from maturity.
Areas: LLM/API correctness, prompting, structured output, context
engineering, embeddings, retrieval, RAG, vector/index design, MCP, tool
calling, agents, multi-agent orchestration, memory/state, evals,
hallucination/grounding, guardrails, human-in-loop, security, observability,
FinOps, cost/latency, caching, model routing, resilience/self-correction,
production architecture, agentic SDLC, governance/privacy, standards
freshness, business/customer value.

**Current honest snapshot** (see PROJECT_STATE.json verification_state for
per-capability detail): MCP and RAG are at roughly level 3–4 (unit tested /
runtime verified) for the local read-only scope; nothing in this project is
at level 5–6 yet. Do not describe any capability here as higher than its
recorded verification_state status.

## Metric north stars (future — not instrumented yet)

Quality, autonomy, efficiency, RAG (Recall@K/Precision@K/MRR/retrieval→
verified ratio), MCP/tools (calls/latency/failures/blocked-unsafe/
truncation), model/FinOps (routing, escalation, cache efficiency, cost),
learning (correction success, recurrence, lesson reuse), security/governance
(least privilege, excessive-agency prevention, secret handling, prompt-
injection/RAG-poisoning resistance, audit evidence). Company/customer value:
customer pain evidence, time-to-value, sales funnel, engineering hours
saved, retention, unit economics. **Overall north stars: cost per verified
change, tokens per verified change, time per verified change, human minutes
per verified change, autonomous verified completion rate, customer value
created per verified change.** Never fabricate a commercial metric before
real customer evidence exists.

## Founder/company decision perspectives (structured views, not agents, until justified)

Founder/Owner, Product, CTO/AI, Sales/GTM, Customer Success, CFO/unit
economics, Security/Risk, Competitive/Market — initially just structured
lenses over shared evidence, not separate agents. No role-play agents with
no data to reason over.

## Multi-agent roadmap (foundation only — one implementer + one independent QA evaluator subagent exist as of 2026-09-11; neither is wired into the live public pipeline yet; RAG/MCP/deterministic functions remain tools, not agents)

`qa-evaluator` (`.claude/agents/qa-evaluator.md`) was created as the
first real step down this roadmap — see docs/ARCHITECTURE_V2.md for the
full design, why it exists (a real false-success incident,
`trainer-7769757e`), and why full Agent Teams were deliberately NOT
enabled (experimental, no measured need yet). It has not replaced the
live implementer path and is not yet measured against it — see
docs/ARCHITECTURE_V2_EVALUATION_PLAN.md.

Possible further future agents (create only when there's a real job,
isolated context/specialization provides measurable benefit, evidence
exists to reason over, and benefit exceeds coordination/token/cost
overhead): orchestrator, requirement/business analyst, context/retrieval,
planner, architecture, coding, build/test, failure diagnosis, security,
runtime/UI verification, Git/PR, release/deploy, production observer,
eval, FinOps/model router, memory curator, standards checker,
product/customer value, sales/GTM, finance. Before retaining any new
agent, eventually compare quality/latency/tokens/cost/human-effort/
redundancy/coordination against not having it. Remove unnecessary agents.

## Data as a strategic company asset (accepted top priority, not implemented)

Capture valuable, lawful, observable software-delivery data as early as
possible — historical trajectories cannot be recreated later once lost.
This is why "durable remote event ledger" is the near-term roadmap's #1
item. Desired categories: requirements/prompts supplied where safe/
authorized, run/session lifecycle, risk/complexity decisions, model
calls (provider/model/version, input/output tokens when exposed,
latency), tool calls/results, retrieval/RAG activity, file/change
metadata, proposals, authorization requests/decisions, builds, tests/
evals, failures/errors/timeouts, commits, deployments, production
verification, human interventions, transport/infrastructure problems,
corrections, regression outcomes. **Preserve failures — never overwrite
them with later successes** (this project's `web_run_history.jsonl` and
`knowledge/sessions/` records already follow this in miniature; the
future event ledger generalizes it). Never store hidden model
chain-of-thought, plaintext passwords/OTP codes, API keys/tokens, or
unnecessary personal/customer data. Data classification and training
eligibility must become part of future data governance before any of
this feeds model training.

## Evidence/provenance (no graph DB yet)

Eventually reconstructable: requirement → retrieved evidence → decision →
agent/tool actions → code changes → compile/test → runtime evidence →
review → approval → PR → deploy → production observation → lesson. Preserve
practical metadata now where cheap (source path, chunk hash, retrieval
score, provider/model/version, run ID, verifier, test/commit evidence) —
already partially true of the RAG index and metrics.py. Don't overbuild
metadata infrastructure ahead of need.

## Standards freshness process

Already practiced in DECISIONS.md's "Standards freshness" table (technology,
chosen version, source, date verified, reason, re-check trigger). Continue
that pattern for future fast-moving choices; don't repeat research when
already-fresh.

## Enterprise benchmark roadmap (grow requirement-by-requirement, never manually pre-built; clean-room synthetic only, never proprietary data)

Ladder: 1) one-class endpoint, 2) controller/service/repository, 3)
persistence/migration, 4) cross-layer validation, 5) cross-service work, 6)
event+DB+external API, 7) security-sensitive change, 8) ambiguous/
conflicting docs, 9) production defect diagnosis, 10) architecture-level
change. Future synthetic domain surface (customer/billing/payments/plans/
notifications/auth/audit/etc.) and evidence corpus (schemas, ADRs, diagrams,
rules, specs, tickets, runbooks, incidents, stale/conflicting docs) — grown
only as real requirements demand it, starting from the current tiny Customer
app.

## YogaCRM future pilot (accepted direction — do not touch YogaCRM yet)

A real, externally-developed CRM product, identified as a potential first
genuine external product pilot for the Workbench. Safe progression: local
benchmark proof → YogaCRM read-only repository understanding → a real
requirement → agent proposal → a dedicated Git branch → automated tests →
staging → human review → only after that evidence, controlled production
use, with humans retaining business/risk/approval responsibility
throughout. Do not assume repository access, technology stack,
credentials, CI/CD, staging, or production permissions — ask the owner
when any of those actually become relevant. See docs/IDEAS.md for what
remains genuinely unresolved about this pilot.

## Explicitly deferred (roadmap only — do not build without a new explicit task)

Dashboard UI, Creator Session Intelligence UI, external/interviewer
dashboard, Project Intelligence Chat, SQLite telemetry store, OpenTelemetry
export, full FinOps platform, multi-agent architecture, founder/CTO/CFO/
sales agents, sales CRM, huge enterprise corpus, production deployment,
Streamable HTTP hosting (tracked as ACTION_QUEUE ACT-005 for local
verification only), formal constitution *engine* (the constitution itself
is docs/CONSTITUTION.md; enforcement automation is future), full benchmark/
eval platform, AST-aware chunking, production vector DB.
