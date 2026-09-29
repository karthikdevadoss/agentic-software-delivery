# UI defect register — from the Owner's screenshot review, 2026-09-29

**Source:** `D:\iphone\UI-screenshotswithbugs.docx` — 13 screenshots, **desktop Chrome at 1920×1080**, walking the public navigation.
**Status:** RECORDED ONLY. Nothing fixed, nothing committed, nothing deployed. Awaiting sprint approval.

## Why these reached you despite 240/240 production verification

My matrix tested **1280 / 768 / 390**. I called 1280 "desktop". **1920 — the width you actually use — was never tested.** Every defect below reproduces in Chromium at 1920; none of them needed an iPhone to find. That is a gap in my test design, not in the browser.

Second cause: the alignment check I added during Sprint 14 covered **two pages** (home, case study). `/standing-interview` was never checked, and that is where the worst defect is.

---

## Defects, measured

### D1 — Standing Interview navigation is broken · **SEVERE**
The nav spans the **full 1920px viewport**, sits flush at **x=0** with "Home" clipped against the window edge, while the page content is centred at **x=596**. A 596px disconnect.

**Cause:** in `agent/web/standing-interview.html` the `<nav id="top-nav">` sits *outside* `.si-wrap` (the `max-width:760px; margin:0 auto` container), so it inherits no width constraint and no centring.

**Measured, all pages at 1920:**

| Page | nav x | content x | verdict |
|---|---|---|---|
| **standing-interview** | **0** | **596** | **misaligned by 596px** |
| home | 552 | 552 | ok |
| case-study | 632 | 632 | ok |
| workbench / triage / ask-codebase / showcase / usage / dashboard | 492 | 492 | ok |

### D2 — The whole page jumps sideways as you click the nav · **HIGH**
Three different column widths across the public surface, so every navigation shifts the layout horizontally:

- **936–1000px** — Workbench, Triage, Ask Codebase, Showcase, Usage, Dashboard (content starts x=492)
- **860px** — Home (x=552) → **60px jump** from any dark page
- **700px** — Case study (x=632) → **80px jump** from Home, **140px** from Workbench

### D3 — Home wastes most of the screen · **HIGH** *(Owner-reported)*
| Width | Home column | Empty margin |
|---|---|---|
| 1920 | 860px | **1060px — 55% of the screen** |
| 1440 | 860px | 580px — 40% |
| 1280 | 860px | 420px — 33% |

Case study is worse: **64% empty at 1920**.

### D4 — Header block and panel block are misaligned on the dark pages · **MEDIUM**
The header/nav column does not line up with the panels beneath it:

| Page | nav x | panel x | offset |
|---|---|---|---|
| workbench / triage / ask-codebase / showcase | 492 | 480 | 12px |
| **usage / dashboard** | 492 | **430** | **62px** |

### D5 — Font sizes are inconsistent across pages · **MEDIUM** *(Owner-reported)*
| | Home / Case study | All other pages |
|---|---|---|
| Body | **17px** | **16px** |
| H1 | **44px / 41px** | **26.4px** |

The h1 on Workbench, Triage, Ask Codebase, Showcase, Usage, Standing Interview and Dashboard is **40% smaller** than the home page's, so page titles stop reading as titles.

### D6 — Text below a readable floor · **MEDIUM** *(Owner-reported)*
Smallest text actually rendering on screen:

| Page | smallest | element |
|---|---|---|
| **showcase** | **10.88px** | `sc-live-badge` |
| **dashboard** | **11.2px** | `badge st-ok` |
| **usage** | **11.52px** | `exec-note` |
| case-study | 12px | `small` |
| home | 14px | secondary CTA |

Anything under ~12px is uncomfortable on a 1920 display.

### D7 — Nothing of value above the fold on some pages · **HIGH** *(Owner-reported)*
At 1920×1080, what a visitor sees before scrolling:

| Page | Page height | = screens | First screen carries |
|---|---|---|---|
| **standing-interview** | 1080px | 1.0 | nav + title + one input, then a large empty void |
| workbench | 1141 | 1.1 | title, target app panel |
| triage | 1080 | 1.0 | title, scenario A |
| **home** | 3544 | **3.3** | name, role, lede, separation — proof cards start below the fold |
| **usage** | 5260 | **4.9** | title + one dense jargon heading |
| **showcase** | 5431 | **5.0** | title + START HERE |
| **dashboard** | 12335 | **11.4** | title + status badges |

**Correction to my own first reading (2026-09-29, after measuring at a realistic browser fold):** I first wrote that the home page's proof cards begin below the fold. They do not. At 1920x940 — a real browser viewport after tabs and the address bar take their ~140px — all three cards are fully visible. The measurement that misled me was page *height* (3544px), which says how long the page is, not what a visitor sees first. **Usage is the real failure here**: it shows only a title and one dense jargon heading in the first screen, and it is the only page that fails the above-the-fold guard.

