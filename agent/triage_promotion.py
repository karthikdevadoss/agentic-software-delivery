"""
Incident Triage Lab -- candidate-patch promotion pipeline (Priority 2/3,
flagship-completion session, 2026-09-15).

Completes the ONE remaining gap in the full Triage Lab lifecycle every
scenario's own design doc names: approve -> commit the exact reviewed
candidate -> push -> deploy the real Customer App -> re-run the exact
same reproduction -> assert resolved. Reuses agent/demo_execution.py's
real isolated-workspace clone/commit/push/deploy machinery WHOLESALE --
the exact same functions the public Workbench's own real production
pipeline already uses, never a second implementation.

APPROVAL BINDING (the master instruction's own explicit requirement):
approval must bind to run id + base content + candidate content hash +
diff hash, and any mismatch must be APPROVAL_INVALIDATED, never silently
regenerated after approval. This module's design goes one step further
than "compare hashes the client sends back": it never accepts
client-supplied candidate content for promotion AT ALL. Only the most
recent candidate that this SAME server process itself genuinely watched
reach COMPILE_VERIFIED (via record_verified_candidate(), called only
from the real verification code path in web_server.py) can ever be
promoted -- closing the TOCTOU gap structurally, not by trusting an
echoed hash a compromised or buggy client could forge.

NEVER SELF-APPROVED: promote_verified_candidate() requires real ADMIN
credentials, verified server-to-server against the real Customer App's
own /auth/login -- the exact same call approve_scenario()/_b()/_c()
already make, reused not reinvented. Nothing in this module, or anywhere
else in this codebase, can trigger a promotion without a real human
supplying real admin credentials to this specific function call.

FAILS CLOSED ON A STALE BASELINE: before writing the candidate, the
freshly-cloned file's real current content is hashed and compared
against the exact baseline the candidate was generated against. A
mismatch means master has moved since verification (most likely: the
defect was already fixed, exactly the case for Scenario A -- its real
historical bug was fixed in commit 2155a8a long before this pipeline
existed) -- the function refuses rather than silently overwriting an
already-correct file with a redundant AI-regenerated copy of the same
fix.
"""

import hashlib
import time
from pathlib import Path

import demo_execution
import event_ledger
import triage_execution as te

CUSTOMER_APP_PROJECT_ID = "e19ceaff-846f-4d4a-b840-ce1248dd3325"
RAILWAY_SERVICE_NAME = "agentic-delivery-customer-app"
RAILWAY_ENVIRONMENT = "production"
PUBLIC_CUSTOMER_APP_URL = "https://agentic-delivery-customer-app-production.up.railway.app/"

# In-memory, per-process, keyed by scenario id ("a"/"b"/"c"): the most
# recent candidate that genuinely reached COMPILE_VERIFIED. Populated
# ONLY by record_verified_candidate() -- promote_verified_candidate()
# never accepts candidate content from a caller, only reads this.
_LAST_VERIFIED_CANDIDATE: dict = {}

_REPRODUCE_FN_NAME = {"a": "reproduce_scenario", "b": "reproduce_scenario_b", "c": "reproduce_scenario_c"}
_APPROVE_PATH = {s: f"/internal/triage/scenario-{s}/approve" for s in ("a", "b", "c")}


