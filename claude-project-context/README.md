# Claude Project Context (public engineering)

Attach this **one folder** to the Claude Project as its public-repo
knowledge source, so Karthik never has to hand-pick dozens of files.

## Read order

1. **`CONTEXT_SNAPSHOT.md`** first — a single consolidated file containing
   the verbatim current content of every canonical public-engineering
   source Claude Chat needs to act as prompt architect.
2. `SOURCE_MANIFEST.yaml` if you need to know exactly which source file
   and which hash a given section came from.

## Ground rules

- **This bundle is a derived view, not a new source of truth.** Every
  section in `CONTEXT_SNAPSHOT.md` is copied verbatim from a canonical
  file in the main repository and says so. If this snapshot and a live
  canonical source ever disagree, **the canonical source wins** — this
  file may simply be stale (see `agent/validate_claude_context_bundle.py`,
  which fails loudly when that happens).
- **Bundle generation time is not fact observation time.** `CONTEXT_SNAPSHOT.md`'s
  header states both the source state (repository HEAD SHA + that
  commit's own timestamp — stable, changes only when a new commit lands)
  and `generated_at` (a real wall-clock regeneration timestamp — by
  design, differs on every run even with zero source changes; treat it as
  "when this copy was produced," never as evidence anything was
  re-verified). Its "Freshness contract" section spells out exactly how a
  prompt architect must treat `(canonical)` vs `(current)`/`(historical)`
  sections — each `(current)`/`(historical)` section carries its own
  `as of:` marker — and when a task requires inspecting the real live
  source instead of trusting this snapshot. Read that section before
  acting on any fast-changing fact (Git HEAD, CI status, production
  status, blockers, action queue, test/eval results).
- **Model memory is not authoritative.** A fact only counts as durable
  project truth if it's in one of the canonical files this snapshot was
  built from (or their live originals), never from a model's own
  recollection of a past conversation.
- **Current model roles:** Claude Chat = primary prompt architect (reads
  this bundle, produces precise Claude Code execution prompts). Claude
  Code = executor (inspects the real repo/runtime and carries out task
  contracts — Claude Code should generally read the live files directly,
  not this snapshot, since it has full repo access). ChatGPT = independent
  reviewer/challenger, invoked on request.
- This bundle covers **public engineering-project context only**.
  Karthik's private career/job-search/resume/trainer context lives in the
  separate private `karthikdevadoss/karthik-ai-context` repository's own
  `claude-project-context/` folder — attach both folders to the Claude
  Project, one from each repository.

## Regenerating

```
python agent/generate_claude_context_bundle.py
python agent/validate_claude_context_bundle.py
python agent/check_bundle_idempotency.py
```

Deterministic concatenation + hashing only — no LLM involved in
generating or validating this bundle. Re-run the generator whenever a
listed canonical source changes; the validator will refuse (exit 1) if a
source has drifted since the bundle was last generated, if a required
source has disappeared, or if it detects a phrase that belongs only in
the private repository. `check_bundle_idempotency.py` regenerates the
bundle again and confirms nothing except the known `generated_at`-bearing
lines changed — a real content difference (a source edited between the
two runs, or a generator bug) fails it and shows exactly which line
diverged.
