# Session Record — Agentic Delivery Platform: Control UI, Dashboard, and the Security Lessons Behind Them

**Type:** development (building the product, not the product running against a real ticket)
**Scope:** spans multiple work periods culminating in this date's Control UI + Dashboard delivery. Exact historical start time, human active time, and token/cost are **NOT CAPTURED** — no instrumentation existed for those until this session (see "What is NOT captured" below). Durations below are the specific ones that WERE actually measured live.

This is a narrative index into real evidence, not a duplicate of it. Full
detail lives in docs/PROJECT_STATE.json (`verification_state`), docs/LESSONS.md,
docs/DECISIONS.md, and the Git history below.

## Goal / business reason
Three connected goals held throughout (see CLAUDE.md / docs/CONSTITUTION.md):
career evidence for real job applications, a genuinely trustworthy
requirement→verified-change delivery product, and eventual commercial
value. The operating rule throughout: perform only the prescribed duty,
verify before claiming, never let the agent approve its own writes.

## Architecture arc (commit-referenced)
1. **V1/V2** (`4ef1aef`, `943648e`) — ticket → plan via Claude API, then repository-aware static planning.
2. **V3** (`c40d1e8`) — controlled read-only tool-using agent: `list_repository_files`/`read_file`/`search_code`, strict tool-call budgets, thinking/tool_use round-trip.
3. **MCP + RAG** (`d312dd1`) — official `modelcontextprotocol/python-sdk` adapter delegating to `tools.py` (zero duplicated security logic); local fastembed + numpy semantic search as a 4th tool, content-hash incremental indexing.
4. **V4 write boundary** (`b724035`) — `write_tools.py` propose/approve/apply flow, scope-restricted to `app/src/{main,test}/java` `.java` files; `build_tools.py` allowlist-only Maven compile/test, no shell.
5. **V4.1 live execution** (`e90eb0c`) — `agent_loop.py` made generic (`tool_schemas`/`dispatch_fn`), wired the model to real propose/apply/compile/test tools while keeping approve/reject as plain Python functions never exposed to the model.
6. **Browser Control UI** (`11f4429`) — Starlette + Server-Sent Events; human Approve/Reject via a plain HTTP endpoint outside the tool surface. First genuine human-approved browser run reached VERIFIED SUCCESS.
7. **Evidence Dashboard** (`35889a0`) — `/dashboard`, sourcing only real state (PROJECT_STATE.json, the RAG index file, a small local run-history log, live metrics) — no fabricated values, gaps labeled `NOT CAPTURED YET`.

## Real security gaps found and fixed (not hypothetical — found via actual testing)
- **Secret-filename check only covered existing files.** `tools._resolve_safe_path` blocked secret-like filenames for files that already existed, but a *new* file with a secret-like name would have slipped through. Found via testing during the V4 write boundary work, fixed, re-verified. See docs/LESSONS.md.
- **Approval was a boolean, not bound to content.** Early design: `approve_edit()` set a flag; nothing stopped `edit.new_content` or `edit.path` from being mutated after approval and before apply. Fixed by hashing `(path, content)` at approval time and refusing apply if either changed — proven by `test_content_substitution_after_approval_is_rejected` / `test_target_substitution_after_approval_is_rejected`.
- **Exact-match vs. substring security verification.** A self-review found that an earlier test asserting "approve/reject not reachable" used substring matching, which could pass even if a differently-named path existed. Rewritten as exact set-membership (`test_approval_not_present_in_tool_schemas_by_exact_name`) — a lesson about not trusting your own security tests to be precise by default.
- **Non-interactive EOF must fail closed.** `input()` raises `EOFError` in a non-interactive environment; if uncaught, that's a crash, not a security property. `_default_approval_prompt` now catches it and returns `False` (reject) — verified both by unit test and by it actually happening live during a demo run with no human present.

## Real UI defects found through actual use (not code review — found by the creator using the product)
- **Scroll-jump after COMPLETED.** Root cause (found by code inspection, not assumed): `EventSource` was never explicitly closed on terminal state; a plain `EventSource` auto-reconnects on any dropped connection, and the backend's SSE generator naturally ending its loop counts as a drop — so the frontend replayed the *entire* event history on every reconnect, repeatedly re-triggering `scrollIntoView()`. Fixed with an explicit `eventSource.close()` on `COMPLETED`/`FAILED`, plus defense-in-depth (bounded/scrollable log, `overflow-anchor: none`, near-bottom-only auto-scroll).
- **Empty Build/Test panel + cosmetic-green banner.** Two separate bugs: the panel was never populated at all, and the final success/failure banner was decided by regex-sniffing the agent's free-text summary — which could go green even on a real failure. Fixed by adding a real `summary` field to `tool_result` events for the two verification tools (bounded, tail-biased real Maven output excerpt, not an invented test count), and deriving the banner from structured state (`approvalDecision`, `applySucceeded`, `compileResult`, `testResult`) instead of prose.

