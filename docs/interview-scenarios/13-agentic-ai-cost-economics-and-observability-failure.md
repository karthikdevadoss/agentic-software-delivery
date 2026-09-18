# Interview Scenario: Agentic AI Cost Economics — A Real €40 Overnight Incident, and Why the Observability Meant to Prevent It Had Silently Failed

Derived from a real incident (2026-09-16 → 2026-09-18): a single Claude Code
session accumulated an estimated $439.87-at-API-list-price token bill (real
€40 pay-as-you-go credit actually burned before switching to a Max plan),
root-caused via direct forensic analysis of the session's own transcript
files, and two real, previously-undiscovered defects found and fixed in the
telemetry system that was supposed to make this kind of thing visible.

## Business Why

Agentic coding tools (Claude Code and similar) charge by token, and modern
LLM pricing structurally rewards long conversations via prompt caching
(cache reads cost a fraction of fresh input). That combination creates a
non-obvious risk: a session's *per-message* cost looks cheap and its
*aggregate* cost over hours can be enormous, and neither the tool nor most
surrounding infrastructure surfaces that aggregate cost live, in context,
broken down by what was actually being done. When something built to solve
exactly that (a durable, per-event cost ledger) itself silently stops
working, the operator is flying blind at the exact moment they most need
visibility — a classic "observability system whose own failure is
invisible" problem, not unique to AI tooling but sharpened by it.

## Requirement (reconstructed after the fact — the real gap this exposed)

- Every meaningful AI-costing activity should be attributable: what was
  done, how long it took, exactly how many tokens, and a cost figure or a
  clearly labeled estimate — not just a session total.
- That data must reach a durable store reliably; a capture mechanism that
  silently stops delivering data is worse than no mechanism, because it
  creates false confidence.
- A human operator should be able to answer "why did this cost so much"
  from evidence, not from memory or a rough guess.

## Architecture (as it actually existed, and where it broke)

```
Claude Code hook fires (SessionStart/PreToolUse/PostToolUse/SessionEnd/...)
   |
   v
agent/claude_code_hook.py  -- must return in milliseconds, zero network I/O
   |-- event_ledger.spool_only()   -- appends to a local JSONL file only
   |-- event_ledger.trigger_background_sync()
           |-- if SYNC_LOCK_PATH.exists(): return   <-- BUG 1 (no staleness check)
           |-- else: touch lock, spawn detached `python event_ledger.py --sync-spool`
                        |
                        v
                new subprocess, _schema_ready = False (fresh process)
                        |
                        v
                sync_spool():  with _lock:  ...  _insert(row)  ...
                                                     |
                                                     v
                                              ensure_schema(): with _lock:  <-- BUG 2 (same
                                              non-reentrant lock, same thread -> deadlock)
```