def _reproduce(scenario: str) -> dict:
    """Looks up te.reproduce_scenario[_b/_c] BY NAME at call time, not a
    reference captured at import time -- a module-level dict of bound
    function objects would silently ignore a test's
    mock.patch("triage_execution.reproduce_scenario_b", ...) (a real
    mistake caught by this module's own test suite), since patching
    replaces the attribute on the te module, not any earlier reference
    to the original function object."""
    return getattr(te, _REPRODUCE_FN_NAME[scenario])()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_verified_candidate(scenario: str, target_file_rel_to_java_root: str,
                               baseline_source: str, candidate_source: str, diff: str) -> None:
    """Called by the web layer immediately after apply_and_verify_candidate*
    returns COMPILE_VERIFIED -- overwrites any prior entry for this
    scenario, since only the MOST RECENT verified candidate may ever be
    promoted. target_file_rel_to_java_root matches the exact convention
    _isolated_compile_java_candidate already uses (e.g.
    "com/example/customer/service/ContractPlanService.java"), never the
    "app/src/main/java/..."-prefixed FIX_FILE constant."""
    _LAST_VERIFIED_CANDIDATE[scenario] = {
        "target_file_rel_to_java_root": target_file_rel_to_java_root,
        "baseline_source": baseline_source,
        "candidate_source": candidate_source,
        "diff": diff,
        "candidate_hash": _sha256(candidate_source),
        "baseline_hash": _sha256(baseline_source),
        "verified_at": time.time(),
    }


def get_verified_candidate_summary(scenario: str) -> dict | None:
    """Read-only view for the approval UI -- hashes and a diff preview
    only, never re-exposes the full candidate source as a second,
    promotable copy a caller could tamper with and echo back."""
    entry = _LAST_VERIFIED_CANDIDATE.get(scenario)
    if entry is None:
        return None
    return {
        "available": True,
        "target_file": entry["target_file_rel_to_java_root"],
        "candidate_hash": entry["candidate_hash"][:16],
        "baseline_hash": entry["baseline_hash"][:16],
        "verified_at": entry["verified_at"],
    }


class PromotionError(Exception):
    """Raised for any safely-reportable promotion failure -- never a raw
    stack trace or a partially-applied state reaching a caller."""


