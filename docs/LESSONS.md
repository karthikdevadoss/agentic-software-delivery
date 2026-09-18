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

- **Python's `zoneinfo` has no IANA tz database on stock Windows.**
  `ZoneInfo("Europe/Berlin")` raised `ZoneInfoNotFoundError` on this
  machine even though the stdlib module imported fine — Windows doesn't
  ship a system tzdata the way most Linux/macOS installs do. Fix: add the
  `tzdata` PyPI package (pure data, no compiled extension) as an explicit
  dependency wherever `zoneinfo` is used for anything beyond UTC/fixed
  offsets — don't assume `zoneinfo` "just works" cross-platform just
  because it's stdlib.

- **A "required evidence is missing" acceptance criterion is not
  automatically a genuine-uncertainty (UNKNOWN) test.** Distinguish
  criteria the evaluator can conclusively rule out (an artifact provably
  never existed, checkable via e.g. `git log --all` across full history)
  from criteria that are genuinely unreachable by any tool the evaluator
  has. Only the second category should produce UNKNOWN; the first is a
  well-evidenced FAIL, and a rigorous evaluator will correctly call it
  that. V2 Shadow Trial #3 tried to elicit UNKNOWN with a "human must
  have logged a browser-confirmation file" criterion; the qa-evaluator
  proved the file had never existed anywhere in history and correctly
  returned FAIL — the trial design conflated "missing" with "unknowable."
  See docs/ARCHITECTURE_V2_EVALUATION_PLAN.md's Trial #3 section and the
  Learn topic `evaluator-uncertainty-and-verdict-design` for the reusable
  framework.

