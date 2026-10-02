# Sprint 18 — Evidence-First Recruiter Proof Platform V1

**Owner review package.** Written 2026-10-02 at the end of an authorized
autonomous work block. Nothing in this sprint was pushed, deployed or published.

> **Continuation state: `NEEDS_OWNER_GOAL_REVIEW`.**
> The engineering is complete and verified. What is not settled is a decision
> only the Owner can make — see §E. The work is deploy-ready locally and
> publication-ready pending that decision.

---

## A. What the sprint actually changed, in one paragraph

The public claims used to be hand-written HTML. A status label, a sentence and a
link, maintained by remembering to. There was no machine link between what the
page said and what the capability registry recorded, so a claim could outlive its
evidence silently — and it already had: four recorded evidence paths pointed at
files that no longer existed at those paths. Now there is one registry, the pages
are generated from it, every claim carries a verification status that cannot
exceed the level actually recorded for that capability, every claim carries its
own limitation beside it, and a build check refuses the whole surface if any of
that stops being true.

---

## B. The evidence architecture

```
docs/PORTFOLIO_CAPABILITIES.yaml      what exists, and how verified      (registry v3, 23 capabilities)
          |                            authority for TRUTH
          v
docs/PUBLIC_PROOF_SURFACE.yaml        what we say in public              (16 public, 7 on the front door)
          |                            authority for PRESENTATION
          |                            cannot exceed the level above it
          v
agent/proof_registry.py               13 structural checks -- refuses the surface
          |
          v
agent/build_proof_surface.py          renders the pages FROM the registry
          |
          v
agent/web/home.html (fenced region)   the front door, 7 strongest claims
agent/web/proof.html  (/proof)        the evidence index + 3 audience routes
```

**Why two files and not one.** `PORTFOLIO_CAPABILITIES.yaml` answers "what exists
and how verified is it" and is consumed by JD matching. `PUBLIC_PROOF_SURFACE.yaml`
answers "what do we say, where does a visitor go, what is the honest boundary."
They cannot contradict each other, because that is mechanically enforced: every
id must exist in the registry, there is one entry per id, and `status_requires`
forbids a public status above the recorded `verification_level`. **A claim cannot
be upgraded by editing the public file — only by doing the work that raises the
verification level in the registry.**

### The whole public status vocabulary — four values

| Status | Shown as | Means |
|---|---|---|
| `LIVE_VERIFIED` | Live | Running now, the visitor can open it |
| `TESTED_VERIFIED` | Tested | Proven by deterministic tests/evidence, not visitor-executable |
| `DOCUMENTED` | Documented | Source/history/case-study evidence, not publicly runnable |
| `EXPERIMENTAL_PAUSED` | Experimental / paused | Research, with its limits stated; not a product |

---

## C. The seven front-door capabilities, exactly as published

| # | Headline | Status | Registry level |
|---|---|---|---|
| 1 | An AI agent that cannot approve its own writes | **Live** | PRODUCTION_VERIFIED |
| 2 | A workflow that survives a crash | **Live** | PRODUCTION_VERIFIED |
| 3 | Retrieval that is measured, not assumed | **Tested** | RUNTIME_VERIFIED |
| 4 | One model boundary, with a kill switch | **Live** | PRODUCTION_VERIFIED |
| 5 | Every step and every model call is recorded | **Live** | PRODUCTION_VERIFIED |
| 6 | A real Java and Spring system underneath | **Live** | PRODUCTION_VERIFIED |
| 7 | An experiment that failed its own test, and was stopped | **Experimental / paused** | TESTED |

Nine more are on `/proof` only (the independent evaluator, the deterministic
static gates, the Standing Interview, the estimation/retro loop, JWT/RBAC,
Flyway/PostgreSQL, downstream resilience, the real-topology tier, and production
verification). Deliberately kept off the first screen: a front door that lists
everything proves nothing, because nothing stands out.