### D8 — Showcase title breaks badly · **MEDIUM**
`Senior Java Backend + AI-Assisted Delivery Transformation — evidence-backed, not a technology badge list` wraps mid-word as "evidence-" / "backed", and mixes a title with an editorial tagline in one h1.

### D9 — Internal vocabulary on recruiter-facing pages · **MEDIUM**
Usage shows raw identifiers to a visitor: `delivery_events`, `event_type=run_usage_summary`, `FAILED/NO_CHANGE_NEEDED/DEPLOYMENT_STATUS_UNKNOWN`, and a heading reading *"WORKBENCH DELIVERY EFFICIENCY (PIPELINE RUNS ONLY — SEE "CLAUDE CODE DEVELOPMENT COST" BELOW FOR A SEPARATE TOTAL)"*. Showcase renders `Last verified 2026-09-29`, internal metadata.

### D10 — Test-design gaps that let all of this through · **HIGH**
1. 1920 was never tested — "desktop" meant 1280.
2. The nav-alignment check covered 2 of 9 pages.
3. No check on font-size consistency or minimum legible size.
4. No check on what is above the fold.
5. No check that the content column is consistent across pages.
6. `docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml` (AEQ-001…029) received **nothing** from Sprint 14 — defects were recorded in commits, the retro and the backlog, but not in the canonical defect ledger.

---

## Out of scope for a UI sprint, recorded here

Your note *"It answers so crazily for some questions"* on Standing Interview is an **answer-quality** issue, not a UI one. It is already covered by the 2026-09-29 SI audit and `BL-142`–`BL-144`, and the sprint contract for Sprint 14 forbade touching SI behaviour. It should stay a separate sprint.

---

# Resolution — Sprint 15 (2026-09-29)

| Defect | Status | What changed | Guard that would now catch it |
|---|---|---|---|
| **D1** Standing Interview nav at x=0, content at x=596 | **FIXED** | nav moved inside `.si-navwrap` sharing the 1200px shell | `nav aligns with content` — now all 9 pages × 5 viewports, was 2 pages |
| **D2** Layout jumps sideways between pages | **FIXED** | one `--shell: 1200px` / `--shell-pad: 2rem` token adopted by every page | `one content column across the whole site` |
| **D3** Home wastes 55% of a 1920 screen | **FIXED** | 860px → 1200px shell, prose capped at 68ch separately | same |
| **D4** Header and panels misaligned (12px / 62px) | **FIXED** | `main` and `header` share `--shell-pad`; `#dash-main` 1100 → `var(--shell)` | same |
| **D5** Body 16 vs 17px, h1 26.4 vs 44px | **FIXED** | 17px body sitewide; `h1: clamp(28px, 2.4vw, 34px)`, home capped 38px | `body size is the same`, `the page title is a title` |
| **D6** Text at 10.88 / 11.2 / 11.52px | **FIXED** | 12.5px floor applied at source in `showcase.css`, plus a named class list in `style.css` | `renders no text below 12px`, per page |
| **D7** Nothing meaningful above the fold | **FIXED (usage)** | plain-English intro + `.fold-actions` link rows on usage and dashboard | `puts something meaningful in the first screen` at 1920×**940** |
| **D8** Showcase title breaks mid-word | **FIXED** | h1 is the role title alone; the editorial line moved into the sentence beneath it; measure capped so it wraps at spaces | — (visual; covered by the h1 checks) |
| **D9** Internal vocabulary on recruiter pages | **FIXED** | `outcome_class` / consumption categories get English labels with the raw value kept beside them; `canonical_source` moved into a `<details>` labelled "Where this number comes from"; ISO dates read as dates; `NOT_PRODUCTION_PROVISIONED` rewritten in prose | — |
| **D10** Test-design gaps | **FIXED** | `e2e/ui-standards.spec.js`, 67 assertions; AEQ-030..032 backfilled; ledger now a named sprint close-out step | the suite itself |

**D7, honestly:** only the Usage failure is fixed. The page-length figures in the table above (dashboard 11.4 screens, showcase 5.0) are unchanged — those pages are long because they carry a lot of evidence, and length is not itself the defect. What is now guaranteed is that the *first* screen of every page carries real content and something to click.

**D9, scope note:** the deep technical vocabulary on the showcase page — `LOWER()/CONCAT()`, `pg_trgm`, `ContractPlanService.enroll()`, `run_in_threadpool`, `agent/risk_policy.py` — was deliberately left alone. That page is evidence written for an engineer reading it, and method names and file paths are the substance, not jargon to be smoothed away. Only identifiers that had leaked into *recruiter-facing prose* were translated, and none was deleted.

## One thing this sprint could not fix

`/standing-interview` declines "describe a technical disagreement and how you resolved it" on every draw. That is a **corpus gap**, not a gate defect: the private books are technical, so retrieval genuinely finds nothing behavioural and the model correctly refuses rather than inventing a story about a disagreement that may not have happened. Loosening the decline gate would be worse than the refusal. Adding behavioural/STAR material to the corpus is the Owner's call on his own career content — the audit parked it as SI-19.
