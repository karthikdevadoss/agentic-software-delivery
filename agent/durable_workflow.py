"""
Durable software-change workflow -- Sprint 13, BL-093.

WHAT THIS IS
One bounded, production-grade, STATEFUL agent workflow built with LangGraph on
top of capabilities this platform already has. It runs the existing Workbench
software-change flow as an explicit graph:

    RECEIVED -> INVESTIGATED -> PROPOSED -> WAITING_FOR_APPROVAL
        -> (APPROVED | REJECTED) -> APPLIED -> COMPILED -> TESTED -> VERIFIED
        -> COMPLETED            (or BLOCKED / FAILED, each terminal)

with persisted checkpoints in the same Postgres that holds the event ledger,
a real human-in-the-loop interrupt at approval, resume across a process
restart, and idempotent handling of the one side-effecting stage (apply).

WHAT IT IS NOT
- Not a replacement for agent/web_server.py's Workbench run path. That path
  keeps its synchronous, in-process approval prompt exactly as it is. This is
  a parallel path (Owner decision 2026-09-29), so a defect here cannot take
  the live Workbench down.
- Not new authority for the model. Every decision that matters is code:
    * risk_policy.classify() gates the requirement BEFORE anything runs;
    * demo_catalogue.normalize_requirement() determines the proposal -- the
      target file and the exact mutation -- deterministically, as the public
      Workbench already does; the model's contribution is ADVISORY
      (an investigation summary routed through reasoning_gateway, kill-switch
      honoured, and discarded if it is not plain text);
    * write_tools' ALLOWED_WRITE_PREFIXES / ALLOWED_WRITE_EXTENSIONS and its
      hash binding are reused unchanged for the apply stage;
    * build_tools' allowed goals are the only compile/test operations;
    * approval arrives ONLY through resume_workflow() called by a human HTTP
      action, carrying the binding hash of the exact proposal shown. There is
      no tool the model could call to approve, and a resume whose binding does
      not match the checkpointed proposal is refused.

HOW THE CRITICAL SCENARIO IS HANDLED (Owner's demonstration)
The apply stage writes the approved content into an isolated git workspace
and commits it, with the binding hash in the commit subject. Both facts --
the workspace path and the commit sha -- go into the checkpoint. On any
re-entry (a resume after a crash, a duplicate resume request, a retry),
apply first looks for its own commit in the workspace by binding hash:
found -> the write already happened, skip it; not found and the workspace is
gone -> the side effect died with the workspace, so the workflow FAILS SAFELY
with that exact reason instead of quietly writing again. If a push credential
is configured the commit is also pushed to workflow/<id>, which survives a
container restart; push status is recorded either way, never assumed.

Every state transition is a `workflow_transition` event in the existing event
ledger (agent/event_ledger.py). No parallel observability system.

PERSISTENCE
agent/workflow_checkpointer.py implements LangGraph's BaseCheckpointSaver on
two tables added to infra/event-ledger/schema.sql, applied by the ledger's
own ensure_schema(). The checkpoint format is the library's typed JSON blobs;
the operator-facing summary (id, current state, completed states, pending
human action, deterministic decision, timestamps, outcome) is derived from the
latest checkpoint's channel values by describe_workflow() -- one source of
truth, no second table that can drift.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

import backend_execution
import backend_rag_index
import demo_catalogue
import demo_execution
import reasoning_gateway
import risk_policy
import write_tools

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

# --- explicit states --------------------------------------------------------
STATES = (
    "RECEIVED", "BLOCKED", "INVESTIGATED", "PROPOSED", "WAITING_FOR_APPROVAL",
    "APPROVED", "REJECTED", "APPLIED", "COMPILED", "TESTED", "VERIFIED",
    "COMPLETED", "FAILED",
)
TERMINAL_STATES = frozenset({"BLOCKED", "REJECTED", "COMPLETED", "FAILED"})
MAX_REQUIREMENT_CHARS = 400          # same cap as the Workbench's public path

WORKSPACE_ROOT = pathlib.Path(os.environ.get(
    "WORKFLOW_WORKSPACE_ROOT", str(pathlib.Path.home() / ".agentic-workflows")))
# What the apply stage clones. The public repository in production; the
# hermetic tests and the drill point it at a local git repository.
SOURCE_REPO_URL = os.environ.get("WORKFLOW_SOURCE_REPO", demo_execution.PUBLIC_REPO_HTTPS_URL)


def _drill_pause(point: str) -> None:
    """Crash-drill hook (BL-094). When WORKFLOW_DRILL_PAUSE_AT names this
    point, print a marker and block so the orchestrating process can KILL
    this one -- a real process death at a known boundary. Inert unless the
    variable is set; production never sets it."""
    if os.environ.get("WORKFLOW_DRILL_PAUSE_AT") == point:
        print(f"DRILL_PAUSE {point}", flush=True)
        time.sleep(600)


def workspace_path(workflow_id: str) -> pathlib.Path:
    """A pure function of the workflow id. CRASH DRILL FINDING (run 2, A4,
    2026-09-29): after a kill inside the apply node the checkpoint held
    workspace=None -- the path lived only in the node's final state update,
    which never ran -- and the resumed node cloned onto the existing
    directory and failed. Deriving the location from the id means re-entry
    can always find its own prior work, checkpointed or not."""
    return WORKSPACE_ROOT / f"wf-{workflow_id}"


def _create_workspace(workflow_id: str) -> tuple[pathlib.Path, bool, str]:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    ws = workspace_path(workflow_id)
    if ws.exists():
        # A directory with none of our commits is a clone that died before
        # the side effect (checked by the caller): nothing to preserve.
        import shutil
        shutil.rmtree(ws, ignore_errors=True)
    ok, out = _git(["clone", "-q", "--branch", "master", SOURCE_REPO_URL, str(ws)], WORKSPACE_ROOT, 180)
    return ws, ok, out


class WorkflowState(TypedDict, total=False):
    workflow_id: str
    requirement: str
    requirement_sha256: str
    state: str
    completed_states: list[str]
    transitions: list[dict]          # {from, to, at, note}
    decision: dict                   # risk_policy.classify() output, verbatim
    investigation: dict              # advisory only
    proposal: dict                   # {path, new_value, operation_id, binding, new_content_sha256, diff}
    proposal_content: str            # the exact approved content (checkpointed)
    pending_human_action: str | None
    approval: dict                   # {decision, binding, actor, at}
    workspace: str | None
    applied: dict                    # {binding, commit_sha, at, push_status}
    build: dict
    tests: dict
    verification: dict
    outcome: str | None
    error: str | None
    created_at: str
    updated_at: str


# --- helpers ----------------------------------------------------------------
def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_transition(state: WorkflowState, new_state: str, note: str = "") -> dict:
    """The ONLY way a state changes. Appends to the checkpointed transition
    log and writes the same fact to the event ledger. Never raises."""
    prev = state.get("state")
    at = _now()
    completed = list(state.get("completed_states") or [])
    if prev and prev not in completed:
        completed.append(prev)
    transitions = list(state.get("transitions") or [])
    transitions.append({"from": prev, "to": new_state, "at": at, "note": note})
    try:
        import event_ledger
        event_ledger.record_event(
            "workflow_transition",
            source="durable_workflow", activity_class="PRODUCT_RUNTIME",
            run_id=state.get("workflow_id"), stage=new_state, status=new_state,
            payload={"workflow_id": state.get("workflow_id"), "from": prev, "to": new_state,
                     "note": note, "requirement_sha256": state.get("requirement_sha256")},
        )
    except Exception:
        pass
    return {"state": new_state, "completed_states": completed,
            "transitions": transitions, "updated_at": at}


def _git(args: list[str], cwd: pathlib.Path, timeout: int = 30) -> tuple[bool, str]:
    return demo_execution.run_controlled(["git", *args], cwd, timeout)


# --- nodes ------------------------------------------------------------------
def receive(state: WorkflowState) -> dict:
    """Deterministic gate. The model has not been consulted yet."""
    req = (state.get("requirement") or "").strip()
    if not req or len(req) > MAX_REQUIREMENT_CHARS:
        upd = _record_transition(state, "BLOCKED", "requirement empty or over the length cap")
        return {**upd, "outcome": "BLOCKED", "error": "requirement empty or too long",
                "decision": {"decision": "blocked", "reason": "length"}}
    decision = risk_policy.classify(req)
    if decision.get("decision") == "blocked":
        upd = _record_transition(state, "BLOCKED", "risk policy blocked the requirement")
        return {**upd, "decision": decision, "outcome": "BLOCKED",
                "error": "blocked by risk policy"}
    upd = _record_transition(state, "RECEIVED", "risk policy allowed")
    return {**upd, "decision": decision, "requirement_sha256": _sha(req)}


def investigate(state: WorkflowState, create_fn=None) -> dict:
    """Retrieval plus an ADVISORY model summary. Nothing here can change what
    gets proposed; the proposal is the catalogue's, below."""
    req = state["requirement"]
    summary: dict[str, Any] = {"retrieved": [], "advisory": None, "model_called": False}
    try:
        hits = backend_rag_index.semantic_search(req, top_k=3)
        summary["retrieved"] = [{"source_path": h.get("source_path"), "score": h.get("score")} for h in hits]
    except Exception as exc:                                # retrieval is optional evidence
        summary["retrieval_error"] = str(exc)[:200]
    try:
        if not reasoning_gateway.llm_mode_disabled():
            r = reasoning_gateway.call(
                purpose="SEMANTIC_REQUIREMENT_INTERPRETATION",
                system_prompt=("Summarise, in two plain sentences, what this software-change "
                               "requirement asks for. You are advisory only; nothing you say "
                               "is executed."),
                user_message=req, max_tokens=200, create_fn=create_fn,
                model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-5"))
            summary["model_called"] = bool(r.get("model_called"))
            summary["advisory"] = (r.get("text") or "")[:600] if r.get("model_called") else None
            summary["usage"] = r.get("usage")
    except Exception as exc:
        summary["advisory_error"] = str(exc)[:200]
    upd = _record_transition(state, "INVESTIGATED")
    return {**upd, "investigation": summary}


def propose(state: WorkflowState) -> dict:
    """Deterministic proposal from the catalogue, validated against the write
    boundary, hash-bound. Fails closed on anything unsupported."""
    req = state["requirement"]
    try:
        norm = demo_catalogue.normalize_requirement(req)
    except (demo_catalogue.UnsupportedRequirement, demo_catalogue.InvalidValue) as exc:
        upd = _record_transition(state, "FAILED", f"no deterministic proposal: {exc}")
        return {**upd, "outcome": "FAILED", "error": f"unsupported requirement: {exc}"}
    target = norm.target_file
    # Same boundary the live write path enforces: prefix + extension.
    if not target.startswith(write_tools.ALLOWED_WRITE_PREFIXES) or \
            pathlib.Path(target).suffix.lower() not in write_tools.ALLOWED_WRITE_EXTENSIONS:
        upd = _record_transition(state, "FAILED", "proposal outside the write boundary")
        return {**upd, "outcome": "FAILED", "error": f"target outside write boundary: {target}"}
    source = (REPO_ROOT / target)
    if not source.is_file():
        upd = _record_transition(state, "FAILED", "proposal target missing in the repository")
        return {**upd, "outcome": "FAILED", "error": f"target not found: {target}"}
    old = source.read_text(encoding="utf-8")
    try:
        new = demo_catalogue.apply_operation(old, norm.operation_id, norm.new_value)
        line_idx, old_line, new_line = demo_catalogue.compute_single_line_diff(old, new)
    except RuntimeError as exc:
        upd = _record_transition(state, "FAILED", f"deterministic mutation refused: {exc}")
        return {**upd, "outcome": "FAILED", "error": str(exc)}
    binding = write_tools._binding_hash(target, new)   # noqa: SLF001 - the live boundary's own binding
    proposal = {"path": target, "operation_id": norm.operation_id,
                "new_value": norm.new_value, "risk_class": norm.risk_class,
                "line_changed": line_idx, "old_line": old_line, "new_line": new_line,
                "binding": binding, "new_content_sha256": _sha(new)}
    upd = _record_transition(state, "PROPOSED", f"{norm.human_name} -> {norm.new_value!r}")
    return {**upd, "proposal": proposal, "proposal_content": new,
            "pending_human_action": "approve_or_reject"}


def mark_waiting(state: WorkflowState) -> dict:
    """Its own node so the WAITING_FOR_APPROVAL transition is checkpointed
    once; the interrupt node after it is re-executed on every resume."""
    return _record_transition(state, "WAITING_FOR_APPROVAL", "awaiting a human decision")


def wait_for_approval(state: WorkflowState) -> dict:
    """The HITL interrupt. Everything before this line has been checkpointed;
    the process can die here and the workflow is still WAITING."""
    proposal = state["proposal"]
    # LangGraph re-runs this node on resume, so the WAITING transition is
    # recorded by mark_waiting() (below) exactly once, before the interrupt.
    answer = interrupt({"workflow_id": state["workflow_id"], "action": "approve_or_reject",
                        "proposal": {k: proposal[k] for k in ("path", "old_line", "new_line", "binding")}})
    # --- resumed: `answer` came from a human HTTP action, nowhere else -----
    decision = (answer or {}).get("decision")
    binding = (answer or {}).get("binding")
    actor = (answer or {}).get("actor") or "unknown"
    if binding != proposal["binding"]:
        upd = _record_transition(state, "REJECTED", "approval binding did not match the proposal")
        return {**upd, "approval": {"decision": "reject", "binding": binding, "actor": actor,
                                    "at": _now(), "reason": "binding mismatch"},
                "pending_human_action": None, "outcome": "REJECTED"}
    if decision == "approve":
        upd = _record_transition(state, "APPROVED", f"approved by {actor}")
        return {**upd, "approval": {"decision": "approve", "binding": binding,
                                    "actor": actor, "at": _now()},
                "pending_human_action": None}
    upd = _record_transition(state, "REJECTED", f"rejected by {actor}")
    return {**upd, "approval": {"decision": "reject", "binding": binding, "actor": actor,
                                "at": _now()}, "pending_human_action": None, "outcome": "REJECTED"}


def _find_own_commit(workspace: pathlib.Path, binding: str) -> str | None:
    ok, out = _git(["log", "--all", "--format=%H %s"], workspace, 20)
    if not ok:
        return None
    for line in out.splitlines():
        if binding[:16] in line:
            return line.split()[0]
    return None


def apply_change(state: WorkflowState) -> dict:
    """THE side-effecting stage, and the idempotent one.

    Precondition is code, not trust: approval.decision == approve AND
    approval.binding == proposal.binding AND sha256(content) still matches.
    Then: if our own commit (binding in subject) already exists in the
    workspace -> skip; if the workspace is gone -> fail safely; else write,
    commit, (push if configured), and checkpoint the commit sha."""
    proposal, approval = state.get("proposal") or {}, state.get("approval") or {}
    content = state.get("proposal_content") or ""
    if approval.get("decision") != "approve" or approval.get("binding") != proposal.get("binding") \
            or _sha(content) != proposal.get("new_content_sha256") \
            or write_tools._binding_hash(proposal.get("path", ""), content) != proposal.get("binding"):  # noqa: SLF001
        upd = _record_transition(state, "FAILED", "apply precondition failed (approval/binding)")
        return {**upd, "outcome": "FAILED", "error": "apply refused: approval does not bind to this content"}

    applied = state.get("applied") or {}
    # Derived, never merely recorded (see workspace_path).
    ws = pathlib.Path(state["workspace"]) if state.get("workspace") else workspace_path(state["workflow_id"])

    if ws.is_dir():
        existing = _find_own_commit(ws, proposal["binding"])
        if existing:
            upd = _record_transition(state, "APPLIED", f"already applied as {existing[:10]}; not applied again")
            # CRASH DRILL RUN 3 (A4): this branch returned no `workspace`, so the
            # next stage raised KeyError. Record the derived path here too.
            return {**upd, "workspace": str(ws),
                    "applied": {**applied, "binding": proposal["binding"], "commit_sha": existing,
                                "skipped_duplicate": True, "at": applied.get("at") or _now()}}
    elif applied.get("commit_sha"):
        # The checkpoint says the write happened, and the workspace that held
        # it no longer exists. Re-writing into a fresh clone would be a
        # second side effect nobody approved a second time.
        upd = _record_transition(state, "FAILED", "side effect recorded but its workspace is gone; refusing to apply again")
        return {**upd, "outcome": "FAILED",
                "error": f"applied commit {applied['commit_sha'][:10]} exists in the record but workspace "
                         f"{state.get('workspace')} no longer exists (push_status={applied.get('push_status')})"}

    if not ws.is_dir() or not _find_own_commit(ws, proposal["binding"]):
        ws, ok, out = _create_workspace(state["workflow_id"])
        if not ok:
            upd = _record_transition(state, "FAILED", "workspace clone failed")
            return {**upd, "outcome": "FAILED", "error": f"clone failed: {out[-400:]}"}

    target = ws / proposal["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    branch = f"workflow/{state['workflow_id']}"
    _git(["checkout", "-b", branch], ws, 15)
    _git(["config", "user.email", "workflow@agentic-software-delivery.local"], ws, 10)
    _git(["config", "user.name", "Agentic Software Delivery (durable workflow)"], ws, 10)
    _git(["add", "--", proposal["path"]], ws, 15)
    ok, out = _git(["commit", "-m", f"workflow {state['workflow_id']}: {proposal['new_value']!r} "
                                     f"[binding {proposal['binding'][:16]}]"], ws, 30)
    if not ok:
        upd = _record_transition(state, "FAILED", "commit failed")
        return {**upd, "outcome": "FAILED", "error": f"commit failed: {out[-400:]}", "workspace": str(ws)}
    _, sha = _git(["rev-parse", "HEAD"], ws, 10)
    _drill_pause("apply_committed")          # side effect done, checkpoint not yet
    push_status, push_msg = demo_execution.push_change(ws, branch)
    upd = _record_transition(state, "APPLIED", f"commit {sha.strip()[:10]} push={push_status}")
    return {**upd, "workspace": str(ws),
            "applied": {"binding": proposal["binding"], "commit_sha": sha.strip(),
                        "at": _now(), "push_status": push_status, "push_message": push_msg[:200],
                        "skipped_duplicate": False}}


def _ws(state: WorkflowState) -> pathlib.Path:
    """The workspace, from the checkpoint if it is there and derived if not."""
    return pathlib.Path(state["workspace"]) if state.get("workspace") else workspace_path(state["workflow_id"])


def compile_stage(state: WorkflowState) -> dict:
    _drill_pause("before_compile")           # apply is checkpointed, compile has not run
    ws = _ws(state)
    result = backend_execution.run_maven_compile(ws / "app")      # (ok, output)
    ok = bool(result[0])
    if not ok:
        upd = _record_transition(state, "FAILED", "compile failed")
        return {**upd, "build": _slim(result), "outcome": "FAILED", "error": "compile failed"}
    upd = _record_transition(state, "COMPILED")
    return {**upd, "build": _slim(result)}


def test_stage(state: WorkflowState) -> dict:
    ws = _ws(state)
    proposal = state.get("proposal") or {}
    if proposal.get("path", "").startswith("app/src/main/resources/static/"):
        # Same deterministic verdict the Workbench records for a static-resource
        # change: Maven's test phase has no mechanism to exercise it.
        upd = _record_transition(state, "TESTED", "NOT APPLICABLE: static resource, no Java test surface")
        return {**upd, "tests": {"status": "NOT_APPLICABLE",
                                 "reason": "single-line static resource substitution; no Java test surface"}}
    result = backend_execution.run_maven_targeted_tests(ws / "app")   # (ok, output)
    ok = bool(result[0])
    if not ok:
        upd = _record_transition(state, "FAILED", "tests failed")
        return {**upd, "tests": _slim(result), "outcome": "FAILED", "error": "tests failed"}
    upd = _record_transition(state, "TESTED")
    return {**upd, "tests": _slim(result)}


def verify_stage(state: WorkflowState) -> dict:
    """Deterministic: the approved content is what is on disk in the
    workspace, and our own commit is HEAD of the workflow branch."""
    ws = _ws(state)
    proposal, applied = state["proposal"], state.get("applied") or {}
    on_disk = (ws / proposal["path"]).read_text(encoding="utf-8") if (ws / proposal["path"]).is_file() else ""
    content_ok = _sha(on_disk) == proposal["new_content_sha256"]
    _, head = _git(["rev-parse", "HEAD"], ws, 10)
    commit_ok = head.strip() == applied.get("commit_sha")
    verification = {"content_matches_approved": content_ok, "head_is_own_commit": commit_ok,
                    "head": head.strip()[:12], "checked_at": _now()}
    if not (content_ok and commit_ok):
        upd = _record_transition(state, "FAILED", "verification failed")
        return {**upd, "verification": verification, "outcome": "FAILED", "error": "verification failed"}
    upd = _record_transition(state, "VERIFIED")
    return {**upd, "verification": verification}


def complete(state: WorkflowState) -> dict:
    upd = _record_transition(state, "COMPLETED")
    return {**upd, "outcome": "COMPLETED", "pending_human_action": None}


def _slim(result) -> dict:
    ok, out = result[0], result[1] if len(result) > 1 else ""
    return {"success": bool(ok), "output": str(out)[-1500:]}


# --- graph ------------------------------------------------------------------
def _route_after(node_state_key: str, ok_next: str):
    def _r(state: WorkflowState) -> str:
        return END if state.get("outcome") in TERMINAL_STATES else ok_next
    return _r


def build_graph(checkpointer, create_fn=None):
    g = StateGraph(WorkflowState)
    g.add_node("receive", receive)
    g.add_node("investigate", lambda s: investigate(s, create_fn=create_fn))
    g.add_node("propose", propose)
    g.add_node("mark_waiting", mark_waiting)
    g.add_node("wait_for_approval", wait_for_approval)
    g.add_node("apply", apply_change)
    g.add_node("compile", compile_stage)
    g.add_node("test", test_stage)
    g.add_node("verify", verify_stage)
    g.add_node("complete", complete)
    g.add_edge(START, "receive")
    g.add_conditional_edges("receive", _route_after("receive", "investigate"))
    g.add_edge("investigate", "propose")
    g.add_conditional_edges("propose", _route_after("propose", "mark_waiting"))
    g.add_edge("mark_waiting", "wait_for_approval")
    g.add_conditional_edges("wait_for_approval", _route_after("wait_for_approval", "apply"))
    g.add_conditional_edges("apply", _route_after("apply", "compile"))
    g.add_conditional_edges("compile", _route_after("compile", "test"))
    g.add_conditional_edges("test", _route_after("test", "verify"))
    g.add_conditional_edges("verify", _route_after("verify", "complete"))
    g.add_edge("complete", END)
    return g.compile(checkpointer=checkpointer)


# Checkpoints are persisted BEFORE the next node starts. LangGraph's default is
# "async" (checkpoint writes overlap the next step); crash-drill run 5 showed a
# kill at the start of compile losing the apply node's checkpoint. The apply
# node's idempotency covers a kill inside a node; this covers the boundary.
DURABILITY = "sync"


def _config(workflow_id: str) -> dict:
    return {"configurable": {"thread_id": workflow_id}}


# --- public API -------------------------------------------------------------
def start_workflow(requirement: str, checkpointer, create_fn=None, workflow_id: str | None = None) -> dict:
    """Runs until the approval interrupt (or a terminal state)."""
    wid = workflow_id or uuid.uuid4().hex[:12]
    graph = build_graph(checkpointer, create_fn)
    initial: WorkflowState = {"workflow_id": wid, "requirement": requirement, "state": None,
                              "completed_states": [], "transitions": [], "created_at": _now(),
                              "updated_at": _now(), "pending_human_action": None, "outcome": None}
    graph.invoke(initial, _config(wid), durability=DURABILITY)
    return describe_workflow(wid, checkpointer)


def resume_workflow(workflow_id: str, decision: str, binding: str, actor: str,
                    checkpointer, create_fn=None) -> dict:
    """The ONLY entry point that can carry a human decision into the graph.
    Called by the HTTP layer on a real click; never listed as a model tool."""
    desc = describe_workflow(workflow_id, checkpointer)
    if desc.get("status") != "ok":
        return desc
    if desc["state"] in TERMINAL_STATES:
        return {**desc, "status": "refused", "reason": f"workflow is {desc['state']} and cannot be resumed"}
    if desc["state"] != "WAITING_FOR_APPROVAL" or desc.get("pending_human_action") != "approve_or_reject":
        return {**desc, "status": "refused", "reason": f"workflow is not waiting for approval (state={desc['state']})"}
    graph = build_graph(checkpointer, create_fn)
    graph.invoke(Command(resume={"decision": decision, "binding": binding, "actor": actor}),
                 _config(workflow_id), durability=DURABILITY)
    return describe_workflow(workflow_id, checkpointer)


def continue_workflow(workflow_id: str, checkpointer, create_fn=None) -> dict:
    """Resume a workflow that was interrupted by a process death AFTER
    approval (no human input is needed or accepted here). If it is still
    waiting for approval, it stays waiting -- that is the correct outcome."""
    desc = describe_workflow(workflow_id, checkpointer)
    if desc.get("status") != "ok":
        return desc
    if desc["state"] in TERMINAL_STATES:
        return {**desc, "status": "refused", "reason": f"workflow is {desc['state']}"}
    if desc["state"] == "WAITING_FOR_APPROVAL":
        return {**desc, "status": "waiting", "reason": "still waiting for a human decision"}
    graph = build_graph(checkpointer, create_fn)
    graph.invoke(None, _config(workflow_id), durability=DURABILITY)
    return describe_workflow(workflow_id, checkpointer)


_REQUIRED_KEYS = ("workflow_id", "state", "completed_states", "transitions")


def describe_workflow(workflow_id: str, checkpointer) -> dict:
    """Operator-facing summary derived from the latest checkpoint. Corrupt or
    incomplete state is reported as such -- never partially trusted."""
    try:
        tup = checkpointer.get_tuple(_config(workflow_id))
    except Exception as exc:
        return {"status": "corrupt", "workflow_id": workflow_id, "reason": f"checkpoint unreadable: {exc}"[:300]}
    if tup is None:
        return {"status": "not_found", "workflow_id": workflow_id}
    values = (tup.checkpoint or {}).get("channel_values") or {}
    if not isinstance(values, dict) or any(k not in values for k in _REQUIRED_KEYS) \
            or values.get("workflow_id") != workflow_id or values.get("state") not in STATES + (None,):
        return {"status": "corrupt", "workflow_id": workflow_id,
                "reason": "checkpoint is missing required keys or holds an unknown state"}
    proposal = values.get("proposal") or {}
    return {
        "status": "ok",
        "workflow_id": workflow_id,
        "state": values.get("state"),
        "completed_states": values.get("completed_states") or [],
        "pending_human_action": values.get("pending_human_action"),
        "decision": values.get("decision"),
        "proposal": {k: proposal.get(k) for k in ("path", "old_line", "new_line", "binding", "risk_class")} if proposal else None,
        "approval": values.get("approval"),
        "applied": values.get("applied"),
        "workspace": values.get("workspace") or (str(workspace_path(workflow_id))
                                                 if values.get("applied") else None),
        "build": {k: v for k, v in (values.get("build") or {}).items() if k != "output"} or None,
        "tests": {k: v for k, v in (values.get("tests") or {}).items() if k != "output"} or None,
        "verification": values.get("verification"),
        "outcome": values.get("outcome"),
        "error": values.get("error"),
        "created_at": values.get("created_at"),
        "updated_at": values.get("updated_at"),
        "transitions": values.get("transitions") or [],
        "checkpoint_id": (tup.config or {}).get("configurable", {}).get("checkpoint_id"),
    }
