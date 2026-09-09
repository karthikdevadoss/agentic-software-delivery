# Roadmap (future increments — none of this is implemented yet)

Long-horizon direction, kept separate from PROJECT_STATUS.md (verified
progress) and DECISIONS.md (why choices were made). This file is vision/
reference, not a build plan for the current session. See docs/CONSTITUTION.md
for the operating principles that govern how all of this should be pursued
(smallest useful step, real verification, no scope drift, no fabricated
maturity).

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

## Multi-agent roadmap (not built — currently ONE reasoning agent; RAG/MCP/deterministic functions are tools, not agents)

Possible future agents (create only when there's a real job, isolated
context/specialization provides measurable benefit, evidence exists to
reason over, and benefit exceeds coordination/token/cost overhead):
orchestrator, requirement/business analyst, context/retrieval, planner,
architecture, coding, build/test, failure diagnosis, reviewer, security,
runtime/UI verification, Git/PR, release/deploy, production observer, eval,
FinOps/model router, memory curator, standards checker, product/customer
value, sales/GTM, finance. Before retaining any new agent, eventually
compare quality/latency/tokens/cost/human-effort/redundancy/coordination
against not having it. Remove unnecessary agents.

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

## Explicitly deferred (roadmap only — do not build without a new explicit task)

Dashboard UI, Creator Session Intelligence UI, external/interviewer
dashboard, Project Intelligence Chat, SQLite telemetry store, OpenTelemetry
export, full FinOps platform, multi-agent architecture, founder/CTO/CFO/
sales agents, sales CRM, huge enterprise corpus, production deployment,
Streamable HTTP hosting (tracked as ACTION_QUEUE ACT-005 for local
verification only), formal constitution *engine* (the constitution itself
is docs/CONSTITUTION.md; enforcement automation is future), full benchmark/
eval platform, AST-aware chunking, production vector DB.
