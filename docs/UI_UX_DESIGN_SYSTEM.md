# UI/UX Design System

Bounded design-research pass (2026-09-15), grounded in two sources: (1)
established public enterprise design-system principles (IBM Carbon,
Microsoft Fluent 2, Material 3, Apple HIG — information hierarchy,
progressive disclosure, semantic color, density, accessibility), and (2)
direct inspection of this platform's actual current live UI (Customer
App login/overview/admin, Workbench, Dashboard — screenshotted live
during this session, not guessed at). This is a decisions record, not an
essay — it exists so future UI work in this repo is consistent rather
than each surface re-inventing its own look.

**Test for every decision below:** *if every AI reference were removed,
would this still look like a serious product intentionally designed by
an experienced product/design team?* The answer must be yes.

## What the current UI already gets right (keep, don't rebuild)

Direct inspection of the live Customer App (USER and ADMIN views) and the
Workbench found the baseline is already closer to "product" than
"AI-slop" — no gradient hero banners, no glassmorphism, no floating
decorative shapes, no emoji-heavy copy, plain functional cards, real
data, honest empty/loading states already documented in
`docs/UI_AUDIT_OPEN_ITEMS.md`. **The instruction to avoid AI-generated
aesthetics is already substantially satisfied by the existing design —
this document tightens and codifies it, it does not start over.**

Genuine gaps found by direct inspection, worth fixing opportunistically
(not tonight, unless called out in `docs/ACTION_QUEUE.json`):
- Every Customer App card currently gets identical visual weight
  (Overview/Profile/Plan/Preferences/Appointment/Activity all look like
  peers) — real products vary density: identity + plan status deserve
  more visual priority than Preferences.
- The Workbench's dark theme is not shared by the Customer App or
  Dashboard-adjacent surfaces (light) — each surface has its own
  personality by design (see below), but the *underlying scale* (spacing,
  radius, type) should still be the same tokens, not independently
  invented per surface.

## Design tokens (one language, shared across all subsystems)

These are the shared primitives. Per-subsystem "personality" (below)
means different token *values are emphasized*, not a different system.

**Typography scale** (system font stack, no webfont dependency to keep
pages fast): `12 / 14 / 16 / 20 / 28 / 36` px, one weight step (regular
400 / semibold 600) — never more than 2 weights on one page. Line-height
1.5 for body, 1.2 for headings.

**Spacing scale** (8px base, matches Carbon/Fluent convention):
`4 / 8 / 12 / 16 / 24 / 32 / 48` px. Card internal padding: 16-24px.
Section gaps: 32-48px. Never hand-pick an arbitrary pixel value outside
this scale.

**Color — semantic, not decorative:**
- Status: `success` (green), `warning` (amber), `danger` (red), `info`
  (blue), `neutral` (gray) — used for badges/chips (ACTIVE, FAILED,
  PENDING, etc.), never as arbitrary brand color.
- Never color-only state: every status chip carries text, not just a
  color (already true in the live Customer App — `ACTIVE` renders as
  text-in-a-badge, not a bare colored dot).
- One accent color per light surface (the existing blue used for primary
  buttons) — no rainbow gradients, no purple/blue neon combinations.

**Surfaces & elevation:** flat cards with a 1px border (already the
pattern in the live Customer App) over heavy drop-shadows. Reserve real
elevation (shadow) for transient layers only — a modal/drawer/tooltip
that must visually separate from the page behind it — never for
resting-state cards.

**Radius:** one consistent small radius (4-8px) everywhere. Not
"everything is a rounded pill" (the AI-slop tell), not sharp 0px
brutalism either.

**Motion:** motion explains state, never decorates.
- Good: a Workbench stage indicator pulsing while genuinely in progress,
  a drawer/modal open-close transition, a success/failure state
  transition, a loading spinner tied to a real pending request.
- Bad: continuous background animation, floating shapes, decorative
  parallax, animated gradients.
- Respect `prefers-reduced-motion` — disable non-essential transitions
  when set.

## Component patterns (use the right one, not "everything is a card")

Per the master instruction, information density should vary by content,
not be flattened to uniform cards:
- **Summary/stat block** — a single important number + label (e.g. plan
  status, cost-per-verified-change) — not wrapped in a full bordered card
  if it's one line of information.
