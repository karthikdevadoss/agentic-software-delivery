# First-screen review — Sprint 17

**GENERATED FILE.** Produced by `python agent/first_screen_review.py` from the
two real capture manifests. Do not hand-edit: re-run it after re-taking either
pack, or the tables and the screenshots will disagree about what was measured.

## What the Owner is being asked to do

Look at the screenshots and say whether the pages look good. That is the one
question this document deliberately does not answer, and the one question that
matters. Sprint 15 shipped 67 green UI guards on pages you opened and disliked;
Sprint 16 shipped 86. Every guard was right about what it measured, and not one
of them measured whether a page is pleasant to look at. Nothing in Sprint 17
changes that, and this session does not certify it.

## How the two packs were produced

| | BEFORE | AFTER |
|---|---|---|
| Base URL | `https://agentic-platform-backend-production.up.railway.app` | `http://127.0.0.1:8420` |
| Captured (UTC) | 2026-09-30T09:21:21.571Z | 2026-09-30T10:32:04.683Z |
| Folder | `visual-audit-sprint17-before/` | `visual-audit-sprint17-after/` |
| Records | 27 | 27 |
| Screenshots | 18 | 18 |
| Model calls | 0 | 0 |

Interaction, both packs: GET/render only. No click, type, submit, auth or model-backed control was touched.

### One thing that is NOT comparable between the packs, stated up front

BEFORE is **production**; AFTER is **this laptop**. For every page whose length
is fixed by its content that makes no difference. For `/usage` and `/dashboard`
it makes a large one, because both render real accumulated history and the two
environments hold very different amounts of it:

| Page | BEFORE (production) | AFTER (this laptop) | Why |
|---|---|---|---|
| `/usage` desktop height | 6759px | 69767px | real session/history rows, not a layout change |
| `/dashboard` desktop height | 15810px | 16853px | real session/history rows, not a layout change |

Measured directly: `/usage` renders **2** session rows against production and
**511** against this machine. The page is not ten times longer because anything
changed; it is ten times longer because this laptop has a year of its own
development history in it. Read those two heights as environment, not as
regression.

## Per-surface measurements

`overflow` is `document.documentElement.scrollWidth > clientWidth + 1`.
`primary Y` is the document-space Y of the first visible, interactive,
non-navigation control -- the thing a recruiter would click. `3p fonts` counts
real requests to a third-party font host on load.

### `/`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-home.png` | `desktop-1920-home.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → 455 | 0 → 0 | 1 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → 455 | 0 → 0 | 1 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-home.png` | `mobile-390-home.png` | 200 → 200 | no (390/390) → no (390/390) | not detected → 606 | 0 → 0 | 1 → 0 | 0 → 0 |

### `/workbench`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-workbench.png` | `desktop-1920-workbench.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | 988 → 641 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | 988 → 641 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-workbench.png` | `mobile-390-workbench.png` | 200 → 200 | no (390/390) → no (390/390) | 1180 → 799 | 0 → 0 | 3 → 0 | 0 → 0 |

### `/triage`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-triage.png` | `desktop-1920-triage.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | 713 → 760 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | 713 → 760 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-triage.png` | `mobile-390-triage.png` | 200 → 200 | no (390/390) → no (390/390) | 939 → 898 | 0 → 0 | 3 → 0 | 0 → 0 |

### `/ask-codebase`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-ask-codebase.png` | `desktop-1920-ask-codebase.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | 812 → 550 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | 812 → 550 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-ask-codebase.png` | `mobile-390-ask-codebase.png` | 200 → 200 | no (390/390) → no (390/390) | 1044 → 588 | 0 → 0 | 3 → 0 | 0 → 0 |

### `/showcase/senior-java-ai-transformation`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-showcase.png` | `desktop-1920-showcase.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | 964 → 602 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | 964 → 602 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-showcase.png` | `mobile-390-showcase.png` | 200 → 200 | YES (435/390) → no (390/390) | 1343 → 784 | 0 → 0 | 3 → 0 | 0 → 0 |

