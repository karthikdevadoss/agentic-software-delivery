# Workbench Reliability Gap Analysis (2026-09-13)

Written per the Owner's explicit PHASE 1 instruction, from a forensic
inspection of the CURRENT source/tests/production state — not from prior
documentation or prior session claims. Baseline commit: `557d0f9`
(HEAD == origin/master, working tree clean at the start of this task).

## Current truth, verified fresh this session

- `python -m unittest discover` (agent/): **284 tests, 283 pass + 1
  pre-existing platform skip** — actually run, not recalled.
- All 6 public routes + Customer App: HTTP 200, verified via direct curl.
- Customer App content: byte-for-byte identical (line-ending normalized)
  to `app/src/main/resources/static/index.html` — genuinely at baseline.
- `/api/trainer/reset` status: idle.

## Full pipeline trace (as the code actually is today, not as documented)

| Stage | Component | Inputs | Outputs | Failure states | Existing tests | Gap |
|---|---|---|---|---|---|---|
| Authorization/scope | `risk_policy.classify()` (text keyword/complexity heuristic) | raw requirement string | `{decision: auto\|blocked, ...}` | none (never raises) | `test_risk_policy.py` incl. 9-prompt adversarial regression | **Not a request contract** — no operation type, target, or expected-verification-method is derived here; it only answers yes/no on the raw text. A "safe-sounding" freeform requirement (e.g. "reword the subtitle to be catchier") still reaches the full agentic investigation path. |
| Requirement normalization | **does not exist as a distinct stage** | — | — | — | — | Real gap named directly in this task: no structured `{operation, target, new_value}` contract exists anywhere. The LLM interprets AND effectively decides scope by whichever file it chooses to call `propose_source_change` against (bounded only by `write_tools.ALLOWED_WRITE_PREFIXES`, a coarse directory allowlist, not a per-field contract). |
| Workspace acquisition | `_check_repository_workspace_ready()` | `REPO_ROOT` (the platform-backend's OWN long-lived checkout) | ready/not-ready | git not usable | `RepositoryWorkspaceReadyTestCase` | **The trainer thread mutates the same live checkout the running server process itself was started from.** No isolation between "the server's own files" and "a demo run's workspace." A partially-failed commit, or two logically-adjacent runs, share one mutable directory. |
| Impact/change selection | `run_agent_loop()` (real Claude tool-calling agent) with `execution_tools`' read/write/build tools | requirement text, full repo (read-only tools) | a proposed diff via `propose_source_change` | agent proposes nothing; agent proposes an unintended file/region | `test_agent_loop.py`, `test_execution_tools.py` | Verified via existing tests that the *tool surface* is bounded (approve/reject not model-reachable, write scope enforced by `write_tools.py`). NOT verified anywhere: that the *content* of an approved edit only touches the field the requirement actually asked about — an LLM could correctly target `index.html` but rewrite unrelated lines too, and nothing catches that (no Layer-3 diff-purity test exists today). |
| Implementation | `write_tools.propose_edit/apply_edit` | path + new full file content | file written to `REPO_ROOT` | scope/extension rejection | `test_write_tools.py` (17 tests, incl. this session's adversarial-path regression) | Solid. |
| Testing-state | `_determine_testing_state()` | changed path, test_events | PASSED/FAILED/NOT_APPLICABLE/NOT_CONFIGURED/SKIPPED | — | `DetermineTestingStateTestCase` (8 tests) | **Fixed last session** (ordering bug: static-resource check now runs before the project-wide "any test file exists" check). Regression-tested. Confirmed still correct by this session's fresh full-suite run. |
| Commit | `git add`/`git commit` in `REPO_ROOT` | changed path | commit sha | commit failure | none dedicated (covered indirectly via mocked `_run_controlled` in trainer tests) | No test using a REAL temporary git repo exists — every commit-path test mocks `_run_controlled` entirely (Layer 6 gap named explicitly in this task). |
| Push | `git push origin master` **directly to master, from the long-lived container** | — | ok/fail | **ACT-007: always fails from the deployed container** (no configured `origin` — see Dockerfile) | none beyond the mocked reset tests | Real, disclosed, unresolved. Root-caused below. |
| Deploy | `railway up --detach --service <customer-app>` from `APP_DIR` (same long-lived checkout) | — | ok/fail + stdout containing a **build-logs URL with the new deployment's ID as a query param** | upload failure | none real (mocked) | **The new deployment's own ID is available in `deploy_out` today and is never captured or used.** This is the missing piece for genuine deployment-identity verification (Layer 7) — currently deployment "identity" is inferred ENTIRELY from content match, never cross-checked against Railway's own deployment ID. |
| New-deployment identification | **does not exist** | — | — | — | — | Real gap. The polling loop only checks `_fetch_public_app()` content + a `railway status` text grep for "Failed"/"Crashed" — it never confirms the *specific* new deployment (vs. some other/older one) is what answered. Content match is a reasonable proxy but is not deployment-identity proof. |
| Production requested-effect verification | `_fetch_public_app()` + `run.trainer_expected_content in after_html` (whole-file substring containment) | live HTML | bool | timeout, explicit Railway failure | none real | Works for static full-file changes by coincidence (the new file's own text literally is what's served) but is not a targeted DOM/field assertion — cannot distinguish "the requested field changed" from "some other part of the page happens to contain the same substring," and is structurally inapplicable to any non-static change (this is exactly ACT-008). |
| Result shown to user | `workbench.js` renders `run.status`/events | SSE + polling | UI state | — | `test_trainer_frontend.js`, Playwright | Reasonably honest today (COMPLETED/FAILED/DEPLOYMENT_STATUS_UNKNOWN are visually distinct, no "false green" found in this session's live testing). |
| Reset/restoration | `_run_reset_thread()` | `agent/demo_baseline/index.html` | ok/fail | **found and fixed live twice last session**: (1) baseline read from a git tag unreachable in the deployed container's disconnected repo, (2) go/no-go check read the container's own local file instead of real production | `DemoResetTestCase` (6 tests, real file I/O + staged production-content mocks) | Both real bugs are now fixed and regression-tested. Reset still deploys from the SAME long-lived `APP_DIR`, sharing the same isolation gap as the main trainer flow. |

## Root causes of the specifically-named known defects

**1. Static/UI test-selection bug ("app/src/test/java has real test file(s), but none were run").**
Root cause: `_determine_testing_state()` checked "does the project have
ANY test file anywhere" *before* "is this specific changed path a static
resource" — so a genuine static-only change was blocked the instant the
Customer app had any Java test file at all, regardless of relevance.
**Status: FIXED** (commit `82648f7`, prior session) — static-resource
check now runs first, unconditionally. Regression test:
`test_static_resource_change_is_not_applicable_even_when_unrelated_java_tests_exist`.
Existing tests missed it originally because the only test exercising this
exact combination (`test_real_tests_exist_but_not_run_is_skipped`)
asserted the *buggy* behavior as correct — a tautological test: the
oracle encoded the same wrong assumption as the implementation, so it
could never catch this class of bug. That specific test has been
rewritten to test the correct contract instead.

**2. Backend 404-message verification gap (ACT-008).**
Root cause: production verification is a single mechanism
(`_fetch_public_app()` + whole-new-file-content substring match against
the ROOT PAGE) that only works because a static file IS what gets served
verbatim. It is structurally meaningless for a compiled Java change (a
deployed JAR never echoes its own source text in any HTTP response), and
even the *page being checked* (root `/`) would be wrong for a controller-
level message that only appears on a different endpoint (e.g.
`GET /customers/{id}` for a nonexistent id). **Status: correctly
NOT implemented, not silently broken** — a real backend demo was
deliberately never attempted live because of this, exactly per this
task's own instruction ("do not expand the public backend-change feature
until the static/UI path passes the reliability gates"). Remains
deferred; a proper design (per-operation expected-assertion, not a
whole-file substring check) is required before any backend demo op is
added — out of scope for this task per the Owner's explicit phasing.

**3. ACT-007 (git push never succeeds from the deployed container).**
Root cause, and answers to the Owner's specific architecture questions:

- *Why does the deployed execution environment have no origin?* The
  platform-backend's Dockerfile deliberately `git init`s a fresh,
  disconnected local repository at build time (`RUN if [ ! -d .git ]; then
  git init -q && git add -A && git commit ...`) because `railway up`'s
  upload of the local working directory never includes `.git` — this was
  the fix for an EARLIER incident (`trainer-6aedf022`, 2026-09-10) where
  `git commit`/`git rev-parse HEAD` had no repository to operate in at
  all. That fix predates any push/reset requirement and was never
  intended to support pushing to GitHub — see the Dockerfile's own
  comment: "this workspace never pushes to/pulls from GitHub."
- *Is this environment supposed to mutate/push a git checkout at all?*
  As currently built: no. The long-lived platform-backend container's own
  checkout exists only so `git commit` has somewhere to write local
  provenance history — it was never meant to be a durable, origin-tracked
  clone.
- *Should the implementation instead use a short-lived isolated
  workspace/clone?* **Yes — this is the fix implemented this task** (see
  below). A fresh, disposable `git clone --depth 1` of the real public
  GitHub repo, used once per run and discarded, is both more correct
  (real origin, real history, a real tag/branch is reachable) and safer
  (the long-lived server process's own files are never touched by public
  input).
- *Least-privilege token scope, credential isolation, and destination
  control* — addressed by the new architecture below; no token has been
  provisioned this task (that remains an explicit Owner decision), but
  the code path is now ready to use one safely the moment it exists.

## Concurrency/locking — verified, not merely asserted

- Lock acquired before work: **yes**, `_reserve_run_slot()` is called
  synchronously inside the request handler (`start_run`/
  `start_trainer_run`/`start_demo_reset`), before any background thread
  starts — confirmed by reading the exact call order in
  `agent/web_server.py`.
- Second user cannot interfere: **yes**, a 409/429 JSON response is
  returned immediately, before any model call or subprocess runs.
- Failed runs release safely: **yes**, `_release_run_slot()` runs in a
  `finally` block covering every return path in `_run_trainer_thread`/
  `_run_reset_thread`.
- Crashed runs do not permanently deadlock: **yes, by construction** —
  `_CURRENT_RUN_ID` is a plain in-process Python global with no disk
  persistence; a process crash/restart clears it automatically. The
  trade-off (an in-flight run's true outcome becomes unknown to the UI
  after a crash) is a separate, honest limitation, not a deadlock.
- Reset cannot race with an active change: **yes**, reset reserves the
  identical global slot (`_reserve_run_slot("demo-reset")`).
- Deployment verification cannot observe another run: **yes, structurally
  guaranteed** — only one run can ever be in flight, so there is no
  second run's deploy for a verification loop to mistakenly observe.

No code change was needed for concurrency; this section is verification
of an already-correct design, recorded here because the Owner explicitly
asked for it to be checked, not assumed.

## What this task changes (see PROJECT_STATE.json / commits for exact evidence)

1. A genuine, machine-verifiable **request contract** (`agent/demo_catalogue.py`) replaces free-form LLM interpretation for the public demo path: exactly 5 named operations, each with a unique deterministic extraction anchor in the real Customer App HTML, a strict input-validation contract for the new value (Layer 2), and a targeted (not whole-file) production assertion (Layer 8). Zero AI model calls for a supported request — cheaper AND more reliable, per the Owner's explicit preference for deterministic-first design.
2. An **isolated, disposable git workspace per run** replaces mutating the platform-backend's own long-lived checkout — the running server's own files are now never touched by public input.
3. Commits land on a dedicated `demo/*` branch, never `master` directly — smaller blast radius, and push (once a token is provisioned) will never be able to touch real project history.
4. **Deployment-identity verification** using the real deployment ID Railway's own `railway up` output already contains (previously computed but discarded) — checked alongside, not instead of, the existing content verification.
5. Reset reuses the same isolated-workspace + deployment-identity mechanism.

## Explicit gaps this task does NOT close (by design, per the Owner's phasing)

- ACT-007's actual push-credential provisioning (a secrets decision) —
  the architecture is now ready for it; the decision itself is the
  Owner's.
- ACT-008 (a real backend/API demo) — deliberately still not attempted.
- A 100%-automated, no-mock, always-real-git-and-Railway CI suite — real
  git/Railway calls are exercised via a mix of (a) real temporary local
  git repositories for Layers 3/6, and (b) real live production runs
  performed manually/via this session for full-stack acceptance, per the
  Owner's own guidance ("large repeated matrices can run locally... a
  smaller representative subset performs real production deployments").
