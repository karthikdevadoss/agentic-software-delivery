# Recovery

Goal: if this laptop disappears tonight, a new machine can recover this
project without any ChatGPT or Claude conversation history. This document
describes evidence-backed steps conceptually — it does not invent exact
commands or configuration that haven't actually been verified, and marks
incomplete dependencies explicitly rather than pretending they're solved.

## Current recovery status: PARTIAL

Git recovery is now real: this repository has a public GitHub remote
(https://github.com/karthikdevadoss/agentic-software-delivery.git — see
docs/RESOURCE_REGISTRY.md), verified pushed with local HEAD == remote HEAD.
Remaining gaps are narrower: no remote secret manager (step 5 below), no
tested restore of the event ledger's backup (see this file's event-ledger
section), and Claude Code's own local hook/notification configuration is
deliberately NOT committed (see this file's Claude Code section) since it
is user-specific, not project source.

## Recovery steps

1. **Obtain authorized Git access.** Once a remote exists (see the gap
   above), a new machine needs read access to it — credentials or SSO,
   not documented here since none is configured yet.
2. **Clone the repository.**
3. **Read `START_HERE.md`** at the repository root — the canonical entry
   point, which links to every other document in the right order.
4. **Install actual required runtimes/tools**, verified from this
   repository's own evidence rather than assumed: Python 3 (this project
   was developed and verified against a Windows Python installation —
   the exact minimum version has not been pinned/verified, treat this as
   a gap), Java 17 + the bundled Maven wrapper (`app/mvnw`/`app/mvnw.cmd`
   — no separate Maven install required), Node.js (used for `npm`-
   installed CLIs and the plain-Node frontend test harness — exact
   minimum version not pinned), and the Python packages listed in
   `agent/requirements.txt`.
5. **Retrieve secrets from their documented location.** See
   docs/SECRETS_REGISTRY.md for exact names and purposes — values are
   never in this repository. As of this writing there is no standardized
   remote secret manager; `ANTHROPIC_API_KEY` would need to be obtained
   directly from wherever the owner currently keeps it (not yet
   documented — a real gap, not glossed over).
6. **Configure the environment** — at minimum `agent/.env` (gitignored)
   with `ANTHROPIC_API_KEY` set, following the pattern already read by
   `agent/main.py`.
7. **Run verification tests** — `python -m unittest test_agent_loop
   test_rag_index test_mcp_server test_write_tools test_build_tools
   test_execution_tools test_risk_policy test_web_server` from the
   `agent/` directory (85 tests as of the last verified run — confirm the
   current count rather than trusting this number blindly), plus
   `node agent/test_trainer_frontend.js` for the frontend harness. A
   passing suite is the first real signal the recovered environment is
   sound.
8. **Connect to required remote services** — Railway CLI (`railway
   login`, device-flow OAuth) and Vercel CLI (`vercel login`) each need
   their own fresh authentication on a new machine; neither credential is
   stored in this repository (see docs/SECRETS_REGISTRY.md). This step
   requires the owner's own account access, not anything recoverable from
   Git.
9. **Verify production resources** — confirm docs/RESOURCE_REGISTRY.md's
   entries are still accurate (Railway app reachable, Vercel site
   reachable) before assuming they still are; URLs and statuses can
   change independently of this repository.
10. **Continue from current project state** — read
    `docs/PROJECT_STATE.json` (`next_phase`/`next_action`) and
    `docs/PROJECT_STATUS.md`'s "Current Reality" section as the
    authoritative starting point for what to do next. Do not resume from
    assumption or from a stale summary if the two disagree with actual
    repository/runtime evidence — repository state always wins (see
    CLAUDE.md).

## Recovering the durable event ledger (Railway PostgreSQL)

As of this writing this is the ONE piece of durable engineering telemetry
that lives outside Git — everything else in this document assumes Git
recovery is enough, but the event ledger's data lives only in Railway
Postgres (see docs/RESOURCE_REGISTRY.md's "Durable engineering event
ledger" entry).

1. **Reconnect the Railway CLI** (step 8 above) with access to the
   `agentic-delivery-events` project.
2. **Retrieve `EVENT_LEDGER_DATABASE_URL`** — not stored anywhere in Git;
   reconstruct it from the Railway service's Postgres variables plus the
   public TCP proxy host:port recorded in docs/RESOURCE_REGISTRY.md
   (`shortline.proxy.rlwy.net:51211` as of last verification — proxies can
   be recreated if this one expires: `railway tcp-proxy create --port 5432
   --service Postgres`). Add it to the new machine's `agent/.env`.
3. **Install `psycopg2-binary`** (in `agent/requirements.txt`).
4. **Verify connectivity and schema** — `python -c "import event_ledger as
   el; el.ensure_schema(); print(el.count_events())"` from `agent/`. If
   the table doesn't exist yet, `ensure_schema()` creates it from
   `infra/event-ledger/schema.sql`.
5. **Known gap:** no remote secret manager exists, so step 2 above has no
   automated retrieval path — this mirrors the exact same gap already
   recorded for `ANTHROPIC_API_KEY` below.
6. **Known gap:** PITR is disabled on this Postgres instance (a deliberate,
   documented choice pending an explicit cost/approval decision — see
   docs/RESOURCE_REGISTRY.md). If the Railway project/volume itself is
   lost (not just this laptop), the event ledger's data is recoverable
   only from the last manual portable backup run via
   `agent/event_ledger_backup.py` (gitignored, local-only output) — if one
   was taken and that file also survived. **No restore of that backup has
   ever been tested.**

## Recovering Claude Code development-telemetry hooks on a new machine

Claude Code's own development-activity capture (source=claude_code,
activity_class=PRODUCT_DEVELOPMENT — distinct from the Workbench/
PRODUCT_RUNTIME events above) is wired through Claude Code hooks that
invoke `agent/claude_code_hook.py`.