**Claim wording for the six that were already public is carried over verbatim**
from the previously published home page, not rewritten — so publishing this does
not quietly restate claims that were already accepted. The genuinely new text is
the seven limitations and the Deep Consensus entry.

### Deep Consensus, specifically

It appears once, as the seventh front-door item, labelled **Experimental /
paused**, and its limitation says in its own words that the product thesis is
**unproven**, that it demonstrated **zero** genuine false-to-true corrections and
**zero** genuine baseline false claims, and that it must not be read as an
accuracy product or a partial success. Three separate tests assert that it cannot
be relabelled Live, in the registry, on the page, and in the browser. No Deep
Consensus development was resumed; §37 of the brief was not touched.

---

## D. Verification

### Deterministic (blocking)

| Gate | Result |
|---|---|
| `agent/ci_python_tests.py` — release health | **886 tests, 1 failure, 4 skipped** (see E3) |
| `agent/ci_python_tests.py` — quality monitors | 3 tests, **1 known RED**, printed by name, non-blocking |
| `agent/proof_registry.py` | **PASS** — 16 capabilities, 7 front door |
| `agent/build_proof_surface.py --check` | **PASS** — generated pages match the registry |
| `agent/governance_clauses.py` | **PASS** — 18 of 18 required governing clauses present |
| `agent/test_proof_registry.py` | **39 tests**, 21 of them seeded mutations |
| `agent/test_public_leakage.py` | **6 tests**, real public surface clean |
| `agent/test_public_surface_gate.py` | **28 tests** (was 25) |
| `agent/test_governance_clauses.py` | **7 tests**, 4 seeded mutations |

### Browser (Playwright, real Chromium against the local server)

| Suite | Result |
|---|---|
| `home.spec.js` + `nav-consistency` + `link-integrity` | **116 passed, 0 failed** |
| `responsive-invariants` | 2 failed — `showcase` and `usage` scroll horizontally at 390px |
| `third-party-network` | 7 failed — the seven `style.css` pages still request fonts |
| `golden-journey` | passed |

**The 9 failures are expected, named, and each tied to an open Owner decision —
they are not unexplained red.**

- The **7 font failures** are the Sprint 17 spec I carried forward asserting the
  sitewide font removal that E1 says the Owner must decide. `/`,
  `/case-study/durable-agent` and `/proof` all **pass** it. The spec is correct
  and was kept rather than weakened: it will go green the moment E1 is answered
  yes, and it is the thing that will prove it.
- The **2 overflow failures are pre-existing**, not caused here: the production
  before-pack shows `showcase` overflowing at 390px already, and `usage`
  overflows locally because this machine holds hundreds of real session rows.
  `/proof` overflowed too, which **was** mine — found by the capture, fixed, and
  re-measured clean (E4).

One further failure was found during this run and fixed: my own new parse guard
in `home.spec.js` reported 7 status labels where 4 were expected, because the
regex also matched the three audience labels at the same indent. The membership
assertion beside it would have passed with the wrong seven. That guard existing
is the only reason the weaker test was caught.

### Runtime (real HTTP against a real local server)

All public routes 200: `/`, `/proof`, `/workbench`, `/case-study/durable-agent`,
`/usage`, `/ask-codebase`, `/triage`, `/dashboard`, `/standing-interview`,
`/showcase/{slug}`. Private surfaces still 404: `/learn`, `/jd-match`.

**Journeys — 3 of 3 PASS**, evidence in
`docs/evidence/sprint18/journey-verification.json`, harness in the same folder:

| Journey | Page | Questions answerable |
|---|---|---|
| A — recruiter / HR | `/` | 7 / 7 |
| B — AI / agentic hiring manager | `/proof` | 8 / 8 |
| C — backend / architecture interviewer | `/proof` | 5 / 5 |

### Measured, not asserted: third-party requests

Captured on **real production** (before) and **this laptop** (after), at three
viewports:

