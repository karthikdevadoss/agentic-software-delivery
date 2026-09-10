# Company Vision (durable north star)

This file is the durable "why" and "what structure" — it should change
rarely. Ordered execution steps belong in docs/ROADMAP.md; specific
accepted decisions and their rationale belong in docs/DECISIONS.md;
unresolved possibilities belong in docs/IDEAS.md. Do not mix these.

## Product / company

**Agentic Software Delivery.**

## Core purpose

Turn real software/business requirements into controlled, evidence-backed,
verified software changes — and, where authorized, verified production
outcomes. This platform is **not merely a Claude coding demo**. A demo
proves a model can write code once, in a controlled setting, for an
audience. This platform's actual bet is the delivery system around the
model: risk classification, approval boundaries, build/test verification,
production truth-checking, and the accumulated evidence of all of it —
not the model call itself.

## What actually differentiates this over time

Models are commodity workers. The durable, hard-to-replicate assets are:

- **Delivery orchestration** — the propose → approve → apply → build →
  test → deploy → verify pipeline itself, and its safety boundaries.
- **Engineering policies** — the deterministic, evidence-based rules that
  decide what an agent may do autonomously vs. what needs a human (risk
  classification, terminal-state truth, production-reality-wins logic).
- **Evaluation/quality system** — regression tests built from real
  incidents, not synthetic ones; a permanent discipline of evidence →
  root cause → fix → regression → durable lesson.
- **Accumulated software-delivery trajectories** — real requirement →
  investigation → decision → code → verification → outcome sequences,
  preserved as they happen, not reconstructed later (see docs/ROADMAP.md,
  "durable remote event ledger").
- **Human decision/intervention data** — when and why a human actually
  had to step in, and whether that intervention was necessary.
- **Architecture/business context** — the accumulated, evidence-backed
  understanding of a real (or realistic) codebase over time.
- **Durable evidence** — everything above, actually recoverable from a
  canonical store, not living only in a laptop or a chat session.
- **Proprietary learning/eval data** — the eventual training-data asset
  that only accrues if the above is captured faithfully from day one.

**Models and vendors are workers/providers, not the product architecture.**
This project remains model/vendor-neutral by design — see
docs/CONSTITUTION.md §10 (non-attachment to our own technology). Today's
implementation happens to use Anthropic's Claude API; that is an
implementation detail, not a claim of exclusivity or dependency lock-in.

## Public product structure (current accepted decision)

Five public surfaces, one flagship product (Profile added 2026-09-10):

1. **Workbench** — the main product surface. Requirement → analysis →
   implementation → verification → deployment → production verification.
2. **Dashboard** — current platform capability, quality, health, evidence,
   production truth, open problems, and freshness of that evidence.
3. **Usage** — runs/sessions/model calls/tool calls/tokens/time/cost/
   failures/retries/human intervention/productivity/economics.
4. **Learn** — an AI/Agentic-AI-**only** interactive learning and interview
   book, covering AI/Agentic-AI knowledge plus the relevant software-
   engineering concepts, technologies, protocols, bugs, scenarios,
   architecture decisions, human-approval concerns, and business value
   actually encountered while **building** this AI system. Explicitly not
   a general Java/Spring textbook — backend technologies may appear only
   where needed to explain how an AI capability interacts with this
   project's real, actual code.
5. **Profile** — a one-page, evidence-backed professional profile. A
   technology or topic being learned/touched while building this system
   does **not** automatically become a resume claim on this page — Profile
   only asserts what is actually evidenced (see the Constitution's truth/
   zero-delusion principle, docs/CONSTITUTION.md §4).

Not implemented yet: Learn and Profile are both decision records only, not
built pages (see docs/ROADMAP.md for sequencing) — do not build either
from this document alone without an explicit task.

**Planned retirement (decision recorded here, not yet executed):** the
current "Control Plane" as a standalone public-competing page, and the
"Trainer" terminology, are slated to be folded into "Workbench" —
see docs/ROADMAP.md item 7. Not removed by this document; this is a
decision record only.

## Canonical naming / URL plan

**Existing personal site (protected, do not modify without a separate
explicit task):** https://karthikdevadoss.com — may contain older AI
claims that need a credibility review later; that review is a separate,
future task, not implied by this document.

**Planned flagship platform domain:** https://agentic.karthikdevadoss.com
  - `/` → Workbench
  - `/dashboard` → Dashboard
  - `/usage` → Usage
  - `/learn` → Learn
  - `/profile` → Profile

**Planned target-application domain:** https://app.karthikdevadoss.com
(the Customer app the Workbench modifies).

**These custom domains are NOT live.** Do not treat them as reachable
until docs/RESOURCE_REGISTRY.md records them as CURRENT with a verified
date. See that file for what is actually live today (as of this writing:
a Vercel deployment and a Railway deployment under their own default
subdomains, plus an ephemeral Cloudflare Quick Tunnel for local
development — all recorded there with accurate status).

## Organizational governance (accepted direction)

```
OWNER / CREATOR (ultimate purpose + constitutional authority)
        |
docs/CONSTITUTION.md (Layer 0 — no lower objective overrides this)
        |
CEO (business/customer/company execution)
CTO (technology/architecture/engineering)
CFO (capital/cost/unit economics)
        |
future: Product / Quality-Evidence / Security-Governance / Operations
```

The Owner retains ultimate purpose and constitutional authority — this
does not delegate away. CEO/CTO/CFO are **logical decision roles**, not
yet separate employees or separate AI agents — see docs/CONSTITUTION.md
for the amended role hierarchy and docs/ROADMAP.md for when (if ever)
these become real agents, which requires a measured need, not novelty.

**Quality/Evidence must eventually have independent STOP authority** over
unverified or unsafe delivery — i.e., a release/quality gate that cannot
be overridden merely because a business role wants a result faster. Not
implemented as a separate authority yet; today this is enforced by the
existing propose/approve/apply and production-verification boundaries
described in docs/PROJECT_STATE.json's `verification_state`.

## Data as a strategic company asset

See docs/ROADMAP.md's "Data as a strategic asset" section for the
accepted priority and category list — recorded there (not duplicated
here) since it directly feeds the near-term ordered roadmap.

## What this document is not

Not a roadmap (see docs/ROADMAP.md for ordered steps), not a decision log
(see docs/DECISIONS.md), not a list of unresolved ideas (see
docs/IDEAS.md), and not current verified state (see
docs/PROJECT_STATE.json — always the higher authority on "is X true right
now").
