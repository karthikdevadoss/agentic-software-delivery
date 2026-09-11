# UI Audit — Open Items

Found during the autonomous UI/UX hardening pass on Learn, Usage/Session
History, Session Detail, and the PDF-book download experience
(2026-09-11). Items here are things this pass deliberately did NOT fix —
either because they need Owner judgment/decision, or because fixing them
would have exceeded this pass's "low-risk, reversible, no feature creep"
mandate. Items actually found and fixed are recorded in docs/LESSONS.md
instead (durable, reusable defects), not duplicated here.

---

## 1. Missing `<meta name="viewport">` on other public pages

- **Issue:** `workbench.html`, `dashboard.html`, `profile.html`, and
  `control-plane.html` have no viewport meta tag — confirmed by direct
  grep across `agent/web/*.html`. Without it, mobile browsers render the
  page at desktop width and zoom out, making any responsive CSS on those
  pages ineffective.
- **Evidence:** `grep -rn viewport agent/web/*.html` before this pass
  found it in zero HTML files; this pass added it to `learn.html` and
  `usage.html` only (the two pages in scope).
- **Severity:** Medium (affects real mobile usability of 3-4 other
  public pages, not the ones this pass covers).
- **Recommended action:** Add the same one-line `<meta name="viewport"
  content="width=device-width, initial-scale=1">` fix to the remaining
  HTML files.
- **Owner decision required?** No — this is a trivial, safe, one-line
  fix per file with no design/product judgment involved. It was left out
  of this pass purely to stay within the explicit scope ("the newly
  implemented" 4 features), not because it's risky.
- **Backlog relationship:** Small, standalone follow-up; not tied to any
  existing P0 item.

## 2. `workbench.js`/`dashboard.js`/`profile` pages not audited for the same defect classes

- **Issue:** This pass only audited Learn/Usage/Session Detail/PDF. The
  same defect classes checked here (focus-visible outlines, responsive
  breakpoints, long-ID truncation, badge-taxonomy conflation) were not
  systematically checked on Workbench, Dashboard, or Profile.
- **Severity:** Low-Medium — those pages predate this task and have
  their own established, separately-reviewed UI history.
- **Recommended action:** A future, explicitly-scoped UI audit pass for
  those three pages, mirroring this one's checklist.
- **Owner decision required?** No, but it's a genuinely separate task
  the Owner may want to prioritize or not.
- **Backlog relationship:** None yet — not an existing P0 item.

## 3. Session-history panel's internal scroll area is not independently keyboard-scrollable by default in every browser

- **Issue:** `.hist-scroll-area` uses `overflow-y: auto` with a fixed
  `max-height`, which is the correct low-risk fix for "the page does not
  become infinitely long" — but a `<div>` with `overflow: auto` is not
  natively in the browser's Tab order unless it receives `tabindex="0"`,
  so a pure-keyboard user (no mouse/trackpad) may not be able to scroll
  it via arrow keys without first clicking inside it.
- **Severity:** Low (a real accessibility nuance, not a functional
  break — mouse/trackpad/touch scrolling all work correctly, and the
  Load More button remains fully keyboard-reachable and functional as an
  alternative way to reach more sessions).
- **Recommended action:** Add `tabindex="0"` and an `aria-label` to
  `#session-history-list` in a future accessibility-focused pass.
- **Owner decision required?** No — flagged here only because a full
  accessibility-framework migration was explicitly out of scope for this
  pass ("do not turn this into a massive accessibility framework
  migration"), not because it needs product judgment.
- **Backlog relationship:** None yet.

## 4. `AI WAITING FOR HUMAN` / `HUMAN ACTIVE TIME` remain UNKNOWN for most session kinds

- **Issue:** Not a UI defect — the UI now presents these honestly
  (color-coded as `UNKNOWN`, per this pass's note-coloring fix), but the
  underlying gap is real: this project's telemetry genuinely cannot
  measure real human-interaction intervals or most AI-waiting-for-human
  windows today.
- **Severity:** N/A (telemetry gap, not a UI bug) — restated here only
  because the audit surfaced it visually and the instructions explicitly
  said not to silently absorb "missing telemetry" discoveries into a UI
  fix.
- **Recommended action:** A future, separate telemetry-capability task
  (not a UI task) would be needed to close this, and would itself
  require product/architecture judgment (e.g., whether a
  PermissionRequest-equivalent event is worth adding).
- **Owner decision required?** Yes — whether/how to invest in capturing
  this is a product/architecture decision, not a UI call.
- **Backlog relationship:** Related to the already-tracked
  `SESSION-ECONOMICS-P0`/`SESSION-QUALITY-P0` items in
  `docs/ACTION_QUEUE.json`, which already note this as an honest,
  evidence-gated limitation rather than claiming it's solved.

## 5. Real browser click-through verification of this pass's own changes has not been performed

- **Issue:** Same limitation as the P0 implementation task before this
  one: no browser-automation tool was available/connected in this
  session (confirmed by direct tool search). All fixes in this pass were
  verified via direct HTTP checks against a local dev server, the real
  `learn.js`/`usage.js` source loaded in a Node `vm` harness against
  realistic fixtures, and careful manual reasoning about the rendered
  HTML/CSS — never an actual browser screenshot or click-through.
- **Severity:** Process gap, not a known defect.
- **Recommended action:** The Owner (or a future session with a browser
  tool) should visually confirm the specific fixes in this pass — badge
  colors, card layout at narrow widths, PDF button loading/error states,
  session summary card — actually look and behave as intended.
- **Owner decision required?** No decision needed, just a visual check
  when convenient.
- **Backlog relationship:** Same open item already tracked against
  `LEARN-WIKI-P0`/`SESSION-HISTORY-P0`/`LEARN-PDF-BOOK-P0` in
  `docs/ACTION_QUEUE.json`.
