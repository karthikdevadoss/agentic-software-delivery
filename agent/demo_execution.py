"""
Isolated-workspace execution engine for the public Workbench demo
(RELIABILITY/CORRECTION PHASE, 2026-09-13).

Real architecture fix for ACT-007's underlying question ("should this use
a short-lived isolated workspace/clone?" -- yes). Every public demo run
clones a FRESH, disposable copy of the real public repository into a temp
directory, mutates ONLY the one deterministically-targeted file there
(see demo_catalogue.py), commits on a dedicated demo/<run_id> branch
(never master directly), and deploys the Customer App from that isolated
clone's own app/ directory. The long-lived platform-backend server
process's OWN checkout is never touched by public input -- previously,
the trainer thread mutated agent/web_server.py's REPO_ROOT directly,
meaning a bad or partially-failed public request could leave the very
process serving Workbench itself in a mutated state.

Push uses an optional, narrowly-scoped token (DEMO_GIT_PUSH_TOKEN env
var) read once at import time, used only to build an in-memory
authenticated remote URL, and unconditionally redacted from any output
before it is ever returned to a caller (a caller may put that output in
an SSE event visible to the browser). No token is provisioned by this
task -- ACT-007's actual credential-provisioning decision remains the
Owner's -- but this code path is ready to use one safely the moment it
exists. The destination repository/branch is a hardcoded server-side
constant, never derived from public input in any way, so a public
requirement can never redirect where a commit lands.

Deployment-identity verification (a real gap this module closes): the
previous implementation inferred "did the NEW deployment go live" purely
from content matching a fetched page, never cross-checked against
Railway's own deployment records. `railway deployment list --json`
(confirmed empirically to work with explicit --project/--service/
--environment flags, needing no directory-based project link) gives a
real deployment id + status; wait_for_new_deployment() polls until a
deployment ID DIFFERENT from the one recorded before this run's deploy
reaches a real terminal status, never inferring identity from timing or
HTTP 200 alone.

Zero dependency on agent/web_server.py's Starlette app -- fully unit
testable in isolation, including against real temporary local git
repositories (see test_demo_execution.py).
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PUBLIC_REPO_HTTPS_URL = "https://github.com/karthikdevadoss/agentic-software-delivery.git"
DEMO_BRANCH_PREFIX = "demo/"
# Read once at import time -- never logged, never included in any HTTP
# response or SSE event, never derived from public input.
DEMO_GIT_PUSH_TOKEN = os.environ.get("DEMO_GIT_PUSH_TOKEN")

_FAILURE_STATUS_MARKERS = ("FAIL", "CRASH")
_SUCCESS_STATUS = "SUCCESS"


def run_controlled(argv, cwd, timeout_s):
    """Same controlled-subprocess discipline as web_server.py's
    _run_controlled (explicit argv, shell=False, bounded timeout, real
    UTF-8 decoding) -- duplicated intentionally, not imported, so this
    module has zero dependency on the Starlette app."""
    resolved = shutil.which(argv[0])
    argv = [resolved or argv[0], *argv[1:]]
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_s, shell=False,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout_s}s"
    except OSError as exc:
        return False, str(exc)


# --- Isolated workspace ------------------------------------------------

def create_isolated_workspace(run_id: str, repo_url: str = PUBLIC_REPO_HTTPS_URL):
    """Clones the real public repo (read-only HTTPS, no credentials
    needed for a public repo) into a fresh temp directory. Returns
    (workspace_path, ok, output). Caller must cleanup_workspace() when
    done, in a `finally`, regardless of outcome."""
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"demo-{run_id}-"))
    ok, out = run_controlled(
        ["git", "clone", "--depth", "1", "--branch", "master", repo_url, str(tmp_dir)],
        tmp_dir.parent, 60,
    )
    return tmp_dir, ok, out


def _force_remove_readonly(func, path, _exc_info):
    """shutil.rmtree onerror handler: git repositories can leave files
    (notably under .git/objects/pack on Windows) marked read-only, which
    makes a plain rmtree silently fail to actually remove them even with
    ignore_errors=True — clear the read-only bit and retry once, a
    well-known pattern for cleaning up git checkouts cross-platform."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def cleanup_workspace(workspace: Path) -> None:
    """Best-effort: cleanup failing must never crash the caller (worst
    case is a leftover temp directory — a minor disk-space concern, not
    a correctness one). Real read-only-file removal is still attempted
    via the onerror retry, not silently skipped."""
    try:
        shutil.rmtree(workspace, onerror=_force_remove_readonly)
    except OSError:
        pass


# --- Commit / push (isolated workspace only, never the server's own checkout) --

