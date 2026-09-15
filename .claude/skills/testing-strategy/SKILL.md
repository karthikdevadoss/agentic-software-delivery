---
name: testing-strategy
description: Decide WHAT MUST BE PROVEN for a change before implementing it — not merely whether tests ran. Selects the right proof obligations from the change's real risk/context (public UI vs. customer-data/security-sensitive vs. other), so a tiny change doesn't get every possible check and a risky one doesn't get too few. Use when planning or reviewing a change's test strategy, before or alongside implementation.
---

# Testing Strategy — What Must Be Proven

**Prescribed duty (single):** given a real, already-classified change
(see [[requirement-contract]] for scoping it and `agent/change_risk.py`
for its real risk/blast-radius), decide the SET of proof obligations that
change actually needs — not a fixed checklist applied uniformly, and not
"did some tests run." This Skill answers the question one level before
[[test-change]]'s: that Skill records the truthful PASSED/FAILED/
NOT-APPLICABLE terminal state for tests that already ran; this Skill
decides which tests/checks a change of this kind needs to exist in the
first place.

## Canonical sources (reference, do not restate)

- Real risk/blast-radius classification: `agent/change_risk.py`
  (`classify_change`, `RULES`).
- Real deterministic Test Impact Analysis: `agent/test_impact_analysis.py`.
- The deterministic Test Architect cross-check (Base Architecture V3
  Section 9): `agent/test_architect.py::build_test_contract` — matches a
  changed-file set against catalogued invariants
  (`docs/INVARIANT_REGISTRY.md`) and flags an invariant-governed file
  whose proving test isn't actually selected.
- Real historical evidence for why this matters: `docs/ai/
  AI_ENGINEERING_QUALITY_LEDGER.yaml` AEQ-024 (a real production
  navigation-consistency defect that escaped because link-integrity and
  page-identity checks existed, but nothing checked that the SAME
  canonical nav SET was consistent across pages) and AEQ-018 (the real
  duplicate-plan-enrollment defect).

## Selection principle — risk/context-driven, not blanket

Do not require every possible check on every change. Select proof
obligations from what actually changed and what could actually go wrong,
using the real classification from `agent/change_risk.py` as the
starting signal (LOW/MODULE for a single isolated file, HIGH/CROSS_MODULE
for something touching shared infrastructure) — then apply judgment for
the specific change TYPE using the scenarios below as reference patterns,
not a rigid decision tree to follow blindly.

## Scenario 1 — Public UI / navigation change

Grounded in a real defect (AEQ-024): "Role Showcase" was silently absent
from 6 of 8 public pages' navigation because each page hand-copied its
own `<nav>` block — every individual link resolved fine (HTTP 200), so a
pure link-integrity sweep alone would not have caught it. An earlier real
defect (AEQ-022) was a single broken link on a single page — the SAME
sweep DID catch that one. Two real defects, two different actual proof
obligations, from what looks like "the same kind of change" at a glance.

Decide which of these a UI/navigation change actually needs, by asking
what the change touches:

