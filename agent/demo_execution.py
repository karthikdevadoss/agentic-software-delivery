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


def push_change(workspace: Path, branch: str):
    """Never fatal to the caller — a real deploy runs from the isolated
    workspace's own files regardless of push outcome."""
    if not DEMO_GIT_PUSH_TOKEN:
        return False, "DEMO_GIT_PUSH_TOKEN not configured — push skipped (deploy continues from the isolated workspace regardless)"
    auth_url = f"https://x-access-token:{DEMO_GIT_PUSH_TOKEN}@github.com/karthikdevadoss/agentic-software-delivery.git"
    return push_to_remote(workspace, auth_url, branch, secret_to_redact=DEMO_GIT_PUSH_TOKEN)


# --- Deployment identity (real Railway metadata, not HTTP 200/CLI text) --

def get_latest_deployment_id(project_id: str, service_name: str, environment: str, cwd: Path):
    """Read-only. Returns the most recent deployment's id, or None on
    any failure (never raises — a failed lookup means 'unknown', not an
    assumed value)."""
    ok, out = run_controlled(
        ["railway", "deployment", "list", "--json", "--project", project_id,
         "--service", service_name, "--environment", environment, "--limit", "1"],
        cwd, 20,
    )
    if not ok:
        return None
    try:
        data = json.loads(out)
        return data[0]["id"] if data else None
    except (ValueError, KeyError, IndexError, TypeError):
        return None


def trigger_deploy(app_dir: Path, project_id: str, service_name: str, environment: str):
    """Deploys FROM the isolated workspace's own app/ directory — never
    the long-lived platform-backend server's own APP_DIR — using
    explicit --project/--service/--environment flags (confirmed to work
    without directory-based Railway linking, which a fresh temp clone
    would never have)."""
    ok, out = run_controlled(
        ["railway", "up", str(app_dir), "--detach",
         "--project", project_id, "--service", service_name, "--environment", environment],
        app_dir, 60,
    )
    return ok, out


def wait_for_new_deployment(project_id: str, service_name: str, environment: str,
                             previous_deployment_id, cwd: Path,
                             max_wait_s: int = 15 * 60, poll_interval_s: int = 10):
    """Polls real Railway deployment records — never HTTP 200, never
    'Online' CLI text, never elapsed-time guessing — until a deployment
    ID DIFFERENT from `previous_deployment_id` reaches a real terminal
    status. Returns (new_deployment_id_or_None, status, waited_seconds).
    status is one of: 'SUCCESS', a real Railway failure status string, or
    'TIMEOUT' if no new terminal deployment appeared in the window."""
    waited = 0
    while waited < max_wait_s:
        time.sleep(poll_interval_s)
        waited += poll_interval_s
        ok, out = run_controlled(
            ["railway", "deployment", "list", "--json", "--project", project_id,
             "--service", service_name, "--environment", environment, "--limit", "5"],
            cwd, 20,
        )
        if not ok:
            continue
        try:
            deployments = json.loads(out)
        except ValueError:
            continue
        for d in deployments:
            if d.get("id") == previous_deployment_id:
                continue
            status = str(d.get("status", ""))
            if status.upper() == _SUCCESS_STATUS:
                return d["id"], status, waited
            if any(marker in status.upper() for marker in _FAILURE_STATUS_MARKERS):
                return d["id"], status, waited
    return None, "TIMEOUT", waited