def commit_change(workspace: Path, run_id: str, relative_path: str, commit_message: str):
    """Creates a dedicated demo/<run_id> branch and commits ONLY the one
    given path -- never a blanket `git add -A`. Returns
    (branch_name, ok, output)."""
    branch = f"{DEMO_BRANCH_PREFIX}{run_id}"
    ok, out = run_controlled(["git", "checkout", "-b", branch], workspace, 15)
    if not ok:
        return branch, False, out
    for cfg_ok_step in (
        run_controlled(["git", "config", "user.email", "demo@agentic-software-delivery.local"], workspace, 10),
        run_controlled(["git", "config", "user.name", "Agentic Software Delivery (public demo)"], workspace, 10),
    ):
        ok, out = cfg_ok_step
        if not ok:
            return branch, False, out
    ok, out = run_controlled(["git", "add", "--", relative_path], workspace, 15)
    if not ok:
        return branch, False, out
    ok, out = run_controlled(["git", "commit", "-m", commit_message], workspace, 30)
    return branch, ok, out


def get_commit_sha(workspace: Path):
    ok, out = run_controlled(["git", "rev-parse", "--short", "HEAD"], workspace, 15)
    return out.strip() if ok else None


def get_changed_files(workspace: Path):
    """Real, checkable evidence of exactly which paths the commit
    touched — used to assert no protected/unexpected file changed."""
    ok, out = run_controlled(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"], workspace, 15)
    return [line.strip() for line in out.splitlines() if line.strip()] if ok else None


def push_to_remote(workspace: Path, remote_url: str, branch: str, secret_to_redact: str = None):
    """Real git push mechanics, isolated from the hardcoded GitHub URL so
    it can be exercised in tests against a real local repository — proof
    that 'push succeeded' really means the remote received the commit,
    per the Owner's explicit Layer 6 requirement (real git, not mocks
    alone). `secret_to_redact`, if given, is unconditionally stripped
    from the returned output before it is ever handed back to a caller
    that might display it (git can echo a remote URL, credentials
    included, into its own error text on failure)."""
    ok, out = run_controlled(["git", "push", remote_url, f"HEAD:{branch}"], workspace, 60)
    if secret_to_redact:
        out = out.replace(secret_to_redact, "***REDACTED***")
    return ok, out


# WORKBENCH TRUTHFULNESS FIX (2026-09-13): a real Owner-submitted run
# ("Change the footer text to \"Built with DOSS care\"", trainer-25c4e8bb,
# root-caused via the live event ledger) proved genuinely COMPLETED end to
# end, but the UI rendered an alarming "ERROR: git push failed..." line
# for the ordinary, fully-expected DEMO_GIT_PUSH_TOKEN-not-configured
# precondition — indistinguishable from a real attempted-and-failed push.
# push_change() previously returned a plain (ok: bool, message) pair that
# could not express this distinction; the caller had no honest way to
# tell "never attempted, by design" apart from "attempted, genuinely
# failed" other than string-matching the message. These three explicit
# states replace that: only PUSH_STATUS_FAILED is a genuine attempted
# failure worth an "error" event.
PUSH_STATUS_PUSHED = "PUSHED"
PUSH_STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
PUSH_STATUS_FAILED = "FAILED"


def push_change(workspace: Path, branch: str):
    """Never fatal to the caller — a real deploy runs from the isolated
    workspace's own files regardless of push outcome. Returns
    (status, message) where status is one of PUSH_STATUS_PUSHED/
    PUSH_STATUS_NOT_CONFIGURED/PUSH_STATUS_FAILED — callers must render
    NOT_CONFIGURED as an honest, non-alarming precondition, never as an
    error alongside a genuine FAILED push attempt."""
    if not DEMO_GIT_PUSH_TOKEN:
        return PUSH_STATUS_NOT_CONFIGURED, "DEMO_GIT_PUSH_TOKEN not configured — push skipped (deploy continues from the isolated workspace regardless)"
    auth_url = f"https://x-access-token:{DEMO_GIT_PUSH_TOKEN}@github.com/karthikdevadoss/agentic-software-delivery.git"
    ok, out = push_to_remote(workspace, auth_url, branch, secret_to_redact=DEMO_GIT_PUSH_TOKEN)
    return (PUSH_STATUS_PUSHED if ok else PUSH_STATUS_FAILED), out


# --- Deployment identity (real Railway metadata, not HTTP 200/CLI text) --

def utc_now_iso() -> str:
    """Real reference-timestamp capture for deployment-identity checks —
    call this IMMEDIATELY before trigger_deploy(), then pass the result
    to wait_for_new_deployment() as `deploy_triggered_after_iso`."""
    return datetime.now(timezone.utc).isoformat()


def link_workspace_to_railway(app_dir: Path, project_id: str, service_name: str, environment: str):
    """Best-effort only — see the real-evidence caveat in trigger_deploy's
    docstring on why this is NOT treated as fatal. Confirmed empirically
    (2026-09-13, this exact task) to resolve non-interactively and exit 0
    from a real user-authenticated local machine when all three of
    --project/--service/--environment are given. NOT re-confirmed against
    the deployed container's own project-scoped RAILWAY_TOKEN, which may
    legitimately reject a `link` call (a scoped token is already locked
    to one project, so re-linking may be a disallowed operation under it)
    — that is a real, distinct authentication context this function's
    caller must tolerate failing, not treat as blocking."""
    return run_controlled(
        ["railway", "link", "--project", project_id, "--service", service_name, "--environment", environment],
        app_dir, 30,
    )


def trigger_deploy(app_dir: Path, project_id: str, service_name: str, environment: str):
    """Deploys FROM the isolated workspace's own app/ directory — never
    the long-lived platform-backend server's own APP_DIR.

    Real incident (2026-09-13, this exact task, two real production
    acceptance runs): the first attempt found `railway up` failing fast
    from a fresh isolated (Railway-unlinked) directory and hypothesized
    `railway link` first as the fix — but a SECOND real run proved that
    hypothesis incomplete: `railway link` itself failed near-instantly
    when run from inside the deployed container (which authenticates via
    a project-scoped RAILWAY_TOKEN, not full user OAuth like the machine
    this was first tested from) and blocking the deploy on that failure
    made the SAME real defect fail differently, not fixed. Correction:
    `railway link` is now attempted but explicitly NON-FATAL — if it
    fails (e.g. disallowed under a scoped token), `railway up` is still
    attempted directly with explicit --project/--service/--environment,
    exactly as this function did before the link step existed. Link is
    kept as a best-effort attempt because it did resolve one real local
    dev-machine scenario; it must never be allowed to block a deploy the
    explicit flags could otherwise have succeeded at."""
    link_ok, link_out = link_workspace_to_railway(app_dir, project_id, service_name, environment)
    ok, out = run_controlled(
        ["railway", "up", str(app_dir), "--detach",
         "--project", project_id, "--service", service_name, "--environment", environment],
        app_dir, 60,
    )
    if not link_ok:
        out = f"[railway link non-fatal failure, deploy attempted anyway: {link_out[-200:]}] {out}"
    return ok, out


def wait_for_new_deployment(project_id: str, service_name: str, environment: str,
                             deploy_triggered_after_iso: str, cwd: Path,
                             max_wait_s: int = 15 * 60, poll_interval_s: int = 10):
    """Polls real Railway deployment records — never HTTP 200, never
    'Online' CLI text, never elapsed-time guessing — until a deployment
    genuinely CREATED AFTER `deploy_triggered_after_iso` reaches a real
    terminal status.

    Real bug found live (2026-09-13, this exact task, three real
    production acceptance runs before this was caught): the previous
    version identified "the new deployment" as any list entry whose id
    differed from a `previous_deployment_id` captured before this run.
    That is not sufficient — if the genuinely-new deployment has not yet
    propagated into Railway's own recent-deployments list by the time of
    the FIRST poll (confirmed to happen: it can take longer than one 10s
    poll interval), the loop instead matched some OTHER pre-existing
    deployment in the same page that merely wasn't the id it started
    from — in the real incident this caught, a deployment that had
    genuinely FAILED forty-six minutes earlier, for an unrelated reason,
    causing this run to report a false "Railway reported a failed
    deployment" verdict for a change that had, in real fact, just
    deployed successfully. Filtering candidates by real `createdAt` (a
    string compare is correct here since Railway's timestamps are
    ISO 8601 UTC, which sort lexicographically in chronological order)
    makes this genuinely impossible to reproduce, regardless of any
    propagation delay or list-ordering assumption.

    Returns (new_deployment_id_or_None, status, waited_seconds). status
    is one of: 'SUCCESS', a real Railway failure status string, or
    'TIMEOUT' if no new terminal deployment appeared in the window."""
    waited = 0
    while waited < max_wait_s:
        time.sleep(poll_interval_s)
        waited += poll_interval_s
        ok, out = run_controlled(
            ["railway", "deployment", "list", "--json", "--project", project_id,
             "--service", service_name, "--environment", environment, "--limit", "10"],
            cwd, 20,
        )
        if not ok:
            continue
        try:
            deployments = json.loads(out)
        except ValueError:
            continue
        candidates = [d for d in deployments if str(d.get("createdAt", "")) > deploy_triggered_after_iso]
        for d in candidates:
            status = str(d.get("status", ""))
            if status.upper() == _SUCCESS_STATUS:
                return d["id"], status, waited
            if any(marker in status.upper() for marker in _FAILURE_STATUS_MARKERS):
                return d["id"], status, waited
    return None, "TIMEOUT", waited
