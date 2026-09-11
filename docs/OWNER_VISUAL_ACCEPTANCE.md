# Owner Visual Acceptance — Learn / Usage / PDF

Everything below has already been verified via live HTTP/content checks against
production (`https://agentic-platform-backend-production.up.railway.app`). What's
missing is a real human/browser look — no browser-automation tool was available
this session. This is a short, practical checklist for that pass, not a full
spec re-read.

## LEARN

**Click path:**
`/learn` → click **System Design** → click **Databases** → click
**Connection Pooling** → click **HikariCP** (a related-topic chip)

**What should visually appear:**
- Landing page: a grid of domain cards (not one giant list of 268 cards), a
  search box, an experience-classification **legend** with 4 colored pills, and
  a **DOWNLOAD COMPLETE BOOK (PDF)** panel.
- Each domain card should say **DOMAIN** and show a topic count.
- Inside System Design → Databases: child cards should show either "N
  sub-topics ›" or "leaf topic" — so you can tell what clicking does before
  clicking.
- Connection Pooling's page: breadcrumb (`Learn / System Design / Databases /
  Connection Pooling`) + a "← Back to Databases" link above it, a green
  **Current Project Experience** badge, then WHAT/WHY/HOW sections, then a
  Related Topics chip for HikariCP.
- Click Back (browser button) — should return you to Databases, not reload
  from scratch.
- Resize the window narrow (phone-width) — the topic grid should collapse to
  one column, not overflow sideways.

## USAGE

**Sessions to inspect:**
1. **One current/today session** — any `workbench_run` card from today.
2. **One older session** — scroll or click **Load More** in Session History
   until you reach Sep 9 or Sep 10, open any session there.

**Fields to inspect on each:**
- Provenance badge (green "LIVE CAPTURED" or amber "PARTIAL RECONSTRUCTION")
  is a colored pill, not plain text.
- Top of the session detail page: one summary card showing goal, status,
  start→end, wall time, tokens, cost, quality %, value — all before you have
  to expand anything.
- Timing section: AI active time / AI waiting for human / human active time —
  each UNKNOWN value should look intentional (muted, italic), not like a
  missing-data bug. A DERIVED value should look distinctly amber.
- Quality section: a session with real captured tokens/cost should show
  HIGH_CONFIDENCE (green); a session with nothing captured (e.g. a
  NO_CHANGE_NEEDED run) should show a LOW coverage %, not a fake 100%.
- Try Load More a few times — confirm genuinely older sessions keep arriving
  and the list doesn't freeze or duplicate.

## PDF

**Button:** on `/learn`, the **⬇ DOWNLOAD COMPLETE BOOK (PDF)** button
(clearly labeled PDF, not a generic "Download").

**What to inspect inside the book:**
- Title page: book title, generated timestamp, git commit, topic counts, and
  the experience-classification disclaimer.
- Table of Contents with real page numbers.
- System Design → Databases → Connection Pooling appears at the right nesting
  depth with WHAT/WHY/HOW content.
- At least one "Development Steps" section and one "Interview Preparation"
  section, both readable (not clipped/overflowing).
- Click the button twice quickly — should not double-download or error; button
  text should briefly say "Preparing PDF…" then return to normal.

## KNOWN LIMITATIONS (still needs a human, not a bug)

- No browser-automation tool was available this session — every fix above was
  verified via direct HTTP/content checks and a Node harness against the real
  frontend source, never an actual rendered screenshot.
- `AI WAITING FOR HUMAN` and `HUMAN ACTIVE TIME` are honestly `UNKNOWN` for
  almost every session — this project's telemetry genuinely can't measure
  those yet (not a UI bug; see `docs/UI_AUDIT_OPEN_ITEMS.md` item 4).
- Workbench/Dashboard/Profile pages were not part of this UI-hardening pass
  (e.g. they still lack a `<meta viewport>` tag) — see
  `docs/UI_AUDIT_OPEN_ITEMS.md` item 1.