- **Canonical route validation** (does the target route exist in
  `agent/web_server.py`'s real route table?) — needed whenever a NEW link
  or route is introduced. Not needed for a pure copy/wording change to
  existing, already-linked content.
- **Navigation-SET consistency across pages** (does every public page
  render the same canonical destination set, e.g. via `agent/web/nav.js`?)
  — needed whenever a page's `<nav>`/menu markup itself changes, or a new
  canonical destination is added/removed. NOT needed for a change that
  only touches a page's `<main>` content and never its nav markup.
- **Direct-navigation / hard-refresh behavior** — needed whenever
  behavior could plausibly differ between client-side routing state and
  a fresh page load (e.g. anything JS-rendered, like `nav.js` or
  `showcase.js`'s async title fetch). Not needed for pure server-rendered
  static content with no client JS involved.
- **Rendered-browser check, not HTTP status alone** — needed whenever
  content is populated by client-side JS after load (see AEQ-024's own
  `e2e/nav-consistency.spec.js`, and the earlier lesson that Showcase's
  raw HTML shows a "loading…" placeholder until JS replaces it). A pure
  server-rendered page with no async JS can be adequately checked via
  `e2e/link-integrity.spec.js`'s HTTP-level check alone.
- **Important CTA target check** — needed for any change touching a
  primary recruiter-facing action (e.g. Workbench's requirement textbox,
  Showcase's "OPEN CUSTOMER APP" button). Not needed for secondary/
  cosmetic elements.
- **Dead-link detection** — needed for any change adding/editing a
  rendered `<a href>` anywhere, always (cheap, general, matches AEQ-022's
  exact original failure mode).
- **Production-visible check after deployment** — needed for any change
  that will actually be deployed (i.e., always for a real Workbench
  auto-executed change or a manually-deployed fix); not needed while a
  change remains local/unreviewed.

**Not every tiny UI change needs every item above.** A copy-only change
to one page's tagline text needs dead-link detection (cheap, catches
nothing here but costs nothing) and a production-visible check after
deploy — it does NOT need navigation-set-consistency re-verification,
since it never touches `<nav>` markup.

## Scenario 2 — Customer data / security-sensitive change

Grounded in the real Update Email feature (`4440f6d`) and this session's
own real historical replay of it (branch `trainer-replay/update-email-v3`,
`docs/training/REPLAY_EVIDENCE_SUMMARY.md` — that branch only, not
master), which surfaced a real, concrete finding:
this codebase has no workspace/tenant/ownership concept at all, so
"a user must not update another workspace/customer" cannot currently be
proven beyond a scope check — a genuine, disclosed gap, not something to
silently under-test around.

Required proof obligations for this class of change (customer data
mutation, especially behind an authorization boundary):

- **Authorized success** — the real, intended actor can perform the
  action and see the real, persisted result.
- **Unauthorized / cross-boundary denial** — a real request lacking the
  required scope/authority is rejected (401/403), not silently allowed
  or silently no-op'd. If no cross-workspace/cross-tenant isolation
  exists yet in the code (as is currently true here), this must be
  stated as an explicit, disclosed gap in the Test Contract — not tested
  around by writing a test that can't actually prove the thing the
  ticket asked for.
- **Malformed input rejection** — invalid data (e.g. a malformed email)
  returns a real 400 with a structured error, never a 500 or a silent
  partial write.
- **Missing-resource behavior** — a real, correct 404 for a non-existent
  target, distinguishable from an authorization failure.
- **Persistence after a fresh read** — the change is verified by
  actually reading it back in a SEPARATE request/transaction, never
  merely asserting the write call returned success.
- **Unrelated fields remain unchanged** — an update must never
  accidentally rebind or clear fields it wasn't asked to touch (see
  `CustomerEmailUpdateRequest`'s existing design: a single-field DTO,
  never the full entity, structurally prevents this class of bug).
- **Correct integration boundary tested at the right level** — a pure
  service-level unit test (mocked repository) for business-rule
  correctness, PLUS a real Spring Boot integration test (real HTTP, real
  DB) for the full authorization+persistence path — neither substitutes
  for the other (see `docs/TESTING_ARCHITECTURE_V2.md`'s own real
  mutation-testing finding: the integration-level test caught a
  `BigDecimal` scale defect the isolated unit test could not).
- **Focused regression** — the specific test classes covering the
  changed file and its real callers (use `agent/test_impact_analysis.py`
  and, for real symbol-based verification of what those callers actually
  are, `agent/test_architect.py`'s invariant cross-check).
- **Broader regression per real impact** — if `agent/change_risk.py`
  classifies the change as fail-closed (shared/security-adjacent code),
  the full suite, not just the narrowly-selected set.

## Why these two scenarios were chosen

Both are grounded in this project's own real, recent, evidenced
incidents — not hypothetical examples. Scenario 1 (AEQ-024, found and
fixed the same day this Skill was written) demonstrates that "every link
resolves" and "every page shows the same canonical set" are genuinely
different proof obligations discovered by direct comparison of two real
defects. Scenario 2 (Update Email) is this project's own canonical
security-sensitive customer-data change, already real V3-agent-replayed
this session with a real, disclosed finding (no workspace isolation
exists) that a testing strategy must surface honestly rather than paper
over.

## Must NOT

- Must NOT require every possible check on every change regardless of
  what actually changed — see the Selection principle above.
- Must NOT let a testing-strategy Skill substitute for
  [[test-change]]'s terminal-state gate, or for [[ai-feature-evaluation]]'s
  eval-regression gate — this Skill decides WHAT should be proven; those
  Skills decide whether what ran actually passed.
- Must NOT write a test that appears to prove an authorization boundary
  (e.g. cross-workspace isolation) that does not actually exist in the
  code yet — state the gap honestly instead (see Scenario 2).