- **Table** — any list with 3+ comparable rows and sortable/filterable
  columns (Admin's Customer Search already does this correctly).
- **Inline data row** — label/value pairs inside an existing section
  (Overview's Customer ID/Name/Email) — not each field its own card.
- **Drawer/side panel** — for a detail view opened from a list, without
  losing the list's own scroll position (candidate for a future Triage
  Lab / Admin Customer Detail improvement, not required now).
- **Timeline/progress track** — sequential stage state (Workbench
  lifecycle, Triage Lab's Reproduce → Investigate → Diagnose → Fix →
  Verify → Approve steps) — a real, count-driven progress indicator, not
  a decorative animation.
- **Command bar** — a persistent action row for an operational screen
  (Admin search/filter bar) — already correctly used, keep this pattern
  for Triage Lab's scenario picker.

## Per-subsystem personality (one language, different emphasis)

| Surface | Personality | Token emphasis |
|---|---|---|
| **Customer App (USER)** | calm, approachable, plan/identity-first | larger type for identity+plan status, generous spacing, light surface |
| **Customer App (ADMIN)** | dense, operational, searchable | tighter row height, table-first, command bar always visible |
| **Workbench** | engineering workflow, evidence-visible | dark surface (already distinct from Customer App — correct, signals "you are in a tool, not the product"), stage/progress emphasis, monospace for IDs/hashes/diffs |
| **Triage Lab** | incident-response, diagnosis-first | same dark workbench base + a distinct danger/investigation accent (amber, not red — red is reserved for the actual FAILED verdict) for reproduce/investigate steps, explicit human-approval-gate visual treatment (see below) |
| **Dashboard** | executive + engineering intelligence | light surface, data-density higher than Customer App but lower than Admin (narrative sections, not raw tables) |
| **Usage** | analytical, efficiency-focused | tabular/numeric emphasis, sparkline-friendly, ACTUAL/ESTIMATED/UNAVAILABLE labels always visibly distinct (already implemented — keep) |
| **Showcase** | editorial, recruiter-facing front door | lightest information density of any surface — a simple entry point, deep systems live behind it, not in it |

## Human-approval-gate visual treatment (for Triage Lab)

Per the master requirement that human approval for real Git/deploy
actions must be visually unambiguous: a dedicated full-width block,
distinct border color (not the same as a normal card), the literal words
"HUMAN APPROVAL REQUIRED" as a heading (not a subtle icon), two clearly
differentiated buttons (`APPROVE FIX` primary / `REJECT` secondary,
never side-by-side identical-weight buttons), and no auto-advance timer
of any kind — the page must wait indefinitely for a real decision.

## Accessibility (mandatory, not optional polish)

- Every status must be legible without color (text label alongside every
  color-coded chip — audit already confirms this for ACTIVE/FAILED
  badges; extend the same rule to any new Triage Lab verdict chips).
- Visible focus outlines on every interactive element (buttons, links,
  form fields) — never `outline: none` without a replacement.
- Keyboard reachability for every action, including scrollable panels
  (see the open `tabindex="0"` item in `docs/UI_AUDIT_OPEN_ITEMS.md`).
- Real semantic HTML (`<button>`, `<label for>`, `<table>`) over
  `<div onclick>` soup.
- `prefers-reduced-motion` respected everywhere motion is used.

## Copy voice

Real product language, not AI-marketing language:
- Use: "Current Plan", "Appointment Availability", "Paperless Billing",
  "Customer Search", "Production Verification", "Root Cause", "Approve
  Fix" (already the voice used across the live Workbench/Customer App).
- Avoid: "supercharge", "unlock insights", "seamless experience",
  "empower", exclamation-point enthusiasm, emoji in body copy (a single
  emoji as a page's own icon/favicon, as already used, is fine — emoji
  scattered through body text is not).

## What this pass deliberately did NOT do

- Did not redesign any currently-working page from scratch — genuine
  gaps found (see above) are recorded, not silently fixed as scope creep
  during a design-research pass.
- Did not adopt a heavy frontend framework — every current surface is
  server-rendered HTML/CSS/vanilla JS and stays that way; this system is
  expressed as CSS custom properties/utility classes, not a component
  library migration.
- Did not do open-ended web research for hours — this is a bounded pass
  per explicit instruction, grounded in well-established, stable public
  design-system principles (Carbon/Fluent/Material/HIG all publish the
  same core ideas: 8px spacing scales, semantic color, restrained
  elevation, progressive disclosure) rather than a fresh browsing
  session.