Real production Postgres ledger (Railway) <---- never reached, for 7 real days
```

## The Two Real Bugs, Found By Direct Forensic Investigation

**Bug 1 — a lock file with no expiry silently disabled all future syncs.**
`trigger_background_sync()` guarded spawning a new sync subprocess with a
plain "does this lock file exist" check. A sync process died mid-flight
(most likely the laptop sleeping) before its own `finally:` cleanup could
remove the lock. From that moment, every subsequent call saw the lock,
returned `{"spawned": False}`, and did nothing — for 7 days, silently,
because a Claude Code hook must never raise or block (correct design for
hooks in isolation, but it meant zero error surfaced anywhere). Real spool
file grew to 41MB / 18,190 events, none reaching the durable store.

**Bug 2 — a non-reentrant lock deadlocked every real background sync,
independent of Bug 1.** Even after removing the stale lock, the actual
sync subprocess would have hung forever on its first row: `sync_spool()`
holds `_lock` (a plain `threading.Lock()`) for its whole run, then calls
`_insert()`, which unconditionally calls `ensure_schema()`, which tries to
acquire the *same* lock from the *same* thread. A non-reentrant lock blocks
forever on that second acquisition — and because `trigger_background_sync()`
*always* spawns a brand-new subprocess (fresh `_schema_ready = False` every
time), this path was hit on literally every real sync this mechanism ever
attempted, not a rare interleaving. Found by writing a minimal, timestamped
repro script and watching a real 20-second hang with zero output — the same
technique used throughout this project's own debugging discipline (evidence
over assumption).

**Fix:** `SYNC_LOCK_PATH` gets a 30-minute max-age check before being
treated as abandoned (Bug 1); `_lock` changed from `threading.Lock()` to
`threading.RLock()` so the same thread can safely re-enter it (Bug 2). Both
proven independently: a direct repro script showing the hang before the fix
and the immediate return after, plus 3 new automated regression tests
(`StaleSyncLockTestCase` x2, `SyncSpoolFreshProcessTestCase`) that would
catch either regressing.

## Reconstructing "What Actually Cost The Money" — Forensics, Not Estimation

With no live dashboard to consult, the actual per-task cost breakdown had
to be reconstructed directly from Claude Code's own on-disk transcript
files (`~/.claude/projects/<project>/<session>.jsonl` for the main
conversation, plus a `<session>/subagents/*.jsonl` per spawned subagent —
each carries real, provider-returned `usage` objects per assistant turn:
`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`).

Key findings from parsing ~3,540 assistant turns across a 38-hour, 4-times-
resumed session:

- **Total: 3.05M output tokens, 16.8M cache-write tokens, 1.84 BILLION
  cache-read tokens** — at Anthropic's list pricing for the model in use
  ($2/$10/$2.50/$0.20 per MTok for input/output/cache-write/cache-read),
  that totals **$439.87**.
- **Per-hour bucketing** (grouping every turn's timestamp to its UTC hour
  and summing cost) pinpointed a single hour at ~$49 — the almost-certain
  match for the Owner's own report of losing a real €40 credit top-up "in
  an hour."
- **Subagent attribution**: each subagent spawned via the `Agent`/`Task`
  tool gets its *own* transcript file, not inlined into the parent's
  `isSidechain` field as might be assumed — so accurately attributing cost
  to "the two parallel background forks" required locating and separately
  parsing 5 distinct subagent transcript files (found via each one's
  `.meta.json` sidecar, which records `agentType`, `description`, and for
  `fork`-type agents, `worktreeBranch`). Those 5 subagents totaled only
  ~$36 of the $440 — the dominant cost was the *main* thread's own 38-hour,
  never-compacted history, not the subagent work itself.
- **The real trigger event**: two `fork`-type subagents were launched in
  parallel at 01:13–01:14 AM specifically to "get more done while the Owner
  slept" (one UI/frontend work, one backend cost-accounting work in an
  isolated git worktree) — both were cut off after ~20 minutes by a real
  rate/spend limit, which is what forced an emergency plan-tier switch.

## Failure Cases (real, observed)

- A telemetry capture mechanism can be 100% functionally correct
  (`claude_code_hook.py` genuinely extracted real usage every time) while
  its *delivery* mechanism is silently, completely broken — these are
  separable failure modes and must be tested/monitored separately.
- Prompt-cache economics invert intuition: a "cheap per-token" cache-read
  price (10x below fresh input) does not bound total cost when volume is
  unbounded — a long enough, never-compacted conversation converts a
  10x-cheaper rate into a dominant cost line item purely through repetition.
- Parallelizing autonomous agents multiplies *rate* of spend, not just
  total work done — the two forks didn't need to run for hours to matter;
  they needed to run *simultaneously* to double the burn rate at the exact
  moment a spend limit was closest.

## Testing

`test_event_ledger.py`: `StaleSyncLockTestCase` (fresh lock still blocks;
a lock older than the max age is removed and a new sync spawns) and
`SyncSpoolFreshProcessTestCase` (sync_spool must not hang when
`_schema_ready` is False — run on a background thread with a hard 15s
join-timeout so a regression fails the test instead of hanging the suite
forever). Both proven against the real fix, not mocked around it.

## Design Trade-offs

- **Reconstructing cost from raw transcript files (chosen, for the
  historical incident) vs. waiting for the ledger drain to complete:** the
  transcripts are the actual source of truth Claude Code itself writes
  regardless of any downstream telemetry system's health — parsing them
  directly gave an immediate, verifiable answer without depending on the
  very system that had just been proven broken.
- **RLock (chosen) vs. restructuring so `ensure_schema()` is never called
  from inside another `_lock`-held critical section:** RLock is the
  minimal, behavior-preserving fix — every existing caller already assumed
  reentrant-safe behavior; changing the call structure instead would touch
  more surface for no additional safety.
- **30-minute lock TTL (chosen) vs. a shorter one:** a normal drain
  finishes in well under a minute; 30 minutes is generous headroom against
  false-positive "abandon" on a merely slow (not dead) sync, while still
  being far shorter than "forever."

## What Changes At Scale / Going Forward

- A connect-per-row insert loop (the pre-fix `sync_spool()`) is fine for a
  live trickle of individual hook events but becomes the bottleneck the
  moment a real backlog needs draining — fixed to reuse one connection for
  the whole batch, with a one-row fresh-connection retry as a fallback if
  the shared connection itself drops mid-batch.
- The next real gap (proposed, pending review, not yet built): per-task
  granularity is still missing — today's `model_usage` event is one row
  per whole Claude Code session, not per meaningful sub-task, so "why did
  this cost what it cost" for a normal-length session still requires this
  same manual transcript-forensics process rather than a live answer.

## Interview Questions This Answers

- "Tell me about a real production incident involving cost/observability
  for an AI system — how did you find the actual root cause?"
- "What's the difference between a system that's *functionally correct*
  and one that's *operationally reliable* — give a concrete example."
- "Explain why prompt caching can still lead to a large total bill despite
  discounting cache reads heavily."
- "How do you debug a background process that isn't a crash — it just...
  never finishes? What's your process for confirming a hang vs. genuine
  slowness?"
- "Describe a time you found a bug by writing a minimal reproduction
  script instead of reasoning about the code in the abstract."
- "Why is `threading.Lock` dangerous to nest, and what's the fix?"

## Live Demo / Evidence Links

- `agent/event_ledger.py` — `trigger_background_sync()` (Bug 1 fix),
  `_lock = threading.RLock()` (Bug 2 fix), `sync_spool()` (connection-reuse
  fix)
- `agent/test_event_ledger.py` — `StaleSyncLockTestCase`,
  `SyncSpoolFreshProcessTestCase`
- `docs/LESSONS.md` (2026-09-18 entries) — the full incident record
- `docs/CONSTITUTION.md` §7 — the Owner's own stated operating principle
  this incident tests against
- Real session transcript: `~/.claude/projects/.../b5171aab-*.jsonl` +
  its `subagents/*.jsonl` (the actual forensic source data for the cost
  breakdown above)
