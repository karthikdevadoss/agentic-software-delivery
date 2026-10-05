# Decisions waiting on the Owner

Sprint 17, 2026-09-30. Nothing here blocked the sprint — each item was recorded
and work continued on something else, which is what the Owner-away protocol asks
for.

Ordered by how much it matters, not by when it came up.

---

## 1. The per-page visual identity is gone. That was your Sprint 16 USP.

**Status:** DONE, and reversible in one revert. Flagging it rather than burying it.

**What happened.** Sprint 16 gave each of the eight non-home pages its own accent
colour and its own display typeface, and you called that variation *a USP of the
platform*. `docs/PROJECT_STATE.json`'s handoff records it as a standing visual
decision not to be undone without you saying so.

The Sprint 17 brief says the opposite, in four separate places:

> Use a maximum of TWO BRAND typography families. […] Google Fonts CDN must be
> removed. […] Do not restore per-page display fonts. […] ONE engineering-tool
> accent system. Do not assign each tool its own brand color.

**What I did and why.** Under this project's evidence-precedence rule, your
explicit statement in the current session outranks a committed state document, so
the brief won and the per-page identities are gone. One accent (`#5b93ff`, which
was already `:root`'s value before Sprint 16 layered overrides on it), one brand
sans from the system stack, one dark ground, two corner radii.

**Why this needed saying out loud.** Removing eight per-page typefaces was
*required* to get third-party font requests to zero — they were the only reason
nine Google families were being loaded. So the font decision and the identity
decision were the same decision, and the brief made it. But you described the
result as a differentiator, and you should learn it is gone from this paragraph
rather than from a screenshot.

**If it was not intended:** the Sprint 16 block is one contiguous, clearly
commented section of `agent/web/style.css` at commit `a182be1`. Restoring it is a
revert, not a rebuild — though it would bring the Google Fonts dependency back
with it unless the faces are self-hosted, which is real work nobody has done.

**What I need from you:** confirm the reversal, or say restore. See
`docs/DESIGN.md`'s first section for the full statement.

---

## 2. A Standing Interview grading question that needs your confirmation

**Status:** BLOCKED_BY_OWNER. Nothing was changed. SI behaviour is frozen by the
brief and stayed frozen.

**Details deliberately not in this public repository.** The Standing Interview's
acceptance logic appears to require a specific technical detail in an answer about
one employer's async processing, and whether that detail is a confirmed part of the
Owner's record is an open question only he can settle. Discussing the confidence of
a specific career claim in a public repository that this portfolio links to is not
something to do on his behalf, so the specifics live outside it.

Where the full text is:

- the Sprint 17 report at `Downloads/docsforclaude/SPRINT17_FULL_REPORT_2026-09-30.md`
- to be carried into the private context repository (`karthik-ai-context`) as part
  of the canonical-claims work

**What I need from you:** read that section of the report and answer the one
question in it. One word settles it.

**The architectural fix this points at**, recorded for the future canonical-claims
work rather than done now, and safe to state publicly because it is a design
principle rather than a claim about anyone:

```
canonical facts  ->  graders consume canonical facts
```

rather than career claims duplicated inside handwritten evaluator code, where they
drift from the record and nobody notices. Logged as a backlog item.

---

## 3. Visual baseline gating: on or off?

**Status:** OFF, pending your acceptance. `e2e/visual-regression.spec.js` exists,
has 16 accepted-locally baselines, and is gated behind `VISUAL_REGRESSION=1`.

It is off because you have not seen the screenshots. Gating on a baseline nobody
agreed to would block every branch on a diff you never approved — and this branch
is the one asking your opinion.

**What I need from you:** after reading `docs/FIRST_SCREEN_REVIEW.md` and looking
at the two packs, say whether the AFTER screenshots are an acceptable baseline. A
yes makes it gating; a no means the baselines get regenerated after the next
change.

Honest limit, so the yes is informed: it catches unintended *change*, never
first-time ugliness. A baseline of an ugly page is an ugly baseline, faithfully
defended.

---

## 4. "Preview tier" — was there meant to be a tier system?

**Status:** the phrase is removed. Low stakes, recorded for completeness.

*2026-10-05, Sprint 19:* the removal was on the Sprint 17 branch only; the
Sprint 18 branch still carried the phrase. Sprint 19 applied the Sprint 17
tagline wording to `agent/web/workbench.html` (copy only; the auto behaviour is
unchanged by Owner instruction), and `agent/test_public_surface_gate.py` now
forbids "preview tier" hermetically.

The Workbench tagline described the auto-approved path as *"this preview tier"*,
which implies other tiers with different rules. Nothing in the code defines one:
there is one public path with one deterministic gate.

I removed the phrase rather than inventing a tier model, because a reader who
asks "what are the other tiers?" got no answer. If you intend a real tier
structure later, this is where the word went missing.

---

## 5. Three stale infrastructure items, unchanged from the Sprint 16 handoff

Not Sprint 17 findings. Restated because they still need you and nobody else can
do them.

- **`SI_OPERATOR_TOKEN` as a Railway service variable** (any random string, never
  in this repo). Without it the deploy acceptance gate cannot run — it makes 30
  requests against a 25/day per-visitor ceiling. The exemption fails closed, so
  production is safe exactly as it stands; each deploy just needs a manual wait
  for the UTC reset. Take the wait from the server's `Retry-After` header, never
  the local clock: the container ran ~6 minutes behind this laptop.
- **An NVD API key** as the GitHub Actions secret `NVD_API_KEY`, free from
  <https://nvd.nist.gov/developers/request-an-api-key>. Without it the OWASP
  dependency-check step cannot analyse anything and fails with "Invalid API Key,
  length of 0 too short".
- **A git write credential** (`ACT-007`) — the secure push architecture is built
  and proven live; only the credential itself is your decision.

---

## 6. Two real defects found this sprint that are not in scope to fix

Recorded as backlog, stated here because both are recruiter-visible.

*2026-10-05, Sprint 19:* the first is fixed -- `/`, `/proof` and
`/case-study/durable-agent` each carry exactly one `<main>` landmark, held by
`MainLandmarkTestCase`. The second (unbounded `/usage` length) is still open.

- **Three public pages have no `<main>` landmark**: `/`, `/case-study/durable-agent`,
  and `/standing-interview` before this sprint added one. That is a real
  screen-reader defect — a blind visitor cannot skip to content — and it is also
  why the BEFORE capture could not locate a primary control on those pages.
  Standing Interview got one because this sprint was restructuring it anyway;
  Home and Case Study did not, because adding landmarks to pages the brief said
  to leave alone is scope I do not have.
- **`/usage` is 69,830px tall on this machine** (6,759px against production). The
  difference is real data — 511 session rows locally against production's 2 — not
  a layout defect. But a page whose length grows without bound with history will
  eventually be that long in production too, and there is no pagination on the
  "All Sessions" panel, only a LOAD MORE on a different one.