| Page | Third-party font requests BEFORE | AFTER |
|---|---|---|
| `/` | 1 | **0** |
| `/case-study/durable-agent` | 1 | **0** |
| `/proof` | n/a (404 — new surface) | **0** |

The other seven pages are unchanged at 3 each, deliberately — see E1.

---

## E. Blockers: what needs the Owner, and why it was not guessed

### E1. The remaining Google Fonts dependency on seven pages — `NEEDS_OWNER_GOAL_REVIEW`

**The decision needed:** may the Google Fonts dependency be removed from the
seven pages that load `style.css`?

**Why it was not done.** Investigated properly rather than assumed, and the
answer changed twice:

1. All nine public pages loaded a nine-family Google Fonts stylesheet.
2. No `font-family` rule anywhere names those families **directly** — which
   looked at first like a free removal.
3. It is not free. `agent/web/style.css` really does use them, through
   `--font-body: Inter` / `--font-display: Sora|Outfit|Manrope|Fraunces|...` and
   a `"JetBrains Mono"` monospace stack. Those variables are the **Sprint 16
   per-page visual identity** — the feature the Owner called a USP and the
   Sprint 17 brief reversed, which is still open as
   `docs/OWNER_DECISIONS_PENDING.md` item 1.

So removing the fonts from those seven pages is entangled with a visual decision
that is already waiting for him, and doing it would have decided that question by
side effect.

**What was done instead, and why it is safe.** `home.html` and
`case-study-durable-agent.html` deliberately do **not** load `style.css` (their
own comments say so) and carry **no** rule naming any of the nine families — every
rule on them resolves to a system stack. On those two pages the stylesheet was
downloaded, blocked rendering and sent the visitor's IP to a third party while
changing nothing on screen. Removal there is **visually neutral by construction**,
and the before/after capture confirms 1 → 0 with no other change.

### E2. Publication — `NEEDS_OWNER_GOAL_REVIEW`

Nothing was pushed, deployed or published. The new surface is local only. Review
the screenshots in §F, then decide.

### E3. One blocking test failure that is a test-isolation defect, not a product defect

`test_rag_index.RagIndexTestCase.test_new_file_triggers_only_that_files_embedding`
fails in the full suite (`files_added: 10 != 1`) and **passes 13/13 when the
module runs alone**. Cause: it calls `rag_index.build_index()` against the **real
repository**, so its "exactly one new file" assumption is sensitive to how many
new indexable files the repository has gained since the machine-local index was
last written — and this sprint added about ten. It is a real fragility, it was
exposed rather than introduced, and it is **not** fixed here because fixing it
means changing a test to use a fixture corpus, which is its own change with its
own risk and is outside this mission's scope. **Reported, not hidden:** release
health is 886 tests with **1** failure, and that failure is this one.

The second failure found during the sprint,
`test_verify_change.ExecutedNothingTestCase`, **was** fixed: adopting Sprint 17's
better test-impact map meant `agent/web_server.py` stopped being an uncovered
high-risk path, so the test refused to pass vacuously and said so in its own
assertion message. It was re-pointed at `agent/demo_catalogue.py`, verified
against `tia.analyze` over every tracked file.

### E4. `/proof` horizontal overflow at 390px — FOUND AND FIXED, recorded because the fix is worth keeping

The first capture of the new page reported `scrollWidth 753` against
`clientWidth 390`. Cause: source paths rendered in `<code>` contain no spaces, and
the default `overflow-wrap: normal` refuses to break inside a word, so one
70-character path set the width of the whole document. Fixed with
`overflow-wrap: anywhere` plus `min-width: 0` on the grid/flex children (a
grid child's automatic minimum size is its content, which re-widens the column
regardless of what the text is permitted to do).

---

## F. Screenshots