### `/usage`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-usage.png` | `desktop-1920-usage.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | 3190 → 5760 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | 3190 → 5760 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-usage.png` | `mobile-390-usage.png` | 200 → 200 | no (390/390) → no (390/390) | 5849 → 10078 | 0 → 0 | 3 → 0 | 0 → 0 |

### `/standing-interview`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-standing-interview.png` | `desktop-1920-standing-interview.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → 187 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → 187 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-standing-interview.png` | `mobile-390-standing-interview.png` | 200 → 200 | no (390/390) → no (390/390) | not detected → 220 | 0 → 0 | 3 → 0 | 0 → 0 |

### `/case-study/durable-agent`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-case-study.png` | `desktop-1920-case-study.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → not detected | 0 → 0 | 1 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → not detected | 0 → 0 | 1 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-case-study.png` | `mobile-390-case-study.png` | 200 → 200 | no (390/390) → no (390/390) | not detected → not detected | 0 → 0 | 1 → 0 | 0 → 0 |

### `/dashboard`

| Viewport | BEFORE file | AFTER file | HTTP | overflow B→A | primary Y B→A | console errors B→A | 3p fonts B→A | trackers B→A |
|---|---|---|---|---|---|---|---|---|
| desktop-1920 | `desktop-1920-dashboard.png` | `desktop-1920-dashboard.png` | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → 887 | 0 → 0 | 3 → 0 | 0 → 0 |
| firstscreen-1920x940 | — | — | 200 → 200 | no (1920/1920) → no (1920/1920) | not detected → 887 | 0 → 0 | 3 → 0 | 0 → 0 |
| mobile-390 | `mobile-390-dashboard.png` | `mobile-390-dashboard.png` | 200 → 200 | no (390/390) → no (390/390) | not detected → 1530 | 0 → 0 | 3 → 0 | 0 → 0 |

## Totals across all records

| Measurement | BEFORE | AFTER |
|---|---|---|
| Records with horizontal overflow | 1 | 0 |
| Third-party font requests | 69 | 0 |
| Tracker/analytics requests | 0 | 0 |
| Other third-party requests | 0 | 0 |
| Console errors | 0 | 0 |
| Uncaught page errors | 0 | 0 |
| Non-200 responses | 0 | 0 |

## Primary control against the brief's 700–800px band

The brief asked that, for an interactive recruiter destination, the primary next
action sit within roughly the first 700–800 desktop pixels. This table reports
the measurement and nothing else; where a page is over, it is shown as over.

| Page | BEFORE | AFTER | Within 800px? |
|---|---|---|---|
| `home` | not detected | 455 | yes |
| `workbench` | 988 | 641 | yes |
| `triage` | 713 | 760 | yes |
| `ask-codebase` | 812 | 550 | yes |
| `showcase` | 964 | 602 | yes |
| `usage` | 3190 | 5760 | NO |
| `standing-interview` | not detected | 187 | yes |
| `case-study` | not detected | not detected | n/a |
| `dashboard` | not detected | 887 | NO |

Two entries need their own explanation rather than being left to look like gaps:

- **`usage`** is a report, not an interactive destination. Its first *control* is
  a LOAD MORE button far down the page, so this measurement answers the wrong
  question for it. The right one is where the numbers are: measured separately,
  its four cost metrics sit at y=586 and its not-NRG scope sentence at y=219,
  both inside the first screen.
- **`case-study`** has no primary action by design -- it is a document to read.
  It also has no `<main>` landmark, which is a real screen-reader defect
  independent of this sprint and is recorded as backlog rather than fixed here.

## Files

- BEFORE pack: `visual-audit-sprint17-before/` (production, read-only)
- AFTER pack: `visual-audit-sprint17-after/` (local sprint branch)
- Approval-story audit: `docs/SPRINT17_APPROVAL_STORY.md`
- Design lock, including the Sprint 16 reversal: `docs/DESIGN.md`
- Testing architecture: `docs/TESTING.md`
- Decisions waiting on the Owner: `docs/OWNER_DECISIONS_PENDING.md`