def promote_verified_candidate(scenario: str, admin_username: str, admin_password: str,
                                repo_url: str | None = None) -> dict:
    """The ONE promotion entry point, reused by all three Triage
    scenarios -- see this module's docstring for the full approval-
    binding and fail-closed design. repo_url defaults to the real public
    repository; tests inject a local disposable origin instead, exactly
    matching demo_execution.create_isolated_workspace's own existing
    testability convention."""
    entry = _LAST_VERIFIED_CANDIDATE.get(scenario)
    if entry is None:
        raise PromotionError(
            f"No verified candidate available for scenario {scenario!r} -- "
            f"generate and verify a candidate patch (COMPILE_VERIFIED) first."
        )

    # Real admin login + real admin-gated approve -- the exact same
    # server-to-server call approve_scenario()/_b()/_c() already make.
    try:
        login = te._request("POST", "/auth/login", body={"username": admin_username, "password": admin_password})
    except te.TriageExecutionError as e:
        raise PromotionError(f"admin login failed: {e}") from e
    token = login.get("accessToken")
    if not token:
        raise PromotionError("login succeeded but no accessToken was returned")
    try:
        te._request("POST", _APPROVE_PATH[scenario], token=token)
    except te.TriageExecutionError as e:
        raise PromotionError(f"admin approval rejected: {e}") from e

    run_id = f"triage-{scenario}-promotion-{int(time.time())}"
    kwargs = {"repo_url": repo_url} if repo_url else {}
    workspace, clone_ok, clone_out = demo_execution.create_isolated_workspace(run_id, **kwargs)
    try:
        if not clone_ok:
            raise PromotionError(f"could not clone a fresh isolated workspace: {clone_out[-300:]}")

        target_path = workspace / "app" / "src" / "main" / "java" / entry["target_file_rel_to_java_root"]
        if not target_path.exists():
            raise PromotionError(f"target file not found in the fresh clone: {entry['target_file_rel_to_java_root']}")
        current_content = target_path.read_text(encoding="utf-8")

        if _sha256(current_content) != entry["baseline_hash"]:
            raise PromotionError(
                "APPROVAL_INVALIDATED: the real file in master no longer matches the exact "
                "baseline this candidate was generated against. Master has moved since "
                "verification -- most likely this defect was already fixed independently -- "
                "so promoting this candidate now would be unsafe or meaningless. Generate and "
                "verify a fresh candidate against the current file if a real defect still exists."
            )

        target_path.write_text(entry["candidate_source"], encoding="utf-8")
        relative_path = (Path("app") / "src" / "main" / "java" / entry["target_file_rel_to_java_root"]).as_posix()

        commit_message = (
            f"Promote AI-generated Triage Scenario {scenario.upper()} candidate patch "
            f"(candidate hash {entry['candidate_hash'][:12]}, human-approved via real admin token)"
        )
        branch, commit_ok, commit_out = demo_execution.commit_change(workspace, run_id, relative_path, commit_message)
        if not commit_ok:
            raise PromotionError(f"commit failed: {commit_out[-300:]}")
        production_commit = demo_execution.get_commit_sha(workspace)

        push_status, push_out = demo_execution.push_change(workspace, branch)

        deploy_triggered_after = demo_execution.server_verified_now_iso(PUBLIC_CUSTOMER_APP_URL)
        deploy_ok, deploy_out = demo_execution.trigger_deploy(
            workspace / "app", CUSTOMER_APP_PROJECT_ID, RAILWAY_SERVICE_NAME, RAILWAY_ENVIRONMENT)
        if not deploy_ok:
            raise PromotionError(f"Railway deploy trigger failed: {deploy_out[-300:]}")

        new_deployment_id, deploy_status, waited_s = demo_execution.wait_for_new_deployment(
            CUSTOMER_APP_PROJECT_ID, RAILWAY_SERVICE_NAME, RAILWAY_ENVIRONMENT, deploy_triggered_after, workspace)
        deployment_identity_confirmed = new_deployment_id is not None and deploy_status.upper() == "SUCCESS"

        rerun_result = _reproduce(scenario) if deployment_identity_confirmed else None
        resolved = bool(rerun_result is not None and not rerun_result.get("defectReproduced", True))

        # DURABLE PROVENANCE (Base Architecture V3 Section 11): before this
        # fix, this function's result was only ever an in-memory dict
        # returned to whatever HTTP caller invoked it -- the ONE action
        # this whole pipeline exists for (promoting AI-generated code to
        # real production) had zero durable audit trail, and the
        # candidate_hash that answers "is what was approved the same as
        # what got deployed" was about to be erased from memory by the
        # pop() below with nothing left to correlate it against. Recorded
        # BEFORE the pop so the full identity chain (candidate_hash ->
        # baseline_hash -> production_commit -> deployment_id) is captured
        # in one queryable row, real write-through with local-spool
        # fallback on any remote failure (never silently dropped).
        event_ledger.record_event(
            "candidate_promoted",
            run_id=run_id,
            git_commit=production_commit,
            deployment_version=new_deployment_id,
            status="RESOLVED" if resolved else ("DEPLOYED_UNCONFIRMED" if deployment_identity_confirmed else "DEPLOY_FAILED"),
            source=f"triage_scenario_{scenario}",
            activity_class="PRODUCT_RUNTIME",
            payload={
                "scenario": scenario,
                "candidate_hash": entry["candidate_hash"],
                "baseline_hash": entry["baseline_hash"],
                "branch": branch,
                "push_status": push_status,
                "deployment_status": deploy_status,
                "deployment_identity_confirmed": deployment_identity_confirmed,
                "resolved": resolved,
            },
        )

        # A successful promotion invalidates this entry -- the exact
        # candidate that was just promoted can never be promoted a
        # second time from stale state.
        _LAST_VERIFIED_CANDIDATE.pop(scenario, None)

        return {
            "promoted": True,
            "branch": branch,
            "production_commit": production_commit,
            "candidate_hash": entry["candidate_hash"],
            "push_status": push_status,
            "deployment_identity_confirmed": deployment_identity_confirmed,
            "new_deployment_id": new_deployment_id,
            "deployment_status": deploy_status,
            "waited_seconds": waited_s,
            "rerun_result": rerun_result,
            "resolved": resolved,
        }
    finally:
        demo_execution.cleanup_workspace(workspace)
