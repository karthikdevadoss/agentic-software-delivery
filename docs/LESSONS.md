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

- **An interactive approval prompt must fail closed, not crash, when no
  real terminal is attached.** Problem: `input()` raises `EOFError` in a
  non-interactive tool-calling environment (confirmed empirically).
  `_default_approval_prompt` didn't catch it, so a live run in such an
  environment would have crashed instead of safely refusing. Correction:
  catch `EOFError` and return `False` (reject) — absence of a human is not
  the same as an approving one. Future rule: any human-gate function must
  treat "cannot reach a human" as equivalent to "rejected," never to
  "approved" or "crash."

- **Temporary test/demo fixtures must actually be cleaned up, or they
  contaminate real agent observations later.** Problem: a cleanup command
  used a relative path after a preceding `cd`, so `rm -rf app/src/test/...`
  silently targeted a nonexistent path and did nothing; the leftover
  fixture file was then picked up and reported by a *real* V3 agent run's
  tool trace in a later step, momentarily looking like a real anomaly.
  Correction: re-ran cleanup with a correct path, verified with `find`
  before trusting it. Future rule: verify a cleanup actually removed the
  target (don't just trust the command exited 0) before treating the
  workspace as clean, especially right before a run whose output you're
  about to inspect for signal.

- **Agent execution must not depend on one observability transport.** A
  Cloudflare Quick Tunnel silently dropped an entire SSE stream — no
  error, no close, zero bytes — while the backend genuinely executed a
  real run to completion. A client cannot reliably detect that class of
  silent failure from `EventSource`'s own signals. Correction: UI state
  must come from authoritative backend state (an ordinary `GET` of the
  same run), not from the assumption that a live stream is healthy —
  SSE stays the fast path, plain HTTP polling runs as an always-on
  safety net, not a failure-triggered fallback (a client can't always
  detect the failure to trigger on). A transport failure is not the same
  as an execution failure, and a user must always be able to tell
  working / waiting / stalled / degraded / failed / completed apart —
  see `agent/web/trainer.js` and `knowledge/sessions/2026-09-10-trainer-idempotency-fix.md`.

- **Adding a new state to a state machine requires auditing every
  consumer of it, not just the one you're actively working on.** Adding
  `NO_CHANGE_NEEDED` to fix one bug immediately broke SSE stream
  termination, because the delivery layer had its own separate,
  now-stale terminal-state list nobody thought to check in the same
  change. Correction: one authoritative `TERMINAL_RUN_STATES` set instead
  of duplicated tuples; when introducing or changing a run state,
  explicitly review execution/orchestration, terminal-state definitions,
  event emission, SSE, polling/status APIs, persistence, Sessions,
  Dashboard, frontend rendering, and tests — not by blindly editing all
  of them, but by checking each one and changing only what actually needs it.

- **`subprocess.run(..., text=True)` on Windows decodes captured output
  using the system codepage (cp1252), not UTF-8, unless `encoding=` is
  given explicitly.** A CLI tool's own colored/unicode output (e.g.
  Railway's "●" status bullet) can contain byte sequences invalid under
  cp1252, raising `UnicodeDecodeError` inside `subprocess.Popen`'s
  background reader threads. That exception doesn't propagate to the
  caller (Python's default thread-exception hook just prints it) — the
  call appears to "succeed" with corrupted/empty captured text instead of
  raising, which silently broke a `"Online" in status_out` check and
  produced repeatable false "deployment failed" results even though the
  real deploy had succeeded. Root cause confirmed at the exact byte level
  (not assumed): Railway's "●" bullet is U+25CF, UTF-8-encoded as
  `E2 97 8F`; byte `0x8F` alone is undefined in cp1252, which is exactly
  the crash observed. Fixed with `encoding="utf-8", errors="replace"` on
  `_run_controlled()`'s `subprocess.run` call (`agent/web_server.py`).
  Separately, decoding failure had also been conflated with deployment
  failure — fixed by making an independent HTTP check of the real public
  URL the primary evidence for success/failure, with CLI polling only
  corroborating (`_decide_deployment_outcome()`), and adding a genuine
  `DEPLOYMENT_STATUS_UNKNOWN` outcome for when neither signal confirms
  anything — "unknown" and "failed" are not the same claim.
- **Docker `COPY` from a Windows build host does not preserve/infer a POSIX
  executable bit.** Building the platform backend's image (repo-root
  `Dockerfile`) on this Windows laptop, `COPY app/mvnw ./app/` produced a
  file with no execute permission inside the Linux container — a real
  deploy's first Workbench acceptance run failed with `[Errno 13]
  Permission denied: '/repo/app/mvnw'` when the agent tried
  `run_controlled_compile`. Windows filesystems have no POSIX execute-bit
  concept, so there's nothing for Docker's build context to preserve;
  Linux containers need it explicitly. Fixed with an explicit `RUN chmod
  +x app/mvnw` immediately after each `COPY` that could touch that file
  (including after the later `COPY . .`, since a second copy of the same
  path can silently re-clobber the bit set earlier in the same build).
  Verified live: the exact same requirement that failed before the fix
  reached `NO_CHANGE_NEEDED` cleanly after redeploying with the fix.
- **Claude Code development telemetry was believed implemented because the
  hook handler itself passed tests, but the actual Claude Code
  configuration later contained no hooks — so fresh real sessions produced
  zero development events, silently, for at least two consecutive tasks.**
  Root cause, confirmed empirically (not guessed): Claude Code's own
  permission-remember mechanism — the thing that quietly appends a rule to
  `permissions.allow` whenever a tool action gets approved — rewrites the
  ENTIRE content of `.claude/settings.local.json` on every such grant, and
  that rewrite does not preserve unmanaged top-level keys. A `hooks`
  section placed there is silently dropped the very next time ANY
  permission gets auto-remembered, with no error, no warning, no log line.
  Proven by direct test: added a `hooks` key plus a marker key to
  `.claude/settings.local.json`, ran one ordinary novel command, and
  watched both disappear from the rewritten file — reproduced twice.
  `~/.claude/settings.json` (user-level, global) was tested the same way
  in parallel and was completely untouched across the same triggers — it
  is not managed by that rewrite path at all. **Fix: hooks configuration
  must live in the user-level settings file, never in
  `.claude/settings.local.json`** (which remains the right place for
  permission `allow` rules — that churn is its intended job, just never
  put anything else there that needs to survive). See
  docs/RECOVERY.md's "Recovering Claude Code development-telemetry hooks"
  and `agent/verify_claude_hooks_config.py` for the durable fix and its
  regression guard. **Permanent rule this incident established: a
  telemetry capability is verified only when the real producer emits an
  event and the durable remote store contains it — script-level tests
  passing is necessary but never sufficient proof of a live capability.**

- **A "TINY complexity" pre-run token estimate must not assume the agent's
  own investigation is cheap — real evidence shows it can dominate the
  total.** Problem: `agent/estimation.py`'s LOW-confidence fallback
  heuristic (used when fewer than 3 comparable historical runs exist)
  guessed 3,000-9,000 total tokens for a TINY/LOW auto-execute
  requirement. Evidence: the first real public acceptance run on a fresh
  Railway container (zero local history, so the heuristic path was
  exercised for real) made 3 real API calls and used 13,557 actual total
  tokens — 126% above the heuristic's own midpoint, outside the predicted
  range entirely — even though the run correctly reached `NO_CHANGE_NEEDED`
  or with zero code changes. Root cause: reading a real file
  (`app/src/main/resources/static/index.html`, ~5.9KB) plus a real `mvn
  compile` tool call already consumes several thousand input tokens
  before the model produces any output at all — investigation cost, not
  code-generation cost, dominates a small/no-op requirement. Correction:
  none applied yet — the estimate is explicitly labeled LOW confidence
  and ESTIMATED specifically so a miss like this doesn't mislead anyone,
  and the run's own `usage_summary.estimate_error` field records this
  exact miss for future recalibration. Future rule: when there is enough
  real history to widen `estimation.py`'s heuristic ranges (or split them
  by investigation-tool-call count rather than complexity label alone),
  do so from measured `estimate_error` data, not intuition — the labels
  TINY/SMALL describe the size of the *change*, not the size of the
  *investigation* needed to confirm it.

- **Spring Boot 4.1.1 renamed/relocated several classes commonly assumed
  stable from Spring Boot 3.x memory — verify against the real resolved
  dependency tree and jar contents, never assume.** Writing this
  project's first-ever Customer app tests, `com.fasterxml.jackson.databind.ObjectMapper`,
  `TestRestTemplate`, and `@AutoConfigureMockMvc` all failed to compile
  despite `spring-boot-starter-web` + `spring-boot-starter-test` being
  present. Root cause, confirmed via `mvn dependency:tree` and `jar tf`
  on the actual resolved jars (not guessed): Spring Boot 4.1.1 ships
  Jackson 3.x under a new `tools.jackson.*` package (only
  `jackson-annotations` remains under the legacy `com.fasterxml.jackson.core`
  groupId), and `TestRestTemplate`/`AutoConfigureMockMvc` are not present
  in any 4.1.1 jar resolved with just those two starters — Spring Boot
  4's module split appears to have moved or gated them behind a
  different/additional module not currently in this project's `pom.xml`.
  Correction: used `org.springframework.web.client.RestTemplate` (plain,
  always available via `spring-web`) + `@LocalServerPort` (confirmed
  present at `org.springframework.boot.test.web.server.LocalServerPort`
  via direct jar inspection) instead — avoids the uncertain module
  entirely. Future rule: when a "definitely available" Spring Boot test
  class fails to compile after a major-version bump, do not keep
  guessing import paths — run `mvn dependency:tree` and `jar tf` on the
  actually-resolved jars to find the real current location, or pick an
  alternative that doesn't depend on an unconfirmed module.

- **A display surface can silently drift from its own capture layer even
  after the capture layer is fixed — "not captured" and "captured but
  never wired to this display" look identical to a user.** Real incident
  (2026-09-11): `agent/dashboard_data.py`'s economics section was a
  static dict hardcoded to "NOT CAPTURED YET"/"NOT CALCULATED YET",
  written before `agent/pricing_config.py` and the real `run_usage_summary`
  event existed, and never updated afterward — even though real cost
  data (matching the Creator's own directly-observed example: 31,573
  input / 2,797 output tokens / 5 API calls) existed in the event ledger
  the whole time. A second, compounding bug made it worse: `run_usage_summary`
  events stored their real provider/model/token data only inside the
  JSONB `payload` column, never in the dedicated queryable columns other
  usage events use (`agent/web_server.py::_record_ledger_event` didn't
  know this event type carried that data) — invisible to any query
  selecting real columns directly, including the Usage page's own
  `get_recent_events()`. Correction: extended `_record_ledger_event` to
  populate real columns for `usage_summary` events; added
  `event_ledger.get_usage_economics()` as a genuine ledger-backed
  aggregation (last run / last hour / today / lifetime, using COALESCE
  so both pre-fix payload-only rows and post-fix column-populated rows
  aggregate correctly — no historical row lost or ignored); replaced the
  static dict entirely. Future rule: whenever a new event type is added
  to a generic write-through bridge, explicitly decide whether its
  fields need to be queryable as real columns, not just present in
  payload — "the data is captured somewhere" is not the same claim as
  "the data is captured somewhere any consumer can actually query."

- **"No test files exist" and "this kind of change cannot be tested" are
  different claims and must never share a label.** Real semantic bug:
  this project's Workbench labeled every real Java source change
  `TESTING — NOT APPLICABLE` purely because `app/src/test/java` had zero
  files — technically true about the files, but wrong as a quality
  policy, since the Customer app has real testable business logic. NOT
  APPLICABLE must mean the changed artifact genuinely has no test
  surface (e.g. a static HTML resource, which Maven's JUnit phase
  literally cannot exercise); the honest label for "testing should
  apply here but nothing is configured yet" is NOT_CONFIGURED — a
  project-level gap, not a settled correct decision. A third state,
  SKIPPED (real applicable tests exist but weren't run for this change),
  must block commit like a failure, since unlike the other two it's this
  run's own omission, not a pre-existing gap. Correction:
  `agent/web_server.py::_determine_testing_state` now decides from real,
  checkable facts (was a test tool actually invoked; does the changed
  path have any test surface at all; do test files exist anywhere in the
  project) rather than a single boolean. Future rule: when a "not
  applicable" label can be produced by two different real conditions
  with different implications (one benign, one an actionable gap), give
  them different labels — collapsing them hides the actionable one.
