# Design defect register — 2026-09-30

**Source:** the Owner opened the deployed site and said *"None of the pages looks
good in browser. so bad. why is that?"*

**Context that matters:** Sprint 15 had just closed with 67/67 UI guards passing
against this exact production build, plus 15/15 on the acceptance gate and a
measured 28→0 on answer quality. Every one of those numbers is real. **None of
them measures whether a page looks good.** The guards check alignment, font
sizes, a legibility floor and overflow — correctness properties. A page can be
perfectly aligned, perfectly consistent, and still be unpleasant to look at.

Sprint 15's own retro recorded this gap (item 3.7: *"there is no visual
verification in this project, and every defect this sprint was found by eye"*)
and then shipped on green numbers anyway. That is the failure this register
exists to correct.

**Owner's scope decision, 2026-09-30:** keep the light/dark split as it is
(*"leave the theme, fix layout only"* on theme), and do the visual work as a
**proper design pass with screenshot checkpoints**, not a defect patch.

---

## Measured, at 1920×940, against production `deploy-20260929T231340Z-5ddbe74`

| Page | header width | body width | ratio | longest line (chars) | lines >90 | dup links |
|---|---|---|---|---|---|---|
| home | 1136 | 1136 | 1.00 | **113** | 7 | 0 |
| case-study | 710 | — | — | 83 | 0 | 0 |
| workbench | 587 | 1136 | **1.94** | **172** | 3 | 0 |
| triage | 587 | 1136 | **1.94** | **172** | 2 | 0 |
| ask-codebase | 587 | 1136 | **1.94** | **172** | 1 | 0 |
| showcase | 587 | 1136 | **1.94** | **150** | 9 | 0 |
| usage | 587 | 1136 | **1.94** | **172** | 11 | 0 |
| standing-interview | — | — | — | 73 | 0 | 0 |
| dashboard | 587 | 1136 | **1.94** | **172** | **20** | **4** |

---

## DD1 — Line length up to 172 characters · **HIGH, and it is a readability defect, not a taste one**

The readable band is **50–75 characters, 66 optimal**. Dashboard, usage,
workbench, triage and ask-codebase all render paragraphs at **172 characters** —
2.6× the optimum. **53 paragraphs sitewide exceed 90.**

This is why the dashboard reads as a wall of text. Sprint 15 defined
`--prose: 68ch` and applied it to `.tagline`, `.lede` and a handful of named
children — and never to the body text inside panels, which is where most of the
site's prose actually lives.

The two pages with no violations at all (case-study 83, standing-interview 73)
are the two where the prose cap was applied properly. The fix is known and
already half-built.

## DD2 — Every dark page is lopsided · **HIGH**

Header text is **587px** while the content below is **1136px** — a ratio of
**1.94**, on six of nine pages. The top of the page is half the width of the
bottom, so the eye reads a narrow column that abruptly becomes a wide one, with
a large empty area to the right of the header.

Cause: the 68ch prose cap is applied to the header block but the panels below
use the full shell. Both decisions are individually defensible; together they
produce the imbalance.

## DD3 — Navigation reads as body text · **MEDIUM**

The nav sits directly beneath the tagline (and, on usage/dashboard, beneath the
fold-action links too), at a similar size and weight, with no separating
treatment. Three rows of similar-looking text stack up before any content
starts. It is functional and it does not look like navigation.

## DD4 — Duplicate adjacent links on the dashboard · **MEDIUM**

Four instances of the same link text repeated immediately next to itself
(`VIEW EVIDENCE  VIEW EVIDENCE`). Whatever the data reason, it reads as a bug.

## DD5 — Home h1 is 113 characters wide and the page is visually unbalanced · **MEDIUM**

Home is the only page where header and body are both 1136 (ratio 1.00), yet its
longest line is still 113 characters and the top third is heavily left-weighted
with a large empty right side above the proof cards.

## DD6 — Flat visual hierarchy throughout · **MEDIUM**

Thin 1px borders, near-uniform text weight, minimal spacing rhythm, little
contrast between a section label, a heading and body copy. Nothing is wrong
with any single element; there is simply not enough visual difference between
levels for the eye to find structure.

