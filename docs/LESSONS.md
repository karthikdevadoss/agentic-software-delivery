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