Both fixes were verified three ways before being trusted: code-level root-cause inspection, HTTP-level reproduction via a zero-API-cost mock run (`agent/web_server.py::_run_mock_thread`), and finally the creator's own in-browser visual confirmation (explicit "DASHBOARD VISUALLY VERIFIED" / prior Control UI confirmation messages).

## Real, measured durations (from actual live runs, not estimates)
- First real browser human-approved run: `mvnw compile` ~15.3s, `mvnw test` ~19.0s, both PASS.
- Full Python regression suite (`agent/test_*.py` via `python -m unittest`): 60 tests, 59 passed, 1 skip (Windows lacks symlink-creation privilege in this environment — a platform limitation, not a bug), 0 failed. Re-confirmed live multiple times this session with no regression.

## Fixture/artifact discipline lesson
The first browser-approved run created a real placeholder file
(`V41BoundaryDemoTest.java`) to prove the pipeline end-to-end. Once its
evidence value was captured in Git history and `docs/PROJECT_STATE.json`,
the creator explicitly approved deleting it from the Customer app —
runtime evidence belongs in Git/durable-state/tests, not as leftover
inert code in the target application. Verified post-delete: no residue,
`app/src/main/` diff empty, Update Email still unimplemented.

## What is NOT captured (be honest about this — do not infer)
- Exact historical wall-clock session start/end times before this record existed.
- Human active working time (never inferred from wall-clock — would overstate effort).
- Token usage and API cost for any run, historical or current — no instrumentation existed before this session; the Session Intelligence MVP (next) is the first attempt to capture this from the Anthropic API response itself, not from Claude Code's own UI counters (which are a different, unverified measurement).
- A monetary cost figure — deliberately not computed without a versioned, sourced pricing table.

## Portfolio/interview relevance
This session is the primary source for docs/EXPERIENCE_EVIDENCE.md. The
two most interview-worthy stories are (a) the approval-binding
substitution vulnerability found and closed by hashing `(path, content)`,
and (b) the SSE auto-reconnect scroll bug — both are concrete "describe a
bug you found and fixed" answers backed by real code and tests, not
hypotheticals.

## Addendum — Session Intelligence + first public deployment (same build day)
Commits `da50a4f` (Session Intelligence + value ledger), `2c370a2`
(checkpoint), `755f4f3` (public Dashboard/Sessions deployment). Full
architecture reasoning is in docs/DECISIONS.md rather than duplicated
here. Key facts:
- Real Anthropic API token usage is now captured directly from
  `response.usage` in `agent_loop.py` (never estimated) — implemented and
  regression-tested, but **not yet exercised by a real API call**, since a
  real Claude run was deliberately avoided today to save cost.
- Historical sessions are reconstructed from Git commit clustering
  (90-minute gap heuristic), labeled `RECONSTRUCTED FROM PROJECT
  EVIDENCE`, with real commit timestamps but `NOT CAPTURED` human/token
  data — this is a *lower bound estimate of session existence*, not a
  claim of exact working hours.
- First public URL: `https://agentic-software-delivery.vercel.app`
  (new Vercel project, existing `portfolio` project untouched) — a
  **static snapshot** of real Dashboard/Sessions data, not a live
  connection. The interactive Control Plane was deliberately NOT deployed
  publicly: Vercel serverless functions can't host the existing
  background-thread/SSE/in-memory-approval architecture, and more
  importantly, a public write boundary with real production-release
  authority does not exist yet (see CONSTITUTION.md — capability does not
  equal authority).
- The actual Spring Boot Customer app (Java 17, Spring Boot 4.1.1, H2
  in-memory) cannot run on Vercel at all (no JVM runtime). Railway was
  selected as the smallest-fit alternative (free tier, Maven
  auto-detection, no local Docker needed) but deployment is blocked on
  the creator's own one-time browser authorization of the Railway CLI —
  a device code was generated and handed to the creator; this agent
  cannot complete that step itself.