| Pack | Source | Contents |
|---|---|---|
| `visual-audit-sprint18-before/` | **real production** | 9 pages × 2 screenshot viewports |
| `visual-audit-sprint18-after/` | **this laptop** | 10 pages (adds `/proof`) × 2 viewports |

Desktop 1920×1080 and mobile 390×844, full-page, nothing injected to flatter the
pages. Start with `desktop-1920-home.png` and `desktop-1920-proof.png` in the
after pack; `/proof` has no before image because the page did not exist.

**Not comparable, stated so it is not read as a regression:** `/usage` and
`/dashboard` heights differ hugely between packs because this machine holds
hundreds of real session rows and production holds very few. Every other page's
height is content-determined and directly comparable.

**Aesthetic approval was not made here.** The new page follows the existing
recruiter-facing light direction (same tokens, same shell, same nav) rather than
introducing a visual direction. Whether it looks right is the Owner's call.

---

## G. Sprint 17: what was reused and what was deliberately not

Sprint 17 is **already pushed** to `origin/sprint17-recruiter-ux-testing` —
contrary to the state document, which recorded it as local-only. Corrected here.

**Reused** (objectively verifiable, no visual dependency):

- the release-health / quality-monitor separation in `ci_python_tests.py`, which
  is why a stochastic model answer no longer sets the exit code
- `agent/select_tests.py`, `agent/paid_test_guard.py`, `agent/release_health.py`,
  `agent/build_testing_matrix.py`, `agent/network_inventory.py`,
  `agent/first_screen_review.py` and their tests
- the completed test-impact map (`test_impact_analysis.py`), which also closed a
  pre-existing drift failure
- four whole-surface browser specs: `third-party-network`,
  `responsive-invariants`, `copy-contract`, `visual-regression`
- `e2e/capture-pack.js`, used to produce §F

**Deliberately not reused:** every `agent/web/*.html` and `*.css` change, and the
16 visual-regression baseline PNGs — those encode the visual direction the Owner
has not approved. The `visual-regression` spec was taken **without** its
baselines, so if it is ever enabled it baselines the current design, not Sprint
17's.

Integration stayed well inside its budget. `STOPPED_BY_RULE:
SPRINT17_INTEGRATION_BUDGET_EXCEEDED` was not reached.

---

## H. Git

| | |
|---|---|
| Starting branch | `deep-consensus-sprint5-typed-claims` @ `66fcdb7` |
| Working branch | `sprint18-evidence-first-proof`, branched from `origin/master` @ `c59ae21` |
| Pushed | **NO** |
| Deployed | **NO** |
| Published | **NO** |
| Deep Consensus frozen evidence | **unchanged** — nothing under `docs/evidence/deep-consensus-*` was modified; it was copied forward, never edited |
| Deep Consensus branch | **unchanged** — `deep-consensus-sprint5-typed-claims` still at `66fcdb7` |
| Sprint 17 branch | **unchanged** — still at `da8113a`, identical to its remote |
| `master` | **unchanged** |
| History rewritten | **NO**. No force-push, no reset, no branch deleted |

**Why the branch was based on `origin/master` and not on the Deep Consensus
branch:** the DC branch has Sprint 17 as an ancestor, so building on it would
have been the wholesale Sprint 17 merge the brief forbids. The **documentation
and evidence layer** (75 files, including the Deep Consensus closure record and
the frozen evidence packs) was copied forward to the new branch so nothing was
lost; no code, HTML or CSS came with it.

---

## I. The minimum the Owner needs to do

1. **Look at two images** — `visual-audit-sprint18-after/desktop-1920-proof.png`
   and `desktop-1920-home.png`. Approve, request changes, or reject.
2. **Answer E1** — may the Google Fonts dependency go from the seven
   `style.css` pages? This is the same decision as
   `OWNER_DECISIONS_PENDING.md` item 1 and should be answered together with it.
3. **Decide E2** — push and deploy, or hold.

Nothing else is required, and no next sprint is proposed.
