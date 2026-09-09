# Lessons

Durable, reusable technical lessons discovered and verified while building
this project — not architecture decisions (see DECISIONS.md) and not
current state (see PROJECT_STATE.json). Keep entries short and reusable;
this is not a session diary. Add a new entry only when a real failure or
surprising verified behavior would otherwise get rediscovered later.

- **Claude Sonnet 5 returns thinking blocks by default; never assume
  `content[0]` is text.** A response's content list can start with a
  `thinking` block before any `text`/`tool_use` block. Always filter
  content blocks by `.type` explicitly; never index positionally. (Caused
  a real crash in V1: `message.content[0].text` raised `AttributeError`
  because block 0 was a `ThinkingBlock`.)

- **Every `tool_use` block in one assistant turn needs a matching
  `tool_result` in the very next user turn — none can be skipped or
  deferred.** If a safety limit (like a tool-call budget) is reached
  mid-batch, return a synthetic error `tool_result` for the excess calls
  instead of omitting them, or the conversation becomes invalid.

- **`stop_reason` alone is not a reliable "should I stop calling tools"
  signal.** A `max_tokens` cutoff can still carry a complete, valid
  `tool_use` block that must be executed. Gate tool-loop continuation on
  the presence of `tool_use` blocks in the response, not on
  `stop_reason == "tool_use"` specifically.

- **A hardcoded git-log snapshot inside a doc goes stale by construction**
  — a commit can't record its own hash in its own content before it
  exists. Prefer one durable fact (e.g. `last_verified_code_commit` in
  PROJECT_STATE.json) plus "run `git log` yourself" over embedding a log
  snapshot anywhere.

- **Windows drive-relative paths (e.g. `C:foo`, no leading slash) are not
  flagged by `pathlib.Path.is_absolute()`.** Verified empirically that
  `REPO_ROOT / "C:foo"` on the same drive resolves safely inside the repo
  anyway (harmless), but don't assume Windows path edge cases behave like
  POSIX — verify with a quick empirical probe rather than reasoning from
  POSIX intuition alone.

- **Maven Wrapper generation and first run both require network access**
  (the wrapper plugin itself, then the actual Maven distribution zip on
  first `mvnw` invocation). Don't assume `mvnw` is fully offline-capable
  out of the box in a fresh environment.

- **MCP's Python ecosystem naming is unstable across 2026 — verify current
  import paths every time, don't reuse a remembered one (including your own
  earlier answer in the same project).** Problem: an older tutorial's
  `from mcp.server.fastmcp import FastMCP` would already be wrong; picking
  standalone `fastmcp` instead (this session's first pass) wasn't wrong, but
  wasn't re-checked against the actual spec-owner SDK either. Evidence:
  re-verifying (via WebFetch + direct empirical testing of the installed
  `mcp` package) showed the official SDK's `MCPServer` now provides every
  capability that motivated choosing `fastmcp` — including an in-process
  test `Client`, which earlier research hadn't confirmed either way. Root
  cause: fast-moving ecosystems can make a reasonable choice stale within
  the same session; "current" needs re-checking at the point of committing
  to it, not just once at the start. Correction: migrated to the official
  `mcp` package while the surface was still 2 files. Future rule: for a
  Tier-1/spec-owned protocol, give the official SDK a real empirical trial
  (not just a docs skim) before choosing a third-party alternative, and be
  willing to migrate early rather than defend an earlier choice by inertia.

- **Incremental/differential systems should key entries by a stable ID, not
  positional array index.** Context: the RAG index needed to support
  add/update/remove of individual files without rebuilding everything.
  An early array-of-chunks design would make "remove chunk 7" fragile once
  other chunks are added/removed around it (indices shift). Correction:
  used a dict keyed by `f"{path}#{start_line}-{end_line}"` instead, so
  reuse/update/removal are plain dict operations regardless of what else
  changed. Future rule: whenever a system needs partial/incremental
  updates, design the storage keyed by stable identity from the start —
  retrofitting it after an array-based design is in place costs more.

- **A newly built local index/artifact directory must exclude itself from
  its own ingestion sweep.** Problem: the first RAG index rebuild indexed
  its own prior output file (`agent/.rag_index/index.json`), which would
  have compounded in size on every rebuild. Evidence: file count jumped by
  exactly one non-source file after the first build; confirmed by listing
  indexed paths. Root cause: the ingestion step reused the generic
  repository file listing without excluding its own output directory.
  Correction: added the index's own output path to a small ingestion-only
  ignore list. Future rule: any pipeline that both reads "everything in
  the repo" and writes its own output into the repo must explicitly
  exclude its own output path from the read side.

- **HuggingFace Hub's default local caching uses symlinks, which can fail
  on first use on Windows without Developer Mode/admin rights.** Problem:
  first `fastembed` model download raised `WinError 1314` (privilege not
  held) while creating a cache symlink. Evidence: observed directly during
  the first embedding-model load on this machine; the library
  automatically retried via a non-symlink fallback and succeeded ~24s
  later. Root cause: Windows restricts symlink creation by default.
  Correction: none needed — treated as expected first-run behavior, not a
  bug. Future rule: don't treat a Windows symlink warning/retry from
  HF-Hub-backed libraries as a failure; only investigate if it doesn't
  eventually succeed.

- **A path-safety check gated on `if resolved.is_file()` silently skips
  protection for files that don't exist yet.** Problem: `tools.py`'s
  secret-filename block (`.env`, `*credential*`, `*secret*`, etc.) only ran
  when the target already existed on disk — harmless for read-only tools
  (a nonexistent file can't be read anyway), but a real security gap once a
  write tool existed: an agent could create a brand-new file named e.g.
  `testcredentials.java` and the check never fired. Evidence: found via a
  deliberate test while building the V4 write boundary
  (`test_secret_named_new_file_in_scope_rejected`), reproduced before
  fixing. Root cause: the check was written with "does this file already
  look dangerous" in mind, not "could writing to this name ever be
  dangerous." Correction: removed the `is_file()` guard so the name/
  extension check always runs, regardless of existence; re-ran the full
  test suite (24 existing + new) to confirm no regression. Future rule:
  any path-safety check meant to protect against writes must never gate on
  "does the target currently exist" — that's precisely the condition a
  first write changes.

- **An "approved" boolean on a mutable object is not the same as binding
  approval to what was actually approved.** Problem: `PendingEdit.approved`
  was a plain flag; `apply_edit()` re-read `path`/`new_content` fresh at
  apply time with nothing checking they still matched what existed when
  `approve_edit()` was called. Evidence: a deliberate test mutated
  `edit.new_content`/`edit.path` after approval and the apply would have
  silently used the substituted value. Root cause: approval recorded "this
  ID was approved," not "this exact (path, content) pair was approved."
  Correction: `approve_edit()` now stores `sha256(path + content)` as an
  `approved_binding`; `apply_edit()` recomputes and compares it, refusing
  to apply on any mismatch. Future rule: whenever an approval/authorization
  step and the action it authorizes are separated in time, bind the
  approval to a hash/snapshot of exactly what was shown, not to a mutable
  reference that could change underneath it.

- **A substring check for "is this forbidden name present" can produce a
  false positive that masks whether the real invariant holds.** Problem:
  an ad-hoc check `any('approve' in n for n in tool_names)` reported `True`
  because `apply_approved_source_change` contains the substring "approve" —
  not because `approve_edit` was actually exposed. Correction: verify
  forbidden-name exclusions with exact set membership (`"approve_edit" in
  names`), not substring search. Future rule: when writing any check whose
  job is "prove X is absent," use exact matching — a substring/regex check
  can silently turn a real security-boundary test into theater.
