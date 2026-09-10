# Start Here

The single recovery entry point for this project. If you are a new
developer, a new Claude/ChatGPT session, or working from a new laptop,
start here before reading anything else.

## What company/product is this?

**Agentic Software Delivery.** A platform that turns real software/business
requirements into controlled, evidence-backed, verified software changes —
and, where authorized, verified production outcomes. See
[docs/COMPANY_VISION.md](docs/COMPANY_VISION.md) for the full purpose and
why this is not "just a Claude coding demo."

## Why are we building it?

Three connected goals, in this priority order when they conflict:
1. Real, evidence-backed career/portfolio proof of AI engineering ability.
2. A genuinely valuable, trustworthy software-delivery product.
3. Long-term: a company built on repeatable, verified customer value.

## What is the flagship product?

The **Agentic Software Delivery platform** itself — not the Customer app
it operates on (that's the *target* application, see below).

## What are the five public surfaces?

1. **Workbench** — requirement → analysis → implementation → verification →
   deployment → production verification. (Currently implemented and
   internally still named "Trainer" in code — see docs/ROADMAP.md for the
   planned rename.)
2. **Dashboard** — current platform capability, quality, health, evidence,
   production truth, open problems, freshness.
3. **Usage** — runs/sessions/model calls/tool calls/tokens/time/cost/
   failures/retries/human intervention/productivity/economics. (Currently
   implemented as `/sessions`.)
4. **Learn** — an AI/Agentic-AI-only interactive learning and interview
   book. Not implemented yet; see docs/ROADMAP.md.
5. **Profile** — a one-page, evidence-backed professional profile; a topic
   merely touched while building this system does not automatically
   become a resume claim. Not implemented yet; see docs/ROADMAP.md.

See docs/COMPANY_VISION.md for the accepted URL plan (current vs. planned).

## What is the target application?

A separate Spring Boot "Customer" app (`app/`), deliberately kept distinct
from the platform itself. It is what the Workbench proposes and verifies
changes against. See docs/RESOURCE_REGISTRY.md for its current live URL.

## What is currently implemented?

See **docs/PROJECT_STATE.json** — the authoritative, machine-readable
current state (`completed_capabilities`, `verification_state`,
`open_defects`). Do not trust a narrative summary (including this file)
over that file or over actual runtime/Git evidence if they disagree.

## What is currently NOT verified / still open?

See `docs/PROJECT_STATE.json`'s `missing_capabilities` and `open_defects`
keys, and docs/PROJECT_STATUS.md's "Current Reality" section for the most
recent narrative summary.

## What is today's current direction?

See **docs/ROADMAP.md**'s near-term ordered roadmap (durability first,
then live evidence surfaces, then stable public infrastructure, then
product cleanup). Directional, not a guarantee of dates.

## Which documents should be read next?

In this order:
1. `docs/PROJECT_STATE.json` — current verified truth (always check this first)
2. `docs/PROJECT_STATUS.md` — narrative progress + current reality
3. `docs/COMPANY_VISION.md` — durable purpose and product structure
4. `docs/CONSTITUTION.md` — operating principles and governance (read fully before making judgment calls)
5. `docs/DECISIONS.md` — why things were built the way they were
6. `docs/LESSONS.md` — reusable technical gotchas
7. `docs/ROADMAP.md` — future direction (do not build from it without an explicit task)
8. `docs/IDEAS.md` — unresolved possibilities, not yet committed
9. `knowledge/INDEX.md` — narrative incident/session records (interview-prep evidence)
10. `CLAUDE.md` — the operating instructions an AI session actually follows

## Where are source/runtime services/resources documented?

**docs/RESOURCE_REGISTRY.md** — the canonical non-secret registry of every
known URL, provider, and identifier, with CURRENT/PLANNED/EXPIRED status
and last-verified date. Trust this over memory of any URL mentioned
elsewhere.

## Where are secrets referenced?

**docs/SECRETS_REGISTRY.md** — names and purposes only, never values.
Actual secret values are never committed to this repository. As of this
writing there is no standardized remote secret manager — see that file's
`SECRET MANAGER: NOT YET STANDARDIZED` note, which is itself a tracked gap.

## How should a new AI/human resume work safely?

Follow **CLAUDE.md**'s "Session startup" checklist exactly — it exists
precisely for this purpose. In short: read `docs/PROJECT_STATE.json` and
`docs/PROJECT_STATUS.md` first, verify any claim that actually matters for
your task against real source/Git/runtime rather than trusting docs, and
do not modify code until asked. See also **docs/RECOVERY.md** if resuming
from a completely new machine with no prior local state.

## What is the next single strategic priority?

**Durable remote event capture** (a durable cloud event ledger for
runs/sessions/model calls, so new activity is never lost) — see
docs/ROADMAP.md's near-term ordered roadmap, item 2. This
depends on this checkpoint's own remote-Git durability being real first;
see docs/PROJECT_STATE.json's `next_action` for the exact current status.
