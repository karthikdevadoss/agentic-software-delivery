# Session Record — Trainer Demo: Already-Satisfied Requirement Misreported as FAILED

**Type:** development (bug found through real public trainer use, not a code review)
**Commits:** `e84d3a7` (fix + regression test). Related prior work: `a16a086` (trainer feature build), `d3dd645`/`a863e28`/`0d29b95` (real trainer-driven production deploys).

## What happened
A trainer submitted a real requirement through the public `/trainer` page:
"Add a small 'Agent Demo' status badge near the page title." This exact
badge had already been added and deployed during an earlier acceptance
test. The agent correctly investigated (`read_file` + `search_code`),
correctly found the badge already present in
`app/src/main/resources/static/index.html`, and correctly chose not to
propose any change. The trainer UI showed a bare `FAILED` with no
explanation.

## Root cause
`_run_trainer_thread` (agent/web_server.py) unconditionally required
`apply_succeeded and compile_succeeded and test_succeeded` to be true to
call a run successful. It never distinguished "the agent tried and a
real step failed" from "the agent correctly decided no change was
needed." Since `propose_source_change` was never called, `apply_ok` was
trivially `False`, and the run was labeled FAILED — a false negative for
a run that actually did the right thing.

A second, related bug in the same code: every FAILED path emitted the
`stage` event *before* the `error` event. The frontend's `stage`
listener closes the SSE connection as soon as it sees a terminal stage.
Because both events arrive in the same SSE batch, closing on the first
one risked dropping the second before the browser dispatched it —
another path to "FAILED with no visible reason," independent of the
already-satisfied bug.

## Fix
1. Deterministically check (from the event log, not model prose) whether
   `propose_source_change` was ever called. If not, a small keyword
   classifier (`risk_policy.looks_already_satisfied`, same
   denylist-style approach as the risk classifier) decides between a new
   terminal state `NO_CHANGE_NEEDED` and a genuine inconclusive `FAILED`.
   Neither branch grants any write/deploy authority — no code was
   proposed in either case, so this is purely a labeling decision.
2. Reordered every failure emission (`error`/`no_change_needed` before
   `stage`) and added a client-side delay + fallback message in
   `trainer.js` so a FAILED state can never render with zero
   explanation, regardless of batching order.
3. While re-verifying with a genuinely new requirement (footer line),
   found the deploy-poll window was *still* too short even after an
   earlier bump (4 min -> 7 min): a real cold Railway/Nixpacks build
   took ~11.5 minutes. Bumped to 15 minutes with the reasoning recorded
   in a code comment, rather than guessing a third time from one data
   point.

## Verification
- New regression test `agent/test_risk_policy.py` uses the *exact* real
  incident text as a fixture (`AlreadySatisfiedTestCase`), plus a
  negative case (a genuinely confused/inconclusive summary) to prove the
  classifier doesn't just say "always satisfied."
- Re-submitted the exact same requirement through the live public tunnel
  after the fix: correctly returned `NO_CHANGE_NEEDED` with the real
  reason, zero compile/deploy cost.
- Submitted a genuinely new requirement (footer line) and proved the
  full pipeline for real: propose -> apply -> compile -> commit
  (`0d29b95`) -> Railway deploy -> verified live in production via
  direct curl against the real URL (the run's own status still showed
  FAILED due to the timeout, independently confirmed the deploy
  actually succeeded).
- Full regression suite: 68 tests, 67 passed, 1 pre-existing platform
  skip, 0 failed, both before and after the fix.

## Efficiency lesson (the point of this whole fix)
An agent correctly recognizing "this is already done" and doing nothing
is the CORRECT, cheapest possible outcome — it must never be penalized
by looking identical to a real failure. Treating idempotent no-ops as
failures creates an incentive (for a human skimming results) to force
unnecessary rework, wasting real tokens/compile/deploy cycles on
something already satisfied. This is now a permanent terminal state in
the trainer's vocabulary, not a one-off patch.

## Interview/portfolio relevance
A concrete, real "describe a bug you found and the fix" story: found via
actual public use (not code review), root-caused from the real event
log (not guessed), fixed with a deterministic classifier consistent with
the project's existing security-classification style, and locked in with
a regression test built from the real failing input — not a synthetic
one.

## Addendum — SSE terminal-state bug (run `trainer-209e94e7`, commit `77f00b3`)

**Symptom:** Browser stuck at `STARTING`, Live Agent Progress panel
completely empty, no error shown.

**Backend reality:** The run completed correctly in ~12.3s, reaching the
new `NO_CHANGE_NEEDED` state (added by the fix above) with a full,
correct event trail — proven directly via `GET /api/runs/trainer-209e94e7`
and `web_run_history.jsonl`.

**Root cause:** `stream_events()`'s SSE termination check only recognized
`COMPLETED`/`FAILED` as terminal. `NO_CHANGE_NEEDED` was introduced in
this same fix session but never added to that check, so the generator
polled forever after the run actually finished — the connection never
cleanly closed, leaving the browser's `EventSource` with nothing to
process as terminal.

**Engineering lesson:** Adding a new state to a state machine requires
auditing *every* consumer of that state machine, not just the one you
were actively working on. The fix that introduced `NO_CHANGE_NEEDED`
(same session, same day) updated the trainer thread and the frontend's
own stage list, but missed the SSE delivery layer entirely — a
different file, a different concern, easy to forget under time pressure
immediately after fixing something else.

**Permanent prevention:** One authoritative `TERMINAL_RUN_STATES` set in
`agent/web_server.py` (derived from every real `run.status` value in
that file) plus `_run_is_terminal()`, used by `stream_events()` instead
of a second hardcoded tuple. `sessions_data.py` and `trainer.js` each
keep their own necessarily-separate terminal-state check but are now
commented to point back at this set as the source of truth.
`agent/test_web_server.py` regression-tests the exact hang (via a
bounded `asyncio.wait_for`, so a future regression fails fast instead of
hanging the test suite) plus every other real run status.
