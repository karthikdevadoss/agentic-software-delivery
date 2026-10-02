# The design lock

Sprint 17, BL-D, 2026-09-30. Written **before** any CSS was touched, which is the
point — Sprints 15 and 16 both changed appearance first and described the system
afterwards, and both produced a result the Owner rejected.

This file is short on purpose. A design system nobody can hold in their head is
not a system, it is a second thing to drift from.

---

## THIS SPRINT REVERSES A SPRINT 16 DECISION. READ THIS FIRST.

Sprint 16 gave each of the eight non-home pages **its own accent colour and its
own display typeface**, and the Owner called that variation *a USP of the
platform*. That decision is recorded in `docs/PROJECT_STATE.json`'s handoff as a
standing visual decision not to be undone without him saying so.

Sprint 17's brief, written by the Owner the same week, says the opposite, in four
separate places:

> Use a maximum of TWO BRAND typography families. […] Google Fonts CDN must be
> removed. […] Do not restore per-page display fonts. […] ONE engineering-tool
> accent system. Do not assign each tool its own brand color.

Under this project's evidence-precedence rule the Owner's explicit statement in
the current session outranks a committed state document, so Sprint 17's brief
wins and the per-page identities are gone. **I am flagging it rather than
implementing it quietly, because a decision he described as a differentiator has
been removed, and he should find that out from this paragraph and not from a
screenshot.** Also recorded in `docs/OWNER_DECISIONS_PENDING.md`. If the reversal
was not intended, the Sprint 16 block is a contiguous, clearly-commented section
of `agent/web/style.css` in commit `a182be1` and restoring it is a revert, not a
rebuild.

What survived from Sprint 16: the readable line-length work (50–75 characters),
the light/dark split, and home being left alone.

---

## Typography

**Two brand families. Both are already on the reader's machine.**

| Role | Stack | Used for |
|---|---|---|
| Brand sans | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` | Everything, on every page, light and dark |
| Brand serif | `ui-serif, Georgia, "Times New Roman", serif` | Case Study long-form prose only |
| Utility mono | `ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace` | Code, diffs, hashes, run IDs, numeric telemetry — **never** as a page's identity |

`--font-body` and `--font-display` remain as CSS variables and now resolve to the
same brand sans everywhere. They are kept rather than deleted so a future
deliberate change has one place to happen.

**Zero third-party font requests.** No `fonts.googleapis.com`, no
`fonts.gstatic.com`, no `@font-face` pointing off-origin. Nine `<link>` triplets
are removed from nine pages. Asserted, not promised, by
`e2e/third-party-network.spec.js`.

Three reasons, in the order they actually matter:

1. **Home never used any of it.** Home's body font has been a system stack since
   Sprint 14. It was loading nine families and rendering none of them — the
   single clearest piece of evidence that the font loading was decorative rather
   than load-bearing.
2. A recruiter on a slow connection saw a flash of unstyled text before nine
   families arrived from a third party. A system stack paints on the first frame.
3. A German recruiter's browser was making requests to Google on page load. That
   is a GDPR conversation nobody needs to have about a portfolio site.

**Honest trade-off, stated rather than glossed.** System stacks are not identical
across platforms — Segoe UI on Windows, SF on macOS, Roboto on Android. The page
will look slightly different on different machines. That is the cost. It is worth
paying because the alternative on this site was not "one consistent custom face",
it was nine faces, one per page, which was *less* consistent than the platform
variation.

---

## Spacing

**The existing scale, unchanged.** `agent/web/style.css` already has a working
rhythm and no new scale is introduced. Inventing a second one is how a codebase
ends up with two competing systems and a reader who cannot tell which is
authoritative.

---

## Accent

**One engineering-tool accent: `--accent: #5b93ff`.**

This is not a new colour. It is the value `:root` in `style.css` has always
carried; Sprint 16 layered seven per-page overrides on top of it. Removing the
overrides returns to a colour that was already the system default, so this is a
deletion rather than a redesign.

Home and Case Study keep the light portfolio palette (`--accent: #1f4d3d`, a deep
green). That is deliberate and is not a third accent system: it is the
**portfolio mode's** accent, and the two modes are described below.

Accent appears in exactly four places and nowhere else:

- the `.sub` line in an `h1`
- a panel's own heading
- `:focus-visible` outlines
- the current item in the navigation

A colour that appears everywhere signals nothing.

---

## Shared chrome

Every public page shares, with no per-page exceptions:

- **navigation geometry** — rendered by `agent/web/nav.js`, one source
- **header logic** — `h1` plus an optional `.sub`, same scale everywhere
- **button hierarchy** — one primary, any number of secondaries, one tertiary
  text link; never two primaries on a screen
- **corner radius** — 6px controls, 10px cards. Two values, no others
- **spacing rhythm** — the existing scale
- **focus states** — `2px solid var(--accent)` with `2px` offset, on every
  interactive element, in both modes
- **body typography** — the brand sans, one size, one line height per mode

---

## The two modes

| Mode | Pages | Ground |
|---|---|---|
| **Recruiter / portfolio** — light | Home, Case Study | `#fbfaf8` paper, `#14161a` ink |
| **Engineering lab** — dark | Workbench, Triage, Ask Codebase, Showcase, Usage, Standing Interview (and Dashboard, which is not in primary nav) | `#0b0d12` ground, one accent |

The difference must read as **portfolio versus live engineering surface** — the
same product, two rooms. It must not read as two websites. What makes them one
family: identical navigation geometry, identical type, identical spacing,
identical button hierarchy, identical focus treatment. Only the ground and the
accent change.

Dashboard is not redesigned. It stays out of primary public navigation and remains
reachable by URL as deep technical evidence.

---

## First-screen acceptance

Measured at **1920×1080**, **1920×940** (a real laptop, where browser chrome eats
~140px) and **390×844**.

For an interactive recruiter destination, the primary next action should sit
within roughly the **first 700–800 desktop pixels**.

**Not achieved by shrinking everything.** Reducing type and padding until things
fit produces a cramped page that scores well and reads badly — and the measured
cause of Sprint 16's rejection was a *readability* number, not a fit number.
The legitimate moves are: put the interaction first and the explanation after it;
compress status detail to one line; and give supporting material progressive
disclosure instead of laying it all out at equal weight.

**Measured on production before any change** (`visual-audit-sprint17-before/manifest.json`),
which is what makes this a target rather than an aspiration:

| Page | Primary control Y, desktop | Verdict against 700–800 |
|---|---|---|
| Workbench | 988 | over |
| Showcase | 964 | over |
| Ask Codebase | 812 | marginal |
| Triage | 713 | within |
| Usage | **3190** | far over |
| Home, Standing Interview, Case Study, Dashboard | not detected | see below |

"Not detected" is itself a finding, not a measurement gap: those pages have no
`<main>` landmark at all, so the measurement had nothing to scope to. That is a
real screen-reader defect independent of this sprint's aesthetics.

---

## What this document does not do

It does not say whether the result looks good. Nothing in here, and nothing in
any guard this sprint adds, measures that. Sprint 15 shipped 67 green guards on
pages the Owner opened and disliked; Sprint 16 shipped 86. Both were right about
what they measured and silent about what mattered.

**The Owner performs final aesthetic acceptance.** This session does not, at any
point, certify that a page looks good.