---

## DD7 — The testing gap that let all of this ship · **HIGH**

Sprint 15 added 67 guards and every one passed on these pages. They measure:

- nav aligns with content ✓ (it does — at 587px, next to 1136px content)
- one content column sitewide ✓ (true — and the header is not measured against it)
- one body size ✓
- no text below 12.5px ✓
- something meaningful above the fold ✓

**Not one guard asks about line length, header/body balance, or visual
hierarchy.** The defects in this register are all measurable — the table above
is machine-generated — so the gap is not "design can't be tested". It is that
the guards were written to catch the *previous* round of defects and nothing
extended them to the properties that actually make a page readable.

**Explicitly out of scope, by Owner instruction:** unifying the light/dark
split. Home stays light, the other eight stay dark.

---

# Resolution — Sprint 16

## Measured, production build vs after

| | Before | After |
|---|---|---|
| Longest line | **172 chars** | **71–73** |
| Paragraphs over 90 chars | **53 sitewide** | **0** |
| Header/body ratio | **1.94** on six pages | **1.28–1.31** |
| Duplicate adjacent links | 4 on dashboard | 0 |
| Nav vertical position | 0px on three pages, 206–305 on six | 0–24 on all nine |
| Visual complexity (first screen) | — | **low on all nine** |

## The research this was built on, and what each finding changed

| Finding | Source | What it changed here |
|---|---|---|
| A visual judgement forms in ~50ms | Lindgaard et al., *Behaviour & IT* 25(2) | The first screen is the whole opportunity — nav, title and one real paragraph must all land above the fold |
| **High** visual complexity produces a **worse** first impression than low or medium | Tuch et al., *IJHCS* 2012 | Kept the per-page signatures to **one structural move each**, and measured complexity afterwards to confirm it stayed low. Two moves would have been costume |
| Prototypicality predicts trustworthiness (29–68% of variance) | Tuch et al. 2012; follow-up *IJHCS* 2023 | Nav moved to first on every page. For a portfolio whose whole job is to be believed, structural familiarity outranks any accent choice |
| Colourfulness and complexity together predict appeal | Reinecke et al., CHI 2013 | Accent used on four elements only — heading, section label, focus ring, active nav — never as a large fill |
| Readable line length 50–75, 66 optimal | Long-settled typographic research | `--prose`, tuned empirically to 58ch once the guard could measure real characters rather than estimate from width |

## Identity, and its justification

The Owner's decision was explicit: ignore the one-accent convention, because
eight surfaces is eight chances to look considered, and the variation is itself
part of what the platform demonstrates. Each choice is derived from what the
page does, not applied decoratively:

| Page | Accent | Display face | Why this page |
|---|---|---|---|
| workbench | indigo | Sora | an agent working — geometric, engineered; squared corners and a scan-line hairline |
| triage | amber | IBM Plex Sans | incidents — amber is the universal attention colour; left accent bar |
| ask-codebase | cyan | Space Grotesk | retrieval — a focus glow, surfacing something from a dark corpus |
| showcase | emerald | Outfit | proof — the colour of a passing check; ruled section labels |
| usage | gold | JetBrains Mono | money — tabular figures that align down a column |
| dashboard | blue | Manrope | a control surface — denser, flatter, more visible at once |
| standing-interview | violet | Fraunces | a conversation — editorial serif, the widest breathing room |
| case-study | warm tan | Source Serif 4 | long-form reading — 18px/1.75, editorial standfirst |
| **home** | **unchanged** | **unchanged** | the Owner said its colour and font already look good |

**The discipline that stops this being a ransom note:** the display face varies
per page, the **body face does not**, and spacing, layout and reading measure
are shared. Unique headings, uniform readability.

## Still not covered by any assertion

DD6 (flat visual hierarchy) has no guard and deliberately so — no assertion
catches "this looks unconsidered". It was addressed by spacing scale, type
layers and panel elevation, and verified the only way it can be: by looking at
screenshots of all nine pages.