**CRITICAL — the hooks MUST live in your USER-LEVEL settings file
(`~/.claude/settings.json`, i.e. `%USERPROFILE%\.claude\settings.json` on
Windows), never in this project's `.claude/settings.local.json`.** This
was learned the hard way (see docs/LESSONS.md's "believed implemented but
verified nothing" incident and docs/DECISIONS.md): Claude Code's own
permission-remember mechanism (the thing that quietly adds a rule to
`permissions.allow` when a tool action gets approved) rewrites the ENTIRE
content of `.claude/settings.local.json` every time it adds a rule, and
that rewrite does not preserve unmanaged keys — a `hooks` section placed
there gets silently dropped the next time ANY permission gets
auto-remembered, with no error, no warning. Confirmed empirically,
twice, by adding a test marker key to `.claude/settings.local.json`,
running an ordinary novel command, and watching the marker disappear
while `~/.claude/settings.json` (never touched by that mechanism)
retained an identical test marker unchanged. Both locations were tested
side by side, not assumed independently.

Portable, non-secret setup steps for a new machine that wants this:

1. Confirm the installed Claude Code version actually supports the hook
   events used (`SessionStart`, `SessionEnd`, `UserPromptSubmit`,
   `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`,
   `PermissionDenied`, `Notification`, `Stop`, `SubagentStart`,
   `SubagentStop`) — do not assume; verify against that installation the
   same way this was verified here (see docs/DECISIONS.md for the method
   used: extracting literal hook-name strings directly from the installed
   binary rather than trusting docs).
2. Merge the `hooks` key from the git-tracked, secret-free template
   `.claude/hooks-template.json` (in this repo) into your USER-LEVEL
   `~/.claude/settings.json` — do NOT put it in
   `.claude/settings.local.json` (see above). If you already have other
   keys in your user settings (theme, plugins, etc.), merge rather than
   overwrite.
3. **Verify the configuration with `python agent/verify_claude_hooks_config.py`**
   — checks that all expected hooks exist in the user-level file, that
   each command references `claude_code_hook.py` and uses
   `${CLAUDE_PROJECT_DIR}` (portable across projects/machines), and flags
   the exact known-bad case (a `hooks` key sitting in
   `.claude/settings.local.json` instead). Exit code 0 = configuration
   correct. This proves the CONFIGURATION only — not that Claude Code has
   actually invoked it (see step 6).
4. Complete the event-ledger recovery steps above first — the hook script
   spools locally regardless (`agent/event_spool.jsonl`) and only needs
   `EVENT_LEDGER_DATABASE_URL` for the background sync step to actually
   reach the remote database.
5. For the Windows attention-notification mechanism
   (`agent/claude_notify.ps1`, invoked by the hook script for
   `PermissionRequest`/`Notification` events): no setup needed beyond
   having PowerShell available — it uses only built-in Windows APIs (WinRT
   toast via the pre-registered legacy-PowerShell AUMID, `System.Media.
   SystemSounds`, `user32.dll`'s `FlashWindowEx`), no module install.
6. Optionally add narrow permission `allow` rules for safe, read-only,
   local commands in `.claude/settings.local.json` (see the actual rules
   used here for the pattern) — never copy a broad rule like `Bash(git *)`
   or enable `--dangerously-skip-permissions`/`bypassPermissions`. This
   file being auto-rewritten by the permission-remember mechanism is fine
   for permissions (that's its intended job) — just never put anything
   else in it that needs to survive.
7. **A telemetry capability is only verified once real ledger rows exist
   from a real Claude Code process, not once the script/config looks
   right.** Restart Claude Code in this repo after completing the steps
   above (hooks load at session start — a config change made mid-session
   does not apply retroactively to that same session), then query the
   remote ledger directly for a genuine `dev_session_started` row with a
   real, non-test session_id and a recent `timestamp_utc`. Script-level
   testing (direct stdin simulation) proves the hook SCRIPT works: it does
   not prove Claude Code is actually calling it.

## Explicitly incomplete recovery dependencies (not solved by this document)

- No Git remote exists yet — step 1 is currently impossible.
- No remote secret manager exists — step 5's exact retrieval mechanism is
  undocumented by necessity, since none has been chosen.
- Exact minimum Python/Node versions are not pinned or verified anywhere
  in this repository.
- Railway/Vercel CLI authentication has no durable, laptop-independent
  backup — both are single-machine session credentials today.
- The Cloudflare Quick Tunnel used for public Workbench demos is
  inherently non-durable by design (see docs/RESOURCE_REGISTRY.md) — its
  URL is not something to "recover," a fresh one must be created.
- The event ledger's `EVENT_LEDGER_DATABASE_URL` has no automated
  retrieval path on a new machine (same gap as `ANTHROPIC_API_KEY`).
- PITR is disabled on the event ledger's Postgres instance; recovery of
  that project/volume being lost outright depends entirely on whether a
  manual `agent/event_ledger_backup.py` dump was taken and survived — and
  even then, no restore has ever actually been tested.
