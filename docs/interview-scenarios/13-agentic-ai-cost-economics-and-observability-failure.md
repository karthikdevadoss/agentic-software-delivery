# Interview Scenario: A Real €40 Credit, Gone in Under 7 Minutes — Forensically Reconstructing an Agentic AI Cost Incident, and Fixing the Observability That Failed to Show It

Derived from a real incident (2026-09-16): a real pay-as-you-go API credit
top-up (~€40) was fully exhausted in **under 7 minutes**, at a precisely
identifiable moment inside a much longer Claude Code session — reconstructed
to the exact second via direct forensic parsing of the session's own
transcript files, not estimation. The same investigation also found and
fixed two real, previously-undiscovered defects in the telemetry system that
was supposed to make this kind of thing visible on its own, without needing
manual forensics at all.

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
`cache_read_input_tokens`). The method: replay every assistant turn's
`usage` object in timestamp order, computing a running cumulative cost at
Anthropic's list pricing for the model in use ($2/$10/$2.50/$0.20 per MTok
for input/output/cache-write/cache-read) — then find the exact moment that
running total crosses a real, known dollar boundary.

**The exact boundary, to the minute:**

- **23:05 UTC** — an interactive, supervised exchange: *"I want you to act
  as my technical partner here, not just as an implementation agent...
  do not edit anything yet."*
- **23:23:28 UTC** — the mode switch: *"OVERNIGHT OWNER-AUTHORIZED
  ENGINEERING + AI-INTELLIGENCE PASS... I am going offline... Do NOT stop
  to ask me for another plan approval, routine engineering decisions..."*
  — removing the one thing (a human checkpoint) that could have caught
  what happened next.
- **23:25:49 UTC** — cumulative cost crosses $40. **23:30:21 UTC** —
  crosses $44 (~€40.7 at the day's conversion rate). **The real €40 credit
  was gone in under 7 minutes of unsupervised operation.**

**Why it happened that fast, mechanically — not "a runaway loop," something
more mundane and more instructive:** by this point the session already had
~5-6 hours of accumulated conversation history, so *every single turn* —
a plain `Bash` command, a `Read`, an `Edit` — was re-sending roughly
550,000-590,000 cache-read tokens just to maintain context, before any new
work happened. At $0.20/MTok that's ~$0.11-0.18 *per turn* as pure
overhead. A per-minute replay of the exact window shows 5-15 turns firing
per minute (Bash, Read, Edit, and live browser automation via a
Claude-in-Chrome MCP integration) with nothing pausing it. At roughly
$1-3/minute sustained, a ~€40 credit does not last long. No single action
was expensive; the combination of *already-large context* × *high turn
frequency* × *zero pause* was.

**Zooming out to the full session** (it continued long after this, now
running against Max plan quota rather than further real charges): across
~3,540 assistant turns over 38 hours and 4 resumes, total usage was 3.05M
output tokens, 16.8M cache-write tokens, and 1.84 BILLION cache-read
tokens — $439.87 at raw list price if the *entire* session had been billed
per-token, which it was not. Five subagents (found via each session's
`<session>/subagents/*.jsonl` + `.meta.json` sidecar, since Claude Code
does not inline subagent turns into the parent transcript) accounted for
only ~$36 of that total; the dominant driver throughout was the main
thread's own ever-growing, never-compacted context, the same mechanism
identified in the precise 7-minute window above — just sustained for much
longer.

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
- Closed the same night: per-subagent cost attribution. `claude_code_hook.py`'s
  `SessionEnd` handler now automatically walks `<session>/subagents/*.jsonl`
  (the exact convention this investigation discovered by hand) and records
  one `claude_code_subagent_usage` event per spawned subagent — a future
  incident gets this attribution automatically, not via manual forensics.
- Also closed: the Usage page's headline "Lifetime AI spend" figure covered
  Workbench pipeline runs only, with no label saying so — sitting next to
  this incident's real $439.87 Claude Code development cost, it looked
  directly contradictory. Fixed with an explicitly-scoped, separate
  "Claude Code Development Cost" panel (`get_dev_session_cost_summary()`)
  shown alongside, never merged into, the Workbench number.
- Still open: cost is only visible at whole-session granularity for the
  *main* thread (subagents are now itemized, the main thread is not) — a
  future improvement would checkpoint usage incrementally (e.g. on `Stop`)
  rather than only at `SessionEnd`, so a still-running multi-hour session
  is never a total blind spot.

## Interview Questions This Answers

- "Tell me about a real production incident involving cost/observability
  for an AI system — how did you find the actual root cause?"
- "Given a known real-world boundary (a credit that hit zero) but no
  application-level log for it, how do you locate the exact moment it
  happened using only lower-level data you do have?" (Answer: replay the
  real per-event usage data in order, compute a running cumulative value,
  and find where it crosses the known threshold — turning an approximate
  memory of 'it happened sometime that night' into a to-the-second finding.)
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
