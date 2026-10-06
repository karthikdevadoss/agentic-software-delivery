# Public surface checklist (BL-100, scoped, Sprint 27)

A repeatable human/agent audit checklist for every real public surface this
project serves: purpose + 3-5 concrete checks per page. This is a **read-
only audit document**, not a new automated test suite — most checks below
are already covered somewhere in `agent/test_public_surface_gate.py` and
friends; this doc exists so a human (or an agent without time to read the
whole test suite) can sweep the real site in a browser and know what
"right" looks like per page, in one place.

**Scope note (honest, since the backlog item that requested this predates
today's nav changes):** `docs/BACKLOG.json`'s BL-100 was written 2026-09-29
and names "Workbench, customer app, Triage a/b/c, Usage, Dashboard, Ask
Codebase and Role Showcase." The real public-surface list has changed since
(Automation Sprint 4, 2026-10-06 — the same day as this sprint): Dashboard,
Usage and Showcase left the top nav in favour of "For Recruiters" and
"Interviewer Brief", though all three stay reachable by direct link. This
checklist reflects **real routes read from `agent/web_server.py` today**,
not the stale 2026-09-29 list, per this project's own evidence-precedence
rule (real repo state beats an older committed document).

**Live-browser sweep:** not run this session (scoped to the checklist
itself, per this task's own skip condition for a missing production base
URL/credentials or Owner design choice) -- no Playwright pass, no
rendered-content assertions. A cheap real check WAS run: a direct `curl`
against all 14 real GET routes below returned HTTP 200 on every one,
2026-10-06, against the live Railway production host. That confirms the
routes are up; it does not confirm page content is correct, which is what
the per-page checks below (and the existing test suite they cite) are for.

---

## Home — `/`
**Purpose:** The entry point; identifies the Owner, states the real scope
of what this platform is (and isn't), and routes a recruiter to the
strongest proof first.
- [ ] HTTP 200, title and `<h1>Karthikeyan Devadoss</h1>` present.
- [ ] Exactly 3 proof cards and 6 evidence rows (asserted today by
  `test_public_surface_gate.py::HomePageStructureTestCase`).
- [ ] No forbidden positive claim (overclaiming scale/production-readiness) —
  asserted by `ForbiddenClaimTestCase`.
- [ ] Every internal link resolves to a registered route, no dead links.
- [ ] Footer cookie wording and identity line are exact, not paraphrased.

## Workbench — `/workbench`
**Purpose:** Submit a real requirement and watch it move through the
deterministic eligibility, context-retrieval, LLM-analysis, compile/test,
commit and deploy pipeline live, stage by stage.
- [ ] HTTP 200, tagline matches the real pipeline description (no
  mention of a step the code doesn't actually run).
- [ ] Submitting a small, safe requirement produces a real run id and a
  streaming event sequence, not a canned response.
- [ ] A request classified HIGH/CRITICAL shows an Owner-authorization gate
  rather than auto-deploying.
- [ ] Nav renders the current canonical destination set (`agent/web/nav.js`).

## Triage — `/triage`, `/triage/scenario-b`, `/triage/scenario-c`, `/triage/evidence`
**Purpose:** Reproduce a real, contained defect, get an AI diagnosis and a
real patch with real tests, gated by a human-approval step the AI cannot
bypass; `/triage/evidence` states what's proven per scenario and what
isn't, honestly, with no invented accuracy score.
- [ ] All three scenario pages return HTTP 200 and share the same tagline
  wording (reproduction → diagnosis → patch → tests → human gate).
- [ ] `/triage/evidence` names, per scenario, which real tests ran and
  explicitly states no labelled-diagnosis accuracy score exists (it must
  not invent one).
- [ ] The approve/promote step is never reachable without the explicit
  human-approval action having fired first.
- [ ] Reset works and returns the scenario to its real starting defect.

## Ask the Codebase — `/ask-codebase`, `/ask-codebase/examples`
**Purpose:** Real, cited semantic retrieval over a curated slice of this
repo's own source — zero LLM calls, no answer synthesis, honest "no
evidence found" when nothing relevant is indexed.
- [ ] A real question returns evidence with a real similarity score and a
  working source link — spot-checked this session: `agent/
  test_ask_codebase.py`'s structural/security tests pass locally (46/46,
  see this sprint's T6 commit).
- [ ] The new "How good is this, really?" panel (T6, this sprint) shows a
  live Recall@3/MRR number matching `/eval`, not a hardcoded one.
- [ ] `/ask-codebase/examples` matches the latest `publish_ask_codebase_examples.py`
  output (hashed, per `test_publish_ask_codebase_examples.py`).
- [ ] An adversarial query never returns a path outside the curated corpus.

## For Recruiters — `/recruiters`
**Purpose:** The one page built from what real job postings actually ask
for, with a direct link to where each claim can be checked — this is the
canonical recruiter-facing landing page as of Automation Sprint 4.
- [ ] HTTP 200; renders client-side from `/recruiters.json` (per
  `recruiters.html`'s own noscript fallback — confirm JS rendering works,
  not just the empty shell).
- [ ] Every link classification (internal route vs. external vs. quote)
  passes `test_publish_recruiters_page.py`'s existing checks.
- [ ] No claim on this page is unverifiable against `recruiters_source.yaml`.

## Interviewer Brief — `/interviewer`
**Purpose:** A technical-interviewer-facing (post-HR) brief with live
proof links to poke at, distinct from the recruiter-facing `/recruiters`.
- [ ] HTTP 200, identifies the Owner by name, "Live proof to poke at"
  section links resolve.
- [ ] Nav/claims match `test_interviewer_page.py`'s existing assertions
  (no invented claims, proof links real).

## Standing Interview — `/standing-interview`
**Purpose:** Answer real interview questions as the candidate, grounded
only in private recorded material; off-book/world-knowledge/private
questions refuse rather than guess.
- [ ] Gated correctly: the nav link only appears when
  `/api/standing-interview/status` reports a loaded corpus (fail-closed
  if the check errors — `nav.js`'s `requiresEndpoint` mechanism).
- [ ] A grounded question returns a first-person answer with no
  unsolicited negative beyond what the question asked about.
- [ ] An off-book/private-topic question declines rather than inventing
  an answer (deterministic gate, not a model's judgment call).
- [ ] The Dissatisfied button records a real row in the Owner's review
  queue (`python agent/si_review.py`).

## Dashboard — `/dashboard` (deep link only, not in top nav)
**Purpose:** What this system actually does, actually proven — real
values only, unavailable data labelled, never invented.
- [ ] HTTP 200 directly; reachable as a deep link from Usage even though
  it's not in the canonical nav.
- [ ] Every capability shown links to real evidence; no placeholder/dead
  link (`DeadLinkAndPlaceholderTestCase`).
- [ ] Verification-state counts shown match `docs/PROJECT_STATE.json`'s
  real counts at the commit the page reports.

## Usage — `/usage`, `/usage/session/{id}`
**Purpose:** How human + AI resources were actually used to produce
verified value — real values only, unavailable data labelled, never
invented.
- [ ] HTTP 200; a real session id renders that session's real ledger
  events, not a mock.
- [ ] Cost/token figures are labelled ACTUAL vs ESTIMATED, never
  presented as one undifferentiated number.
- [ ] (T10, this sprint, not yet built) a single run's step-by-step view
  from correlated ledger events, honestly labelling UNKNOWN gaps and
  never calling itself "tracing."

## Role Showcase — `/showcase/{slug}` (deep link only, not in top nav)
**Purpose:** A per-role evidence page: every claim links to a real run,
not a technology-badge list.
- [ ] `/showcase/senior-java-ai-transformation` resolves all selected
  capabilities with zero `unresolved_capability_ids`/
  `unresolved_requirement_texts` (checked this session, see T7 commit).
- [ ] Every evidence link classification passes
  `ShowcaseLinkIntegrityTestCase`.
- [ ] `last_verified` is not older than the latest commit touching
  showcase content (`ShowcaseFreshnessTestCase`).

## Retrieval Eval — `/eval` (deep link only, not in top nav; linked from `/ask-codebase`)
**Purpose:** Shows the RAG retrieval layer's measured quality against a
hand-labelled question set, with a written threshold and the real CI gate
status — explained in plain English, not just numbers.
- [ ] HTTP 200; renders `eval-results.json` exactly as published, no
  score computed client-side beyond display formatting.
- [ ] CI gate status section honestly reports when the gate did NOT run
  on the latest master CI run, and why.
- [ ] Every retrieval case (hit/miss) is listed, not just the aggregate
  score.

## Case Study — `/case-study/durable-agent`
**Purpose:** One real incident told end-to-end — what happens when the
machine dies mid-change to an AI-written patch.
- [ ] HTTP 200; keeps an explicit, uncut "honest limits" section
  (`test_case_study_keeps_an_honest_limits_section`).
- [ ] No forbidden positive claim beyond what's actually proven.

## Customer App (separately deployed Java Spring Boot backend)
**Purpose:** The real target application the platform does engineering
work ON — not part of the agentic delivery platform itself.
- [ ] A visible way back to the portfolio from the Customer App (Sprint
  14 finding, `CustomerAppReturnPathTestCase`).
- [ ] Auth/demo-credential claims published anywhere on this platform
  match the real Customer App auth code (BL-102, this sprint's T14).

---

## Explicitly excluded (owner-gated, not genuinely public)

- `/control-plane` — internal human-approval tool; 404s without the
  owner token or `PRIVATE_SURFACES_ENABLED`.
- `/applications` and `/applications.json` — Owner-facing Applications
  Review; 404s without the correct `?k=` token.
- `/learn`, `/jd-match` — Owner decision (Sprint 14): implementation and
  tests preserved, public routes intentionally 404 in production.

## Maintaining this checklist

Re-derive the route list from `agent/web_server.py`'s `Route(...)` entries
(grep for `methods=\["GET"\]`, exclude `/api/`) whenever nav or routing
changes meaningfully — this list is a snapshot of 2026-10-06's real
routes, not a live-generated artifact, and will drift the same way the
2026-09-29 BL-100 description already has.