- **Reusing an existing CSS badge class for a new, semantically different
  taxonomy silently conflates two different questions in the UI.** The
  first Learn Wikipedia implementation rendered `experience_classification`
  (CURRENT_PROJECT_EXPERIENCE/LEARNED_UNDERSTOOD/etc — "is this the
  Creator's own experience?") using the pre-existing `.ev-badge`/
  `.ev-runtime-verified` classes, which were designed for an entirely
  different taxonomy (`evidence_status` — "was this code verified to
  work?"). Both could appear on the same page with identical visual
  styling, making them indistinguishable even though they answer
  unrelated questions. General rule: when a new data field is
  conceptually a different taxonomy from an existing badge/status field,
  give it its own CSS class family from the start, even if the visual
  effect (a small colored pill) looks similar — never repurpose an
  existing status-badge style "because it looks about right," since the
  two meanings will drift apart in the reader's understanding the moment
  they appear together. Fixed by introducing a dedicated `.exp-badge`
  family plus an explicit legend on the Learn landing page (see
  `docs/UI_AUDIT_OPEN_ITEMS.md` and `agent/web/learn.js::expBadge`).

- **A missing `<meta name="viewport">` tag makes every other responsive
  CSS rule on that page ineffective, silently.** Discovered auditing
  Learn/Usage: none of this project's HTML pages had ever included a
  viewport meta tag, so mobile browsers render at desktop width and zoom
  out — any `@media (max-width: ...)` rule added without also checking
  for this tag will appear to do nothing on a real phone, and it's easy
  to misdiagnose as "the media query is wrong" instead of "the viewport
  isn't declared." Always check for `<meta name="viewport"
  content="width=device-width, initial-scale=1">` first, before writing
  or debugging any responsive CSS.

- **A named HTML entity inside reportlab `Paragraph` markup has no
  guaranteed PDF ToUnicode mapping — it can render visually correct while
  extracting as garbage.** Real defect found by an independent qa-evaluator
  pass on the Master Interview Book PDF (2026-09-12): `learn_pdf.py` used
  `&bull;`/`&middot;` for list bullets. Both displayed as the correct glyph
  when the PDF was opened visually, but text extraction was
  library-dependent: PyMuPDF decoded them as U+FFFD (165 occurrences),
  pypdf as a DEL control character — and the project's own existing
  mojibake regression test (`assertNotIn("�", text)`) missed it
  entirely because it only checked pypdf's specific decode path for one
  specific glyph. Fix: use the real literal Unicode character (`•`, `·`)
  directly in the Python source instead of a named entity — reportlab maps
  a literal character correctly regardless of which library later extracts
  it. Future rule: in any reportlab/PDF-generation code, only the three
  characters produced by an escaping function's own `&amp;`/`&lt;`/`&gt;`
  substitution should ever appear as named entities in markup passed to
  `Paragraph` — every other special character should be a real literal
  Unicode character, never a named entity, and a visual "it displays fine"
  check is not sufficient proof of correct extraction; verify with at
  least one independent text-extraction library, not just the one already
  used by the existing test suite. A cheap, durable guard for this class of
  bug is a static source-scan test asserting no other named entity appears
  in the generator's own source at all (see
  `agent/test_learn_pdf.py::test_no_named_html_entities_other_than_the_escaping_triad`).

- **A long content-generation task should checkpoint-commit-and-push
  BEFORE running expensive verification (QA/regression), not after —**
  the checkpoint's own bar is "internally consistent and deterministically
  regenerable," not "fully QA'd." Real operational lesson from resuming
  the Master Interview Book V1 task after a prior session hit its usage
  limit mid-task: a large body of genuinely good, mostly-finished work
  (interview_topics.py + 13 new domains) sat uncommitted across a session
  boundary purely because the previous session was still mid-verification
  when it ran out of quota. This session's explicit instruction (verify
  minimally -> commit+push -> THEN do the expensive QA/regression/deploy
  work) meant a second interruption at any later point could not have lost
  that work again. Future rule: on any task expected to span a real risk
  of a session/quota boundary, checkpoint (commit + push + independently
  verify `git fetch` shows local HEAD == origin) as soon as the work is
  internally consistent and minimally test-passing — treat the full
  independent-QA/deploy pass as a separate, later step that a checkpoint
  should never be blocked on.

- **A deployed container's own local git/filesystem state is not
  authoritative for "does the real deployed service need to change" —
  only the real deployed service's own live response is.** Real incident
  (JOB-SEARCH P0, 2026-09-12), found twice in the same feature before it
  shipped correctly: a "Reset Demo" operation first tried reading a
  canonical baseline from a git tag, which failed live because the
  deployed platform-backend container's Dockerfile deliberately
  `git init`s a fresh, disconnected local repo with no history/tags at
  all (a decision made in an earlier incident, before this feature
  existed). Fixed to read a baseline from a plain file — but the SAME
  container's own local *file* was then used as the go/no-go signal for
  whether a reset was needed, and this was independently proven false
  live: redeploying the platform-backend rebuilds that container fresh
  from this repo's own checkout (`COPY . .`), silently resetting the
  CONTAINER's local file to baseline, while the ACTUALLY DEPLOYED target
  service (a separate Railway service, only updated by its own explicit
  deploy command) still served the old, unreset content. A `git commit`
  in that same container then genuinely had "nothing to commit" — correct
  about that container's own repo, wrong as a signal that no action was
  needed. Both bugs were caught only by independently `curl`-ing the real
  live target service, never by trusting the operation's own report.
  Fix: any go/no-go or already-done check for a deployed target must ask
  that target directly (an HTTP fetch of its real content, a real status
  check) — never infer it from the state of the machine/container running
  the orchestration code, even when that state seems obviously related.
  Future rule: whenever an orchestrator and its deploy target are
  different processes/services with independently rebuildable state
  (a redeployable container driving a separately-redeployable app), any
  "is this already correct" decision must be answered by the target's own
  live behavior, and a "nothing to do" branch that skips deploy needs the
  same live-target check as the "did it work" branch that follows deploy
  — not a shortcut based on the orchestrator's own local state.

- **Never identify "the new deployment" by mere difference from a prior
  reference ID — verify recency/creation-time directly.** Real incident
  (WORKBENCH RELIABILITY P0, 2026-09-13): `wait_for_new_deployment()`
  originally captured a single "previous deployment id" before triggering
  a deploy, then polled `railway deployment list --json` for any entry
  whose id differed from it. This matched an OLD, unrelated deployment
  that had genuinely FAILED 46 minutes earlier (still present near the
  top of the recent-N list) and reported the whole pipeline as FAILED,
  even though the real new deployment had genuinely SUCCEEDED and the
  live Customer App was already correctly serving the new content —
  a false failure discovered only by fetching the raw run event payload
  (`GET /api/runs/<id>`, not the categorized session history) and
  cross-referencing it against `railway deployment list --json` by hand.
  Fixed by recording a real UTC timestamp immediately before triggering
  the deploy (`utc_now_iso()`) and filtering candidates by
  `createdAt > deploy_triggered_after_iso` (ISO 8601 UTC string
  comparison) instead of id inequality — "new" means "created after I
  triggered it," never "not equal to some earlier id I happened to note."
  This bug survived 3 earlier real production acceptance-run failures
  being misdiagnosed as other causes (unlinked deploy directory, then a
  missing content-verification retry window) before the raw event
  payload evidence exposed the real root cause — a reminder that each
  layer of plausible-but-wrong hypothesis should be checked against raw
  evidence before being treated as the fix, especially when a "fix"
  doesn't fully resolve the symptom.

- **A synchronous, real-DB-querying function called directly inside an
  `async def` Starlette/FastAPI route handler blocks the ENTIRE
  single-threaded event loop for EVERY concurrent request, not just its
  own — and a single orphaned "idle in transaction" connection can then
  cascade into a full-service outage.** Real incident (WORKBENCH
  RELIABILITY, 2026-09-13): shortly after a routine platform-backend
  deploy, `/api/dashboard` hung indefinitely, and — far more seriously —
  EVERY other route on the same service (including its custom domain)
  became simultaneously unreachable, even though `railway logs` showed a
  completely clean, error-free startup with no crash reported anywhere.
  Root cause, confirmed via a direct `pg_stat_activity` query (never
  guessed): one real Postgres connection had been sitting "idle in
  transaction" for 963 seconds, holding a lock that blocked every
  subsequent `ensure_schema()` DDL call (`CREATE INDEX IF NOT EXISTS` x5
  + one `ALTER TABLE`) — and nearly every code path in this project's
  event-ledger-backed modules calls `ensure_schema()` first. Every
  connection-opening function in `agent/event_ledger.py` already used
  `try/finally: conn.close()` correctly (audited during the incident, no
  Python-level leak found) — the most consistent explanation is a
  container killed mid-query during a deploy cutover, orphaning the
  connection on the Postgres side faster than Postgres's own default
  dead-peer detection notices it. Separately, `get_dashboard_data`/
  `get_sessions_data`/`get_session_history`/`get_session_detail` all
  called their real synchronous psycopg2-querying functions directly
  inside `async def` handlers, running them ON the asyncio event loop —
  meaning any one slow/stuck DB call (this exact incident, or just
  elevated latency under load) froze every OTHER concurrent request on
  the service too, plausibly also explaining the earlier, never-root-
  caused `PRODUCTION-TRANSIENT-502-OBSERVATION` (docs/ACTION_QUEUE.json)
  seen under concurrent Playwright load. Three-part fix, each
  independently valuable: (1) wrap every such handler's real work in
  Starlette's `run_in_threadpool` so a slow/stuck call can only ever
  block its own request; (2) set a real, server-enforced
  `statement_timeout` on the connection so a genuinely stuck query fails
  fast and honestly instead of hanging forever (sized with real margin
  over an empirically-observed ~12-17s worst case, not guessed); (3) set
  `idle_in_transaction_session_timeout` so Postgres itself kills any
  connection that becomes orphaned idle-in-transaction, regardless of
  what caused it. Future rule: any synchronous, potentially-slow I/O
  (a DB query, a subprocess call, a blocking HTTP request) inside an
  `async def` Starlette/FastAPI handler must be wrapped in
  `run_in_threadpool`/`asyncio.to_thread` — never called directly — and
  any long-lived DB connection pool this project owns should carry both
  a statement timeout and an idle-in-transaction timeout from the start,
  not added reactively after the first real outage.

- **Testcontainers 2.x renamed its Maven module artifacts, but not its
  Java packages.** `org.testcontainers:junit-jupiter` and
  `org.testcontainers:postgresql` (the pre-2.x coordinates many
  tutorials/memory still reference) became
  `org.testcontainers:testcontainers-junit-jupiter` and
  `org.testcontainers:testcontainers-postgresql` in the 2.x BOM Spring
  Boot 4.1.1 actually manages (`testcontainers.version=2.0.5`) — but the
  Java import paths (`org.testcontainers.containers.PostgreSQLContainer`,
  `org.testcontainers.junit.jupiter.Testcontainers`) are unchanged. Maven
  fails fast and clearly here ("version ... is missing") if you guess the
  old artifactId, so this is cheap to catch — just don't assume a
  library's Maven coordinates and Java packages rename together.

- **A CI environment (or any genuinely fresh checkout) will expose a test
  suite's implicit dependency on a gitignored, build-derived artifact
  that a long-lived dev machine quietly always has.** Two tests (one
  pre-existing, one new) failed in this project's first-ever GitHub
  Actions run — not because the code was wrong, but because
  `agent/.rag_index/` and `agent/.backend_rag_index/` (both gitignored,
  regenerated by running `agent/rag_index.py`/`agent/backend_rag_index.py`)
  had simply always existed on the one machine these tests had ever run
  on before. The fix is to make CI build every such artifact before
  running any test that needs it — never to loosen the test's assertion
  to tolerate "index missing" as if that were an equally valid outcome
  for a test whose entire point is verifying real retrieval.

- **Spring Boot 4 split `FlywayAutoConfiguration` out of the
  `spring-boot-autoconfigure` monolith into its own module,
  `org.springframework.boot:spring-boot-flyway`** — exactly like
  `spring-boot-hibernate`/`spring-boot-jdbc`/`spring-boot-jpa` (all
  directly observed via `mvn dependency:tree` once this was suspected).
  `flyway-core` + `flyway-database-postgresql` are the Flyway *library*
  only; without `spring-boot-flyway` as an explicit dependency, the
  `@Configuration` class that even reads `spring.flyway.enabled` is
  never on the classpath, so **no property value can matter, no matter
  which mechanism sets it.** This was the actual root cause behind THREE
  consecutive real GitHub Actions CI failures against a genuine
  Testcontainers Postgres instance (zero Flyway log lines, then
  Hibernate's `Schema validation: missing table [contract_plan]`) —
  confirmed conclusively only after decompiling the actual
  `FlywayAutoConfiguration` class bytecode
  (`javap -v ... | grep -A3 ConditionalOnProperty`) to verify the real
  `@ConditionalOnProperty(name=["spring.flyway.enabled"],
  matchIfMissing=true)` condition existed at all — it didn't, because the
  class wasn't present. Two earlier "fixes" (a separate
  `application-postgres.properties` file, then a single-file
  `#---`/`spring.config.activate.on-profile=postgres` multi-document
  form) both correctly diagnosed a symptom (`spring.flyway.enabled`
  seemingly not taking effect) but the wrong cause (profile-file
  precedence) — property precedence was never the problem; nothing was
  reading the property at all.
  **Compounding, separately real bug found while fixing this**: the
  single-file `#---` multi-document form, once Flyway autoconfiguration
  finally existed, caused `spring.flyway.enabled=true` from the
  postgres-only document to leak into the DEFAULT (no active profile) H2
  context too — plausibly `.properties` (unlike YAML) multi-document
  key overrides not being scoped by the activation condition the way
  expected, though not fully root-caused given the session's time
  budget. Reverted to genuinely separate profile files
  (`application.properties` + `application-postgres.properties`), which
  cannot have this specific failure mode by construction (a key in one
  file cannot leak into a different file's property source). **Lesson:**
  when a fast-moving framework's major-version release notes mention
  "modularized autoconfiguration" (Boot 4's actual, real change here),
  verify EVERY autoconfiguration-providing module you depend on is
  actually present as its own explicit dependency — do not assume a
  library dependency (`flyway-core`) implies its Spring Boot
  autoconfiguration glue comes along for free, and do not spend cycles
  debugging property precedence before confirming the consuming
  `@Configuration` class is even on the classpath (`mvn dependency:tree`
  plus, if still unsure, decompiling the actual class's conditions is
  cheap and conclusive — cheaper than three more guess-and-check CI
  cycles).

- **XML comments cannot contain a literal `--` anywhere in the body, not
  just at the boundaries.** Hit 3 times in one session editing
  `app/pom.xml`: a comment like `<!-- CORE modules only -- not the
  starter -->` fails Maven's POM parser with a "Non-parseable POM"
  error pointing at the *closing* `-->`, which is misleading — the real
  offending token is the earlier mid-comment `--` used as an em-dash
  substitute. Fix: never use `--` for punctuation inside an XML/HTML
  comment; use `:` or a real em-dash character instead. A single-line
  `grep -nE '\-\-[^>]'` is NOT reliable — it misses a `--` sitting at
  the very end of a line (the next character is on the following
  line, outside that grep match, which is exactly how this bit twice
  more in the same session after the check was first written). Check
  the whole comment body instead: `perl -0777 -ne 'for (/<!--(.*?)-->/gs) { print "VIOLATION\n" if /--/ }' pom.xml`.

- **The customer-app Railway service does not auto-deploy on `git push` —
  only `railway up`/`railway redeploy` actually ships new code.** Context:
  the Postgres production cutover (setting `SPRING_PROFILES_ACTIVE=postgres`
  via `railway variable set`) triggered a Railway "redeploy", which
  restarted the *existing built image* rather than rebuilding from the
  latest commit. Evidence: the restarted container logged the "postgres"
  profile as active yet still connected to `jdbc:h2:mem:customerdb` and
  found only 1 of the 3 real JPA repositories — proving the running image
  predated same-session commits (`f33e1a4`, `bc632aa`) by hours, even
  though `origin/master` was already up to date. Root cause: unlike the
  platform-backend (deployed via its own explicit `railway up` calls in
  `demo_execution.py`/`backend_execution.py`), the customer-app Railway
  service has no GitHub-push-triggered build configured — every prior
  customer-app deploy in this project's history was itself triggered by an
  explicit `railway up` call (a Workbench/backend-acceptance run or a
  manual one), never by pushing to GitHub alone. **Lesson:** before trusting
  that a production Railway service reflects the latest commit, check the
  deployment's own `createdAt` against the commit timestamp you expect it
  to contain — do not assume "the code is on `origin/master`" implies "the
  running container has it." A config-only change (env var, profile flip)
  can silently redeploy stale code if the last real build predates the
  feature depending on that config.

- **Raw GitHub Actions job logs require repo-admin authentication even on
  a public repository** — the REST API's log-download endpoint and the
  web UI's rendered log viewer both need auth this session did not have,
  which blocked diagnosing a real CI failure for a long chain of attempts.
  What IS readable anonymously: `GET /repos/{owner}/{repo}/check-runs/{job_id}/annotations`
  (the public Checks API) — but only what the workflow explicitly emits as
  `::error::`/`::warning::` commands. Fix: add a `if: failure()` step that
  greps `target/surefire-reports/*.txt` and emits their content as
  annotations (see `.github/workflows/ci.yml`) — this makes any future
  failure here self-diagnosable without needing log access at all.
  Two follow-on traps building that step, both worth remembering: (1) a
  literal-substring grep like `"FAILED|ERROR"` misses a pure assertion
  failure reported as `FAILURE!` (no "FAILED" substring) — parse the
  authoritative `Tests run: X, Failures: Y, Errors: Z` line instead; (2)
  when one test method's Spring context fails, EVERY subsequent method in
  that class repeats a generic "ApplicationContext failure threshold
  exceeded" cascade — neither a head nor a tail excerpt of the report
  reaches the real, first exception (tail only shows the repeated cascade
  from later methods; head is dominated by ~20 lines of Spring/JUnit
  framework frames before the first real `Caused by:`) — grep specifically
  for `Caused by:` lines instead.

- **Hibernate's `@Lob` on a `String` field validates as CLOB/`oid` on
  Postgres, not `TEXT`.** A Flyway migration declaring a text column as
  `TEXT` (the correct, idiomatic Postgres type for arbitrary-length text)
  will fail `ddl-auto=validate` schema validation against an entity field
  annotated `@Lob` — real error: "wrong column type encountered ... found
  [text (Types#VARCHAR)], but expecting [oid (Types#CLOB)]". `oid` is
  Postgres's legacy large-object reference mechanism, an entirely
  different thing from `TEXT`. Fix: use
  `@JdbcTypeCode(SqlTypes.LONGVARCHAR)` (Hibernate 6) instead of `@Lob`
  for a Postgres `TEXT` column backing a plain `String` field — `@Lob` is
  the wrong tool here regardless, since Postgres `TEXT` has no realistic
  size limit `@Lob`'s semantics would meaningfully add.

- **An always-on `@KafkaListener`/`KafkaAdmin` with no reachable broker
  does not "quietly retry in the background" — it can flood production
  logs badly enough that the hosting platform starts dropping messages.**
  Real incident, not a hypothetical: after deploying Kafka support with no
  real broker configured, Railway logged "rate limit reached for
  deployment... Messages dropped: 621". Two plausible-sounding property
  fixes were tried and both failed to actually solve it — proven by
  redeploying each and re-inspecting real logs, not assumed fixed from
  reasoning alone: (1) `spring.kafka.consumer.properties.reconnect.backoff.ms`
  governs reconnecting to an already-known broker node, not the
  "Rebootstrapping" cycle that fires when bootstrap resolution has NEVER
  succeeded; (2) `spring.kafka.admin.auto-create=false` stopped
  `KafkaAdmin`'s share of the noise but not the `@KafkaListener`
  consumer's own, independent reconnect loop (~1/sec, indefinitely). The
  actual fix was architectural, not another property:
  `@ConditionalOnProperty` on every Kafka-related bean (producer,
  consumer, admin config), gated behind an explicit flag defaulting to
  `false`, so nothing even attempts to connect until the operator
  explicitly turns Kafka on alongside a real broker address. **Lesson:**
  for an optional broker/queue dependency with no guaranteed availability
  in every environment, gate the whole client subsystem behind an
  explicit enable flag rather than trying to tune a specific client's
  internal retry cadence from the outside — the exact internal mechanism
  governing "no node has ever been reachable" retries is not always the
  same one covered by the client's documented backoff properties, and
  guessing which one it is costs real debugging cycles for no guarantee.

- **`railway up`'s build context/Dockerfile depends on the shell's
  current working directory, and this repository has two independent
  Dockerfile-vs-Railpack build setups that can silently swap.** Context
  (2026-09-14, RESUME-AFTER-QUOTA session): running
  `railway up --service agentic-delivery-customer-app` from the repo
  root deployed successfully (no error at upload time) but the resulting
  deployment CRASHED with `ANTHROPIC_API_KEY is not set` — the wrong
  application entirely. Root cause, confirmed via
  `railway deployment list --json`'s `meta.serviceManifest.build`: the
  repo root has its own `Dockerfile` (built for the unrelated Python
  `agentic-platform-backend` service), and Railway silently prefers a
  Dockerfile it finds in the uploaded build context over that service's
  own already-configured Railpack (Maven/Java auto-detect) builder — no
  warning, no confirmation prompt, and the CLI's own "Uploading..."
  output gives no indication anything is wrong. There is no `Dockerfile`
  under `app/`, so running the identical command from inside `app/`
  correctly uses Railpack and succeeds. **Lesson:** in a repo with more
  than one deployable service and more than one build mechanism, always
  `cd` into the exact directory that service's *correct* build context
  requires before running `railway up`, and always check
  `railway deployment list --json`'s real status (not just the CLI's
  upload-time output) after every deploy — a build that starts without
  error is not evidence it built the right thing.

- **An LLM-facing "list files" tool's display truncation cap silently
  becomes a data-loss bug the moment something else reuses it for
  exhaustive enumeration.** Context (2026-09-14, PORTFOLIO COMPLETION
  PUSH session): `agent/rag_index.py`'s whole-repo indexer called
  `tools.list_repository_files()` to enumerate what to index — the same
  function the V3 CLI agent calls to show the model a directory listing,
  which intentionally truncates to `MAX_FILES_LISTED = 200` entries
  (alphabetically sorted) to protect the agent's token budget. Once this
  repository genuinely grew past 200 indexable files, the RAG index
  silently stopped indexing everything sorted after position 200 — a
  real, live gap in the whole-repo index, not just a test artifact,
  discovered only because `agent/test_rag_index.py`'s fixture file
  (`docs/_test_fixture_rag.md`) happened to fall past that cutoff and 4
  of its tests started failing (`files_added`/`files_changed`/
  `files_deleted` stuck at 0, and `semantic_search` on a distinctive
  fixture string returned `P0_PROMPT.txt` instead — a real repo-root file
  that alphabetically sorts earlier). **Lesson:** a function whose
  contract includes "truncate for display/budget reasons" must never be
  reused by a caller that needs a complete, correct enumeration —
  factor out the untruncated walk as its own function
  (`tools.list_repository_files` now delegates to a shared
  `_walk_repository_files` helper, and `tools.list_all_repository_files`
  exposes the untruncated result for internal callers like RAG indexing)
  rather than parsing the truncated, human-formatted string and hoping
  the cap is never actually hit in practice.

- **A test's own broad substring assertion can start failing for a
  reason that has nothing to do with the code under test.** Same
  session: `test_env_and_git_and_target_never_indexable` asserted
  `".git" not in f` for every indexed file path — which correctly caught
  real `.git/` internals when the repo was smaller, but started
  false-failing once `.github/workflows/ci.yml` (a real, legitimately
  indexable file added by an earlier CI task) matched the same bare
  substring. The actual security boundary (`.git` directory exclusion in
  `tools.BLOCKED_DIR_NAMES`) was never broken. **Lesson:** when a test
  asserts "X is never present," match the real boundary being tested
  (a path segment, a directory prefix) rather than a bare substring that
  can coincidentally match an unrelated, legitimate future filename.

- **A "self-test against the real baseline file" that actually reads a
  separately-committed COPY of that file, not the file itself, can drift
  silently for a very long time -- and if that same copy also backs a
  real production "restore to baseline" feature, the blast radius is not
  just broken tests.** Context (2026-09-14, PORTFOLIO COMPLETION PUSH
  session, discovered while wiring the USER/ADMIN login gate into
  `app/src/main/resources/static/index.html`): `agent/demo_catalogue.py`
  defines 5 deterministic public-demo operations, each with a regex
  anchor into that exact file, and runs a `_self_test()` at import time
  whose own docstring says it checks anchors "against the REAL baseline
  file" -- but it actually reads `agent/demo_baseline/index.html`, a
  separately-committed fixture copy. That copy still held the project's
  very first "Find Customer / Create Customer" page from early sessions
  (`find_customer_ui`/`create_customer_ui`, commit `a979075`) -- the real
  file has been completely redesigned multiple times since (Overview/
  Profile/Plan/Preferences/Appointments cards, then a login gate), and
  nothing ever kept the two in sync. Result: 3 of 5 publicly-advertised
  demo operations (`find_button_label`, `create_button_label`, and
  `heading_text`'s badge-span anchor) had been silently unusable for a
  long time -- a recruiter clicking those exact suggested examples on the
  live public Workbench would hit "anchor pattern did not match — refusing
  to guess," an honest failure (the fail-closed design worked as intended)
  but still a broken advertised feature nobody had caught. WORSE: the
  same `agent/demo_baseline/index.html` file is also
  `web_server.py`'s `DEMO_BASELINE_FILE` -- the literal content the real
  "RESTORE PRODUCTION BASELINE" button on the public Workbench writes
  back to production. Had that button been clicked before this was found,
  it would have overwritten the live Customer App with the ancient
  Find/Create-Customer page, silently destroying the real Postgres-backed
  Overview/Profile/Plan/Preferences/Appointments/login functionality in
  production. **Fix:** refreshed `agent/demo_baseline/index.html` to be
  an exact copy of the real, current file (closing both gaps with the
  same edit, since both consumers legitimately want "the current
  canonical state" and a single shared file is the right design as long
  as it's kept in sync); retargeted `heading_text`/`subtitle_text`'s
  anchors onto stable `id="app-heading"`/`id="app-subtitle"` elements
  (the redesigned page now has two `<h1>`/`class="subtitle"` elements --
  login view and post-login app view -- so a bare-class/tag anchor is
  ambiguous); retired `find_button_label`/`create_button_label` entirely
  rather than inventing UI to match, since no find/create-customer flow
  exists in the current single-workspace-per-persona architecture. **The
  generalized lesson:** when a self-test's own purpose is "verify against
  the real/live artifact," make sure it actually reads that artifact
  (or the artifact IS the fixture, with no second copy to fall out of
  sync) -- a fixture that is *supposed* to mirror something real but is
  maintained by hand will eventually stop mirroring it, and nothing will
  say so until a human notices by accident, which may be well after a
  real, disclosed production feature has been quietly built on top of the
  stale copy. Prefer a single source of truth over "two things that
  should always match."

- **JPQL `LOWER(x) LIKE LOWER(CONCAT('%', :param, '%'))` can work fine on
  H2 and still fail on real PostgreSQL with "function lower(bytea) does
  not exist" -- a genuine, real PRODUCTION 500, not a hypothetical.**
  Context (2026-09-14, PORTFOLIO COMPLETION PUSH session, building the
  ADMIN "All Customers" search/pagination endpoint): the full local test
  suite (H2) passed cleanly, but the first real curl against live
  production's `GET /admin/customers?name=...` returned a real 500 --
  `org.postgresql.util.PSQLException: ERROR: function lower(bytea) does
  not exist`. Root cause, confirmed via real Railway logs
  (`railway logs`), not guessed: PostgreSQL's JDBC driver could not infer
  a concrete type for a nullable String bound *through* Hibernate's
  `CONCAT` translation (rendered as `'%'||?||'%'` in the real generated
  SQL) and defaulted the parameter to `bytea` -- a real Postgres/pgjdbc
  parameter-type-inference gap this project's H2 profile has no
  equivalent for, so nothing local could have caught it. **Fix:** never
  wrap a bind parameter itself in `CONCAT`/`LOWER` inside the query --
  pre-build the full, already-lowercased `"%value%"` LIKE pattern in
  Java and bind it as a plain String parameter instead
  (`CustomerRepository.searchWorkspaceCustomers`'s `:namePattern`/
  `:emailPattern`, built by `AdminCustomerController.likePattern()`).
  **The generalized lesson, again reinforcing an existing one in this
  file:** a green H2-only test suite is not proof a JPQL query works on
  the real target database -- any query using string functions
  (`LOWER`, `CONCAT`, `LIKE`) around a *nullable* bind parameter needs a
  real Postgres check (this project already has the machinery for this:
  `PostgresFlywayIntegrationTest`, a real Testcontainers-backed class --
  a regression test was added there, `adminCustomerSearch_byNameAndEmail_
  worksAgainstRealPostgres_notJustH2`, so CI's real Docker runner proves
  it going forward even though this dev machine has no local Docker to
  verify it before every push). Found and fixed via direct production
  verification within minutes of the bad deploy (curl -> railway logs ->
  root cause -> fix -> redeploy -> re-verify), not left for a recruiter
  to discover.

- **The first genuine end-to-end run of a real, previously-untested AI
  pipeline is exactly when its accumulated untested assumptions surface
  -- three real, independent bugs, in three different layers, all
  found in the SAME first live run of `agent/backend_acceptance.py`
  (2026-09-14, Priority 4's "ONE REAL END-TO-END AI BACKEND DELIVERY
  RUN").** This ACT-008 internal pipeline (real MCP/RAG context
  retrieval, a real Claude LLM planning call, real `mvnw compile`/
  `test`, real git commit, real Railway deploy, real production
  assertion, real restore) had been *built* and unit-tested across
  several prior sessions, but never actually *run* for real end to end
  -- each of these three bugs was invisible to every existing test
  because each test mocks exactly the boundary the bug lived in.
  1. **Auth boundary drift.** `backend_acceptance.py`'s own `_fetch()`
     never attached an Authorization header -- correct when it was
     written (this scenario predates JWT security entirely), silently
     wrong once a *later* session added Spring Security JWT to every
     `/customers/**` endpoint. First real run: instant, clean 401 at
     Step 1's baseline check -- caught before anything was cloned,
     committed, or deployed, exactly the fail-closed behavior the
     baseline check exists for. Fix: fetch a real anonymous demo JWT
     (`POST /auth/demo-token`) and attach it.
  2. **Local clock trust.** `demo_execution.utc_now_iso()` trusts this
     dev machine's own system clock for `deploy_triggered_after_iso`,
     which `wait_for_new_deployment()` compares against Railway's own
     (accurate) `createdAt` timestamps. This exact machine's clock was
     independently confirmed running ~6.5 minutes AHEAD of true UTC
     (cross-checked against two unrelated external HTTP Date headers).
     Because the comparison is `created_dt > trigger_dt`, an
     artificially-advanced local trigger time makes every genuinely-new
     deployment look like it was created "before" the trigger --
     permanently, for the entire 900s wait, no matter how long you
     wait, since the skew never closes. Two consecutive real runs both
     reported TIMEOUT after the full 15 minutes even though the real
     deploys had genuinely succeeded on Railway's side in under 3
     minutes each (independently confirmed via `railway deployment
     list` by id, and via direct production content checks -- the probe
     value was genuinely live in production for a period neither this
     script nor its own operator would otherwise have known about
     without manually checking). Fix:
     `demo_execution.server_verified_now_iso(reference_url)` reads the
     real HTTP `Date` response header from a live Railway-hosted URL
     instead of the local clock, falling back to the old behavior (with
     a printed warning) only if that network call itself fails. Applied
     to all three real call sites (`backend_acceptance.py` and both of
     `web_server.py`'s real trainer/reset deploy paths), not just the
     one that happened to expose it -- the deployed container's own
     clock is presumably accurate (a real cloud VM with NTP), but
     "presumably" is exactly the kind of assumption this whole incident
     argues against trusting silently.
  3. **No cutover retry window.** Immediately after
     `wait_for_new_deployment()` correctly confirmed a real SUCCESS
     (fix #2 made this fast -- ~60s instead of a false 900s timeout),
     the very next content assertion hit a real, transient HTTP 502
     ("Application failed to respond") from Railway's own edge --
     Railway's traffic cutover to the new container, plus this app's
     own real ~25-30s Spring Boot startup (Flyway validate + Hibernate +
     Actuator), hadn't finished yet. This is the EXACT SAME real gap
     `web_server.py`'s `_verify_content_with_retry` already solved for
     the static demo path (see its own docstring, 2026-09-13) -- this
     internal ACT-008 script simply predates that fix and never
     inherited it. A single-shot check reported a false FAILED for a
     deploy that, independently re-verified moments later via a fresh
     curl, was already serving the exact correct content. Fix:
     `backend_execution.assert_production_field_with_retry()`, the same
     bounded-retry-only-when-identity-was-confirmed pattern, reused
     rather than re-invented.

  **The generalized lesson:** unit tests that mock the network/clock/
  filesystem boundary a real bug lives in will never catch that bug,
  no matter how many of them exist or how long they've been passing --
  the actual first live run of a real pipeline is not optional
  verification theater, it is the only test that exercises the
  assumptions every mock quietly encoded. None of these three bugs
  were hypothetical or found by inspection; all three were found
  because the pipeline was actually run for real, against real
  production, and its real behavior was independently cross-checked
  (curl, `railway logs`, `railway deployment list`) rather than trusted
  from the script's own self-report -- which is exactly why the
  script's own final verdict said FAIL twice in a row while the
  underlying delivery (LLM analysis, compile, test, commit, deploy,
  content change, restore) had already genuinely succeeded both times.
  "AI does not certify its own work" applies here too: the tool's own
  PASS/FAIL banner was the least trustworthy signal in the room.

- **This specific dev machine genuinely runs low on free RAM (observed
  as low as 1.7GB free of 15.8GB total) during a long session with many
  browser/Chrome-automation tool calls plus a real `mvnw test` (a full
  embedded Spring Boot context: Tomcat, Hibernate, Flyway, Actuator) --
  the OS/harness killed the `backend_acceptance.py` process outright
  (not a Java-level OutOfMemoryError) at that exact phase in 2 of 3
  attempts in the same session (2026-09-14).** Not a bug in the
  pipeline itself (a full run DID complete successfully once memory
  allowed it, with `MAVEN_OPTS=-Xmx512m` set to reduce the JVM's own
  footprint) -- a real, reproducible resource ceiling on this
  particular environment when a long, browser-heavy session and a real
  Maven+JVM test run compete for memory at the same time. **Lesson:**
  before running anything that spawns a real JVM test process
  (`mvnw test`, not `mvnw compile` alone -- compile succeeded every
  single time, only the full Spring context boot under test ever hit
  this), check free memory first (`Get-CimInstance Win32_OperatingSystem`
  on Windows) and set a conservative `MAVEN_OPTS=-Xmx512m` (or similar)
  proactively rather than reactively after a kill -- and if a kill
  happens anyway, the right response is to verify the real external
  state (here: production content, via direct curl) before assuming
  anything was left inconsistent, since a mid-test-phase kill in this
  pipeline's design happens before any commit/deploy step ever runs.

- **The platform-backend Railway service does not auto-redeploy on
  `git push` -- it only redeploys when something explicitly runs
  `railway up` against it -- so a run of docs-only or Python/agent-only
  commits (no reason to touch the live orchestration server) silently
  leaves the DEPLOYED image further and further behind
  `origin/master` with every such session, even though the *repo* is
  fully up to date. Found live (2026-09-15): the deployed Dashboard was
  20 commits behind HEAD (still serving a `dd3b762`-era build), so it
  was actively telling recruiters that USER/ADMIN login and the ADMIN
  dashboard "are genuinely not yet built" -- both of which had been
  real, live, production-verified features for at least a day. Nothing
  in this project's own regression/verification tooling checks
  *deployed-commit distance from HEAD*; every existing check verifies
  "is the currently-deployed thing internally consistent/healthy," not
  "is the currently-deployed thing the CURRENT thing." Compounding
  this: `docs/PROJECT_STATE.json`'s own `next_phase`/`next_action`/
  `last_verified_code_commit` fields (which the Dashboard reads
  directly, unmodified, at request time -- not a cached/hardcoded
  Python constant) had themselves gone stale in the committed repo,
  last edited in an earlier session and never updated across 6
  subsequent commits that added real capability (RBAC/interview-scenario/
  AI-docs work) -- so even a fresh redeploy would still have shown a
  stale narrative until that file's own content was corrected too.
  **Lesson: staleness has two independent layers that must both be
  checked -- (1) is the deployed container's code actually built from
  a recent commit (compare the running service's own reported commit
  to `git log --oneline <that-commit>..HEAD | wc -l`), and (2) is the
  CONTENT of any human-readable summary file the Dashboard surfaces
  (PROJECT_STATE.json's narrative fields, not just its structured
  `completed_capabilities` list) actually current, not just present.**
  A session that adds real capability should end by asking both
  questions, not just "did my new commit compile and pass tests."

- **A generated artifact's own `generated_at = datetime.now()` stamp
  makes every regeneration dirty the working tree even when nothing
  substantive changed, and worse, invites a reader to treat "when this
  file was built" as "when its facts were last true."** Found in
  `agent/generate_claude_context_bundle.py` (and the private
  `karthik-ai-context` repo's identical-pattern generator): both wrote
  wall-clock `generated_at` into the committed snapshot and manifest on
  every run, so re-running the generator with zero source changes still
  produced a diff, and nothing distinguished "bundle regenerated today"
  from "these fast-changing facts (Git HEAD, blockers, action queue) were
  actually re-verified today." Fixed by deriving provenance entirely from
  the source repository's own git state instead of wall-clock time:
  `source_repository_head_sha` + that commit's own `%cI` timestamp +
  a `source_working_tree_clean_at_generation` flag. Two regenerations
  against the same committed HEAD with a clean tree are now
  byte-identical, and every fast-changing (`current`/`historical`
  classified) section is explicitly captioned "last recorded as of
  source state HEAD `<sha>`," never presented as re-verified just because
  the bundle was rebuilt. General rule: **when a generator's timestamp
  exists only to prove reproducibility/provenance, derive it from the
  source's own version-control identity, not `datetime.now()`** —
  wall-clock "now" is almost never the fact you actually want to assert.

- **A "content verified in production" claim can be genuinely, mechanically
  true and still mislead the person reading it, if the app has more than
  one client-side view-state and the claim doesn't name which one it
  checked.** Found in `agent/demo_catalogue.py`'s `heading_text`/
  `subtitle_text` operations (AEQ-025): the extraction regex correctly,
  narrowly targeted one `id`'d element in the login view, and the
  verification retry loop correctly confirmed that exact element's new
  value in the real deployed HTML — no bug in the mechanism itself. The
  gap was that `human_name` ("the main heading text") described a
  broader scope than the anchor could ever reach, and every Owner-facing
  claim string in `web_server.py` was templated straight from that one
  field. Once the app grew persistent authenticated USER/ADMIN sessions
  with their own separately-hardcoded heading text, "the main heading"
  quietly stopped being true for the common (logged-in) case, with
  nothing forcing a re-check of that claim's wording as the app evolved
  around it. General rule: **a verification claim's own wording is part
  of the thing that can go stale, independent of whether the mechanism
  behind it is correct** — when a target app gains new view-states,
  audit not just "does the check still pass" but "does the English
  description of what was checked still match reality."

- **A function that bridges into a real, shared, durable system (a
  production database, an external API) via a process-global sink/
  callback must gate on "was this call genuinely real," decided before
  any test-injection point reassigns the thing under test — not on the
  mere shape/truthiness of a response object, which a test double can
  satisfy just as easily as a real one.** Found in
  `agent/reasoning_gateway.py` (AEQ-028): `call()` recorded token usage
  from any object with a truthy `.usage` attribute, never checking
  whether `create_fn` had been injected by a caller (which this
  function's own docstring already documented as "never omitted in a
  real automated test"). `web_server.py` wires `metrics.py`'s usage sink
  to the real production event ledger as a bare module-level import-time
  side effect — so any process where `web_server` happens to get
  imported (e.g. `test_web_server.py` loading during a full
  `python -m unittest discover` run) silently armed that sink for every
  *other* test file's mocked model call in the same process, for the
  rest of that process's life — `test_web_server.py`'s own
  `ActualUsageSummaryTestCase` (hand-written fake `record_model_usage()`
  calls, testing aggregation logic directly) turned out to be a *second*,
  independent leak into the same sink, found only by re-querying after
  the first fix and noticing the fake-row count kept climbing. Result:
  119 of 314 real production `model_usage` rows (38%) were fake test
  noise, dating back at least 4 days, discovered only because a human
  noticed a suspiciously repeated 10/20-token pattern on the live Usage
  page. **General rule:** when wiring a process-global side effect that
  reaches a real external system, the thing that decides "is this the
  real path" must be captured at the point of injection, not inferred
  later from what the response looks like — fixing one call site's
  version of this bug does not prove no other call site has the same
  bug; the real fix here was making the shared *test-reset* function
  (`metrics.reset()`) also clear the sink, so every test that already
  calls it (an established, common pattern) is protected regardless of
  which other test files happened to import first. A vague "the numbers
  look wrong" report from a human is worth tracing all the way to the
  data layer, not just the display layer that happens to surface the
  symptom.

- **A slug/identifier that recurs N times across a tree must be checked
  N times individually before batch-applying new content to it — a
  duplicate does not mean "N shallow nodes needing the same treatment";
  it can mean one real collision needing a fix and one node that's
  already correctly deep.** Found twice while batch-authoring
  `agent/web/learn-tree.json` content via a one-time enrichment script
  (`enrich_learn_tree.py`, since deleted): first, `indexing` existed
  under both `System Design > Databases` (real B-tree indexing) and
  `RAG` (corpus indexing) — a slug-keyed (not domain-scoped) merge
  overwrote the real database-indexing content with RAG content. Fixed
  by adding a domain-scoped enrichment key (`(domain_title, slug)`).
  Second, deeper case: `production-verification` appeared twice *within
  the same domain* (`System Design > Reliability` and `System Design >
  Cloud-Deployment`) — a later internal-duplicate-slug sweep correctly
  found both instances but wrongly assumed *both* needed new content;
  the `Reliability` one was already a real, pre-existing 9-section
  deep-dive (with `development_steps`/`failure_modes`) that had simply
  never appeared in the original shallow-topics list, and a
  domain-scoped (not path-scoped) write clobbered it with thinner
  content. Caught only by the test suite itself
  (`test_deep_dive_topics_preserved_with_full_sections` failing,
  expecting `development_steps`) — not by inspection, since the diff
  looked like ordinary content addition. **General rule:** before
  writing new content to ANY node found via a duplicate-slug search,
  check that specific node's *current* section count/richness first —
  a slug collision is a signal to investigate each instance
  individually, never a license to treat every instance as needing the
  same fix. Domain-scoping (or even finer, path-scoping by parent
  subdomain) prevents the write from leaking to the WRONG node, but
  does not by itself prove the RIGHT node was actually shallow to begin
  with — that still needs a real, current read before every batch
  write, and a regression test with unusually literal assertions (here,
  "does this specific field exist") is what actually caught the
  second, subtler instance of this same mistake.

- **`git stash`ing real, tested, uncommitted work to switch to a
  higher-priority task is the correct move — but the stash itself is
  not a durable record, and nothing else pointed to it.** A prior
  session had a real, working, fully-tested GraphQL feature (schema,
  controller, exception resolver, 6 passing integration tests) on
  branch `feature/graphql-api`, uncommitted. A higher-priority
  production incident (AEQ-028) came in; the session correctly ran
  `git stash -u` (capturing the untracked new files too, not just
  modified tracked ones) rather than losing the work or blocking the
  urgent fix, switched branches, and fixed the incident. The stash was
  never popped afterward, and — critically — no durable artifact
  (`docs/ACTION_QUEUE.json`, `PROJECT_STATE.json`'s `next_action`, even
  a one-line note) recorded that it existed. When the next session
  resumed after a context compaction, its only source of truth about
  the GraphQL work was the compacted conversation summary's own
  narration — which was accurate about *what* had been built, but the
  actual proof of *where it currently lived* (a specific stash entry,
  on a specific branch, findable only via `git stash list` /
  `git reflog`) was never durably written anywhere a fresh session
  would naturally check. The next session initially reported the work
  as **lost** — wrong, and only caught because the user pushed back
  ("so strange") — because it checked `git log`/the working tree on
  `master` and stopped there, never running `git stash list`. **General
  rule:** `git status --short` and `git log` are NOT a complete picture
  of repository state — before ever reporting real, previously-described
  work as missing, also check `git stash list`, `git branch -a`, and
  `git reflog` (see the Session-startup checklist above, which only
  names `git status --short` and `git log -5 --oneline` — read as the
  *minimum*, not the complete forensic checklist, whenever something
  described earlier appears to be missing). And going forward: any time
  substantial uncommitted work is stashed to context-switch to a more
  urgent task, immediately record a one-line pointer to it (the stash
  message, the branch, what's in it) in `docs/ACTION_QUEUE.json` or
  `PROJECT_STATE.json`'s `next_action` — the stash preserves the bytes,
  but only a durable, indexed pointer makes it findable without manual
  git archaeology, especially across a context-compaction boundary
  where the next session has no memory of having stashed anything at
  all.

- **Running multiple model-heavy background agents in parallel "to get
  more done while the Owner sleeps" multiplies real spend rate, not just
  wall-clock throughput — treat parallelism as a deliberate cost decision,
  not a default.** Real incident: two heavy forks (one doing an extensive
  real multi-source web-research pass, one doing large multi-file backend
  implementation with repeated test runs) were launched simultaneously
  after an instruction to "use the full session without waiting for
  approval." One failed on a rate limit, the other on a real monthly
  spend limit — a genuine, non-trivial amount of real money, on an
  account that had to be upgraded mid-session to continue. Both forks'
  in-progress work was safely recovered (nothing was lost — checked out
  each worktree, ran its real test suite, completed one missing test file
  the failed fork hadn't gotten to yet, then committed/pushed) — but the
  spend itself was real and avoidable. **General rule:** "use the full
  session autonomously" is an instruction about not stalling for routine
  approval, not an instruction to maximize parallel model-heavy work by
  default — before running more than one expensive agent at once, the
  real question is whether parallelism materially reduces total
  time-to-verified-outcome enough to justify multiplying token/cost
  consumption, not merely "can this be done faster in parallel." See
  CLAUDE.md's Human-AI Engineering Operating Policy for the standing rule
  this incident produced.
