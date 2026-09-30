# A proposed simplification of CLAUDE.md

Sprint 17, 2026-09-30. **Documentation only.** `CLAUDE.md` and everything under
`.claude/` were not touched this sprint, by instruction. This is a proposal for
the Owner to accept, reject or edit — nothing here has been applied.

---

## The measurement

| File | Size | Loaded |
|---|---|---|
| `CLAUDE.md` | 24,880 bytes | every session, always |
| `.claude/rules/sprint-process.md` | 11,482 bytes | when a sprint/backlog/retro file is read |
| `.claude/rules/java-and-services-change.md` | 2,596 bytes | when Java/`pom.xml`/`app/`/`services/` is read |

So roughly **25 KB is paid on every single session**, including a session whose
whole job is a one-line CSS fix.

The path-triggered split introduced in Phase 3 (2026-09-25) already works: this
session read the sprint rules when it opened `docs/BACKLOG.json` and never paid
for the Java rules at all, because it touched no Java. The proposal below is more
of the same idea, not a new one.

---

## What I am NOT proposing

Stating this first, because "simplify" is the word most often used to mean "drop
the parts that were inconvenient".

- **No rule is weakened, shortened or dropped.** Every sentence that survives
  survives verbatim, the way Phase 3's move did.
- **No hard-won incident narrative is deleted.** The EUR40 overnight incident, the
  four misclassified hermetic modules, the truncated-evidence root cause, the two
  concurrent forks both minting `ACT-015` — every one of those is the reason a
  rule exists, and a rule without its incident gets argued away by the next
  session that finds it inconvenient. They move; they do not go.
- **Nothing about cost, spend limits, or paid-model policy moves anywhere.** That
  section earned its place at the top of every session.

---

## Proposal 1 — move two sections to path-triggered rule files

Both are large, both are irrelevant to most sessions, and both already have an
obvious trigger path.

### 1a. The AI-characteristic defect discipline → `.claude/rules/ai-defect-discipline.md`

Roughly 7 KB. Trigger paths: `agent/test_*.py`, `e2e/*.spec.js`,
`agent/ci_python_tests.py`, `agent/verify_change.py`, `agent/release_health.py`,
`agent/select_tests.py`, `docs/TESTING.md`, `docs/testing-matrix.json`.

**But three bullets stay in `CLAUDE.md` verbatim**, because a session can violate
them before it has opened any file that would trigger the rule:

- *Never write against a remembered API.* This fires on the first tool call of a
  session that adds a dependency. Too late if it loads on file read.
- *SKIPPED is not PASSED.* Applies to every verification report anywhere.
- *Write-capable subagents run in an isolated git worktree.* This has to be known
  before the `Agent` call, not after.

The rest — the deterministic-gate rules, the computed-not-judged rule, the
diagnostic-tool-must-detect-the-known-bad-case rule, the honest statement of the
two unsolved problems — is genuinely testing-session material.

### 1b. The Durable-state rules' operational tail → `.claude/rules/session-handoff.md`

Roughly 3 KB: the stash-pointer rule, the "local commit is not durably saved"
rule, the §17 no-knowledge-only-on-this-laptop checklist. All of it applies at the
*end* of a session or when interrupted, not while reasoning.

**Risk, stated honestly:** a session that ends abruptly may never have read a
file that triggers it. Mitigation: keep one line in `CLAUDE.md` —

> Before stopping, or if interrupted: read `.claude/rules/session-handoff.md`.

That is a pointer, and a pointer is weaker than the rule. This is the one
proposal here with a real downside, and it is the Owner's call whether 3 KB per
session is worth it.

---

## Proposal 2 — the Session-startup section is longer than the command it describes

The section spends twelve numbered steps describing a workflow whose first step is
a single command that already prints everything the next five steps need.

Proposed replacement, same force, about a third of the length:

```markdown
## Session startup
1. `python agent/state_brief.py` — replaces reading three documents totalling
   402 KB. It is a VIEW: it writes nothing, is never committed, and states no
   fact of its own. A non-zero exit means a real problem (a renamed heading, an
   unclassified queue status, a missing state key) — fix that, do not skim past it.
2. `git status --short`, `git log -5 --oneline`.
3. Heed the staleness banner. When `last_verified_code_commit` is behind HEAD,
   `next_action` is a historical claim, not an instruction. Never resolve it by
   editing the date — the number is the only signal the document is unverified.
4. Read a full source document only for what the brief deliberately omits, which
   it names at each omission.
5. Before reporting previously-described work as lost: `git stash list`,
   `git branch -a`, `git reflog -20`. Status and log alone are NOT a complete
   picture — interrupted work is routinely and correctly stashed or left on an
   unmerged branch.
6. Verify any documentation claim that actually matters for the task against real
   source or Git. Repository state wins; correct the stale doc after verifying.
7. Do not modify code until asked.
```

Dropped: the enumeration of which document holds which omitted detail (the brief
prints that itself, at the point of omission), and the separate
`docs/DECISIONS.md` / `docs/LESSONS.md` / `docs/RETRO_LOG.md` read steps — those
are already path-triggered or read on demand.

---

## Proposal 3 — one line that is now obsolete

> Validation/hardening mode is a real, declarable project state. […] Check
> `docs/PROJECT_STATE.json`'s `next_phase`/`next_action` for whether this is
> currently in effect.

The rule is good. The instruction to check is redundant: `state_brief.py` already
prints `next_phase` and `next_action` on every startup, so a session that followed
step 1 has already read them. Keep the rule, drop the "check" sentence.

---

## What this would save

| | Before | After |
|---|---|---|
| Always-loaded `CLAUDE.md` | ~24.9 KB | ~14–15 KB |
| Testing-session total | ~24.9 KB | ~22 KB |
| Java-session total | ~27.5 KB | ~24 KB |
| Docs-only session total | ~24.9 KB | ~15 KB |

Roughly **40% off the fixed per-session cost**, with nothing deleted and nothing
weakened.

---

## The argument against doing any of this

Worth writing down, because it is not a weak argument.

Every byte in `CLAUDE.md` is there because something went wrong once. The file is
long because the project has learned a lot, and its length is evidence of that
rather than a defect. Moving a rule behind a path trigger means **a session that
does not touch that path never sees it** — which is the entire point, and also the
entire risk. Phase 3's split has held so far, but "so far" is one month.

The honest summary: the cost is real and measurable, the risk is real and not
measurable. That asymmetry is exactly why this is a proposal and not a change.

**My recommendation, for what it is worth:** do 1a and 3, which are low-risk and
account for most of the saving. Hold 1b — the session-handoff rules are the ones
whose violation costs real work, and a pointer is not the rule. Do 2 whenever the
Session-startup section is next edited anyway, rather than as its own task.
