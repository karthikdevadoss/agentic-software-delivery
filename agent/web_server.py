"""
Agentic Software Delivery — Control Plane (minimal browser UI backend).

This is OUR PRODUCT's control surface, kept deliberately separate from the
Customer application (the TARGET software the agent operates on) — this
server never touches the Customer app's own UI/port.

Reuses agent_loop.py/execution_tools.py exactly as committed — adds no new
agent capability, no new tool, no shell access. Zero new dependencies:
starlette/uvicorn/sse-starlette were already installed transitively (via
the mcp/fastembed packages).

CRITICAL invariant, unchanged from the CLI: approval lives here, in this
trusted-host backend process, never inside TOOL_SCHEMAS or dispatch. The
browser's Approve/Reject buttons call a plain HTTP endpoint (/decide) that
only a human clicking the page can reach — the model has no route to it,
exactly as with the CLI's input()-based prompt, just swapped for an HTTP
request instead of a keystroke.

Known limitation: one run at a time (execution_tools.set_approval_prompt
is a process-global hook). Fine for this single-operator local MVP; would
need a per-run approval registry for real concurrent multi-run use.

Run: python agent/web_server.py
Then open http://127.0.0.1:8420
"""

import asyncio
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from main import get_api_key
from agent_loop import run_agent_loop
from execution_agent import EXECUTION_SYSTEM_PROMPT_SUFFIX
import dashboard_data
import event_ledger
import execution_tools
import metrics
import risk_policy
import sessions_data
import write_tools

WEB_DIR = Path(__file__).resolve().parent / "web"
REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
RUN_HISTORY_PATH = Path(__file__).resolve().parent / "web_run_history.jsonl"
PUBLIC_CUSTOMER_APP_URL = "https://agentic-delivery-customer-app-production.up.railway.app/"
RAILWAY_SERVICE_NAME = "agentic-delivery-customer-app"

# Maps a real tool name to a real, honest stage label — never fabricated,
# only ever shown when the corresponding tool is actually called.
STAGE_LABELS = {
    "list_repository_files": "REPOSITORY INVESTIGATION",
    "read_file": "REPOSITORY INVESTIGATION",
    "search_code": "REPOSITORY INVESTIGATION",
    "semantic_repository_search": "RAG / CONTEXT RETRIEVAL",
    "propose_source_change": "PROPOSING CHANGE",
    "apply_approved_source_change": "APPLYING CHANGE",
    "run_controlled_compile": "BUILDING",
    "run_controlled_tests": "TESTING",
}

# The single authoritative list of run.status values that mean "this run
# is done, no further events will ever arrive." Every consumer that needs
# to know whether a run is finished (SSE delivery, this module's own
# terminal checks) must go through _run_is_terminal()/this set rather
# than re-deriving its own list — that duplication is exactly what let
# NO_CHANGE_NEEDED be added as a real run.status value (see the
# "PROPOSING CHANGE"/"BUILDING"/etc. in-progress stages above) without
# stream_events() ever finding out, leaving completed runs' SSE streams
# open forever. If you add a new terminal run.status anywhere in this
# file, add it here in the same change.
TERMINAL_RUN_STATES = frozenset({"COMPLETED", "FAILED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN"})


def _run_is_terminal(run: "Run") -> bool:
    return run.status in TERMINAL_RUN_STATES


def _decide_deployment_outcome(deploy_online: bool, deploy_explicit_failure: bool, production_verified: bool) -> str:
    """The one place a trainer deploy's outcome is decided. Production
    verification (an independent HTTP check of the real public URL) is
    the primary evidence and is checked FIRST — deliberately, so it can
    never be overridden by a Railway CLI signal in either direction. See
    docs/LESSONS.md: a CLI decoding glitch or poll timeout produced real
    false "deployment failed" results on genuinely successful deploys
    three times before this function existed.

    Returns one of the three real outcomes this decision can produce:
    COMPLETED, FAILED, or DEPLOYMENT_STATUS_UNKNOWN (genuine uncertainty
    — never silently folded into FAILED)."""
    if production_verified:
        return "COMPLETED"
    if deploy_explicit_failure:
        return "FAILED"
    return "DEPLOYMENT_STATUS_UNKNOWN"


API_KEY = None
RUNS = {}
_CURRENT_RUN_ID = None  # process-global: metrics.py is single-run-at-a-time (see its own docstring)


def _run_source(run_id: str) -> str:
    """Honest provenance tag derived from this codebase's own existing
    run_id naming convention (mock-/trainer-/plain hex) — not a new
    concept, just carried into the event ledger's `source` field."""
    if run_id.startswith("mock-"):
        return "workbench_mock"
    if run_id.startswith("trainer-"):
        return "workbench_trainer"
    return "workbench"


def _current_git_commit():
    """Real source git commit BEFORE the run (Section 10's reproducibility
    manifest) — a genuine subprocess call, not a cached/guessed value."""
    ok, out = _run_controlled(["git", "rev-parse", "--short", "HEAD"], REPO_ROOT, 10)
    return out.strip() if ok else None


_STAGE_TO_CANONICAL_TYPE = {
    "COMPLETED": "stage_completed",
    "FAILED": "run_failed",
    "NO_CHANGE_NEEDED": "run_no_change",
    "DEPLOYMENT_STATUS_UNKNOWN": "deployment_status_unknown",
}


def _canonical_event_type(internal_type: str, data: dict) -> str:
    """Maps this file's actual internal Run.emit() event types onto the
    canonical taxonomy (CLAUDE.md's event-ledger Section 3). Only maps
    events genuinely emitted today — nothing here is invented to fill out
    the taxonomy."""
    if internal_type == "stage":
        return _STAGE_TO_CANONICAL_TYPE.get(data.get("stage"), "stage_started")
    if internal_type == "tool_result":
        return "tool_call_completed" if data.get("success") else "tool_call_failed"
    if internal_type == "final_result":
        return "run_completed"
    if internal_type == "deployment":
        if data.get("verified"):
            return "deployment_completed"
        return "deployment_failed" if data.get("railway_cli_reported_failure") else "deployment_status"
    return {
        "tool_call": "tool_call_started",
        "proposal": "change_proposed",
        "approval_decision": "authorization_decision",
        "risk_assessment": "risk_assessment",
        "commit": "commit_created",
        "no_change_needed": "run_no_change",
        "error": "error",
    }.get(internal_type, internal_type)


def _record_ledger_event(run: "Run", internal_type: str, data: dict) -> None:
    """Write-through bridge: every Run.emit() call also durably persists to
    the event ledger immediately, not batched to run-end. Never affects
    run.events/run.status either way — event_ledger.record_event() itself
    never raises (falls back to the local spool on any failure)."""
    event_ledger.record_event(
        _canonical_event_type(internal_type, data),
        run_id=run.id,
        source=_run_source(run.id),
        service="web_server",
        environment="local",
        git_commit=run.git_commit_before,
        status=run.status,
        stage=data.get("stage") if internal_type == "stage" else None,
        tool_name=data.get("tool"),
        duration_ms=data.get("duration_ms"),
        training_eligibility=event_ledger.TRAINING_ALLOWED_AFTER_REDACTION,
        payload=data,
    )


def _on_model_usage(usage_event: dict) -> None:
    """Bridges metrics.py's real Anthropic API usage into the ledger the
    moment it's recorded (see metrics.set_usage_sink). Correlated via
    _CURRENT_RUN_ID because metrics.py is itself process-global/
    single-run-at-a-time (see its own module docstring) — not a new
    limitation introduced here."""
    event_ledger.record_event(
        "model_usage",
        run_id=_CURRENT_RUN_ID,
        source=_run_source(_CURRENT_RUN_ID) if _CURRENT_RUN_ID else None,
        service="web_server",
        environment="local",
        provider=usage_event["provider"],
        model=usage_event["model"],
        input_tokens=usage_event["input_tokens"],
        output_tokens=usage_event["output_tokens"],
        cache_read_tokens=usage_event.get("cache_read_input_tokens"),
        cache_write_tokens=usage_event.get("cache_creation_input_tokens"),
        training_eligibility=event_ledger.OPERATIONS_ONLY,
    )


metrics.set_usage_sink(_on_model_usage)


class Run:
    def __init__(self, run_id: str, requirement: str):
        self.id = run_id
        self.requirement = requirement
        self.status = "UNDERSTANDING REQUIREMENT"
        self.events = []
        self.result_text = None
        self.pending_approvals = {}
        self.trainer_changed_path = None  # set by _trainer_approval_prompt_factory
        self.trainer_usage_start_index = 0  # set by the trainer route before the thread starts
        self.git_commit_before = _current_git_commit()
        self._lock = threading.Lock()
        event_ledger.record_event(
            "run_started", run_id=self.id, source=_run_source(self.id),
            service="web_server", environment="local", git_commit=self.git_commit_before,
            status=self.status, training_eligibility=event_ledger.TRAINING_ALLOWED_AFTER_REDACTION,
            payload={"requirement": requirement},
        )

    def emit(self, event_type: str, data: dict) -> None:
        with self._lock:
            self.events.append({"type": event_type, "ts": time.time(), **data})
        _record_ledger_event(self, event_type, data)

    def events_from(self, index: int):
        with self._lock:
            return list(self.events[index:]), len(self.events)


def _safe_input_summary(name: str, tool_input: dict) -> str:
    tool_input = tool_input or {}
    if name == "read_file":
        return tool_input.get("path", "")
    if name == "list_repository_files":
        return tool_input.get("directory", ".")
    if name in ("search_code", "semantic_repository_search"):
        return tool_input.get("query", "")
    if name == "propose_source_change":
        return tool_input.get("path", "")
    if name == "apply_approved_source_change":
        return tool_input.get("edit_id", "")
    return ""


VERIFICATION_TOOLS = {"run_controlled_compile", "run_controlled_tests"}
MAX_SUMMARY_CHARS = 600


def _bounded_summary(result_text: str) -> str:
    """A short, real excerpt of actual compile/test output — not a fake
    metric, not a parsed test count (Maven's own text format isn't reliable
    enough to parse into invented pass/fail counts). Tail-biased: real
    Maven failures are almost always reported near the end of the output."""
    text = result_text or ""
    if len(text) <= MAX_SUMMARY_CHARS:
        return text
    return "...\n" + text[-MAX_SUMMARY_CHARS:]


def _persist_run_history(run: Run, usage_start_index: int = None, extra: dict = None) -> None:
    """Append one compact, real record of this run to a small local JSONL
    log — the smallest persistence that survives a server restart, so the
    Dashboard/Sessions pages have something to show beyond in-memory
    state. Never touches Customer app files; this is our own product's
    operational log."""
    tool_calls = [e for e in run.events if e["type"] == "tool_call"]
    approval = next((e for e in run.events if e["type"] == "approval_decision"), None)
    apply_result = next((e for e in run.events if e["type"] == "tool_result" and e.get("tool") == "apply_approved_source_change"), None)
    compile_result = next((e for e in run.events if e["type"] == "tool_result" and e.get("tool") == "run_controlled_compile"), None)
    test_result = next((e for e in run.events if e["type"] == "tool_result" and e.get("tool") == "run_controlled_tests"), None)
    error = next((e for e in run.events if e["type"] == "error"), None)

    model_usage = None
    if usage_start_index is not None:
        # Real API-reported usage for exactly the model calls this run made
        # (metrics.py is process-global, so slice to this run's window).
        # None for mock runs, which never call the Anthropic API at all.
        events = metrics.get_model_usage_events()[usage_start_index:]
        if events:
            model_usage = {
                "provider": events[0]["provider"],
                "model": events[0]["model"],
                "api_calls": len(events),
                "input_tokens": sum(e["input_tokens"] for e in events),
                "output_tokens": sum(e["output_tokens"] for e in events),
            }

    record = {
        "run_id": run.id,
        "is_mock": run.id.startswith("mock-"),
        "requirement_excerpt": (run.requirement or "")[:200],
        "final_status": run.status,
        "started_ts": run.events[0]["ts"] if run.events else None,
        "ended_ts": run.events[-1]["ts"] if run.events else None,
        "tool_calls_total": len(tool_calls),
        "approval_decision": approval["decision"] if approval else None,
        "apply_succeeded": apply_result["success"] if apply_result else None,
        "compile": {"success": compile_result["success"], "duration_ms": compile_result["duration_ms"]} if compile_result else None,
        "test": {"success": test_result["success"], "duration_ms": test_result["duration_ms"]} if test_result else None,
        "backend_error": error["message"] if error else None,
        "model_usage": model_usage,
    }
    if extra:
        record.update(extra)
    try:
        with RUN_HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # dashboard telemetry is best-effort, never fatal to a run


def _make_dispatch_fn(run: Run):
    def dispatch(name, tool_input):
        stage = STAGE_LABELS.get(name)
        if stage:
            run.status = stage
            run.emit("stage", {"stage": stage})
        run.emit("tool_call", {"tool": name, "input_summary": _safe_input_summary(name, tool_input)})

        start = time.monotonic()
        result_text, is_error = execution_tools.dispatch_execution_tool_call(name, tool_input)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        event_data = {
            "tool": name, "success": not is_error,
            "duration_ms": duration_ms, "result_size": len(result_text),
        }
        if name in VERIFICATION_TOOLS:
            event_data["summary"] = _bounded_summary(result_text)
        run.emit("tool_result", event_data)
        return result_text, is_error
    return dispatch


def _web_approval_prompt_factory(run: Run):
    def prompt(edit) -> bool:
        decision_queue = queue.Queue()
        run.pending_approvals[edit.id] = decision_queue
        run.status = "WAITING FOR HUMAN APPROVAL"
        run.emit("proposal", {
            "edit_id": edit.id, "path": edit.path, "diff": edit.diff,
            "is_new_file": edit.is_new_file,
        })
        # BLOCKS this run's background thread until a real POST /decide
        # arrives from the browser — the model cannot supply this itself.
        decision = decision_queue.get()
        run.emit("approval_decision", {"edit_id": edit.id, "decision": decision})
        return decision == "approve"
    return prompt


def _run_agent_thread(run: Run) -> None:
    global _CURRENT_RUN_ID
    execution_tools.set_approval_prompt(_web_approval_prompt_factory(run))
    usage_start_index = len(metrics.get_model_usage_events())
    _CURRENT_RUN_ID = run.id
    try:
        run.status = "PLANNING"
        run.emit("stage", {"stage": "PLANNING"})
        result = run_agent_loop(
            run.requirement, API_KEY,
            tool_schemas=execution_tools.EXECUTION_TOOL_SCHEMAS,
            dispatch_fn=_make_dispatch_fn(run),
            system_prompt_suffix=EXECUTION_SYSTEM_PROMPT_SUFFIX,
        )
        run.result_text = result
        run.status = "COMPLETED"
        run.emit("stage", {"stage": "COMPLETED"})
        run.emit("final_result", {"text": result})
    except Exception as exc:  # noqa: BLE001 - never crash the server for a run failure
        run.status = "FAILED"
        run.emit("stage", {"stage": "FAILED"})
        run.emit("error", {"message": str(exc)})
    finally:
        execution_tools.set_approval_prompt(execution_tools._default_approval_prompt)
        _CURRENT_RUN_ID = None
        _persist_run_history(run, usage_start_index=usage_start_index)


def _run_mock_thread(run: Run) -> None:
    """DEV/VERIFICATION ONLY — never calls the Anthropic API, never touches
    real source, never calls a real tool. Replays a fixed, clearly-labeled
    event sequence through the exact same Run/SSE plumbing the real agent
    uses, so the frontend fix can be re-verified after a server restart
    without spending real tokens. Durations match this session's actual
    completed real run (compile ~15.3s, tests ~19.0s) for a realistic
    reproduction of the reported bug. Still requires a real human click on
    Approve/Reject — this only fakes the model/tool side, not the approval
    boundary, which is the one thing we must never simulate."""
    try:
        run.status = "PLANNING"
        run.emit("stage", {"stage": "PLANNING"})
        time.sleep(0.3)

        run.status = "REPOSITORY INVESTIGATION"
        run.emit("stage", {"stage": "REPOSITORY INVESTIGATION"})
        for tool, arg in [
            ("list_repository_files", "app/src/test/java/com/example/customer"),
            ("list_repository_files", "app/src/main/java/com/example/customer"),
        ]:
            run.emit("tool_call", {"tool": tool, "input_summary": arg})
            time.sleep(0.2)
            run.emit("tool_result", {"tool": tool, "success": True, "duration_ms": 12.0, "result_size": 90})

        run.status = "PROPOSING CHANGE"
        run.emit("stage", {"stage": "PROPOSING CHANGE"})
        run.emit("tool_call", {"tool": "propose_source_change", "input_summary": "app/src/test/java/com/example/customer/MockDemoTest.java"})

        decision_queue = queue.Queue()
        edit_id = "mockdemo"
        run.pending_approvals[edit_id] = decision_queue
        run.status = "WAITING FOR HUMAN APPROVAL"
        run.emit("proposal", {
            "edit_id": edit_id,
            "path": "app/src/test/java/com/example/customer/MockDemoTest.java",
            "diff": "--- /dev/null\n+++ b/app/src/test/java/com/example/customer/MockDemoTest.java\n"
                    "@@ -0,0 +1,4 @@\n+package com.example.customer;\n+\n+public class MockDemoTest {\n+}\n",
            "is_new_file": True,
        })
        decision = decision_queue.get()  # still a REAL blocking wait on a REAL browser click
        run.emit("approval_decision", {"edit_id": edit_id, "decision": decision})

        if decision != "approve":
            run.status = "COMPLETED"
            run.emit("stage", {"stage": "COMPLETED"})
            run.emit("final_result", {"text": "[MOCK RUN] Proposal was rejected by the human operator. No change applied."})
            return

        run.status = "APPLYING CHANGE"
        run.emit("stage", {"stage": "APPLYING CHANGE"})
        run.emit("tool_call", {"tool": "apply_approved_source_change", "input_summary": edit_id})
        time.sleep(0.2)
        run.emit("tool_result", {"tool": "apply_approved_source_change", "success": True, "duration_ms": 3.0, "result_size": 60})

        run.status = "BUILDING"
        run.emit("stage", {"stage": "BUILDING"})
        run.emit("tool_call", {"tool": "run_controlled_compile", "input_summary": ""})
        time.sleep(1.0)  # shortened stand-in for the real ~15.3s wait
        run.emit("tool_result", {
            "tool": "run_controlled_compile", "success": True, "duration_ms": 15327.0,
            "result_size": 340, "summary": "[MOCK] compile SUCCEEDED in 15327.0ms\nBUILD SUCCESS",
        })

        run.status = "TESTING"
        run.emit("stage", {"stage": "TESTING"})
        run.emit("tool_call", {"tool": "run_controlled_tests", "input_summary": ""})
        time.sleep(1.0)  # shortened stand-in for the real ~19.0s wait
        run.emit("tool_result", {
            "tool": "run_controlled_tests", "success": True, "duration_ms": 18972.0,
            "result_size": 310, "summary": "[MOCK] test SUCCEEDED in 18972.0ms\nBUILD SUCCESS (0 tests run)",
        })

        run.result_text = (
            "[MOCK RUN — no Anthropic API call was made] Proposal approved by the "
            "human operator, applied, compiled successfully, and tests ran "
            "successfully. This text simulates the agent's closing summary."
        )
        run.status = "COMPLETED"
        run.emit("stage", {"stage": "COMPLETED"})
        run.emit("final_result", {"text": run.result_text})
    except Exception as exc:  # noqa: BLE001
        run.status = "FAILED"
        run.emit("stage", {"stage": "FAILED"})
        run.emit("error", {"message": f"[MOCK RUN] {exc}"})
    finally:
        _persist_run_history(run)


# --- Trainer demo: risk-gated autonomous execution -----------------------
#
# Separate, additive code path — never replaces or weakens the default
# human-approval flow used by /api/runs. A requirement only ever reaches
# _run_trainer_thread if risk_policy.classify() (deterministic, text-level,
# server-side) returned decision="auto". Even then, every proposed file
# still passes through write_tools._validate_write_scope() exactly as any
# other edit would — the trainer path does not bypass that check, it just
# replaces the *human* approval click with an automatic one for edits that
# already made it past both gates.

TRAINER_SYSTEM_PROMPT_SUFFIX = """

This session is a PUBLIC LIVE DEMO with automatic approval — there is no
human watching to approve your proposal, so make the SMALLEST possible
change that satisfies the requirement. Strongly prefer touching exactly
ONE file. For visual/UI requirements, prefer editing
app/src/main/resources/static/index.html directly. Do not make
speculative or unrelated changes. After applying, you MUST run the
controlled compile (and tests if relevant) and report the real result.
Your final summary must be exactly one crisp sentence describing exactly
what changed.
"""


def _trainer_approval_prompt_factory(run: "Run"):
    """Auto-approves — by the time propose_source_change reaches this
    prompt, write_tools.propose_edit() has ALREADY enforced path/scope/
    extension rules and raised on any violation, so anything reaching here
    is already inside the approved demo scope. Decision is recorded as
    'policy', never mislabeled as a human decision."""
    def prompt(edit) -> bool:
        run.trainer_changed_path = edit.path
        run.emit("approval_decision", {
            "edit_id": edit.id, "decision": "approve",
            "decided_by": "risk_policy (auto — no human in the loop for this demo tier)",
        })
        return True
    return prompt


def _run_controlled(argv, cwd, timeout_s):
    """Same controlled-subprocess discipline as build_tools.py: explicit
    argv list, shell=False, bounded timeout, output captured not streamed
    raw to the trainer. Resolves argv[0] via shutil.which() first — on
    Windows, CLI tools installed through npm (railway, vercel) are .cmd
    shims, and CreateProcess cannot launch a bare 'railway' without an
    extension; resolving the real path still avoids shell=True entirely.

    encoding="utf-8" is explicit and load-bearing, not a guess: captured
    Railway CLI output was confirmed byte-for-byte to be well-formed
    UTF-8 (its status bullet "●" is U+25CF, encoded as the 3 bytes
    E2 97 8F). Without an explicit encoding, Python's text=True falls
    back to the OS locale's codepage — cp1252 on this machine — which has
    no mapping for byte 0x8F (the last byte of that sequence) and raises
    UnicodeDecodeError inside subprocess.Popen's background reader
    threads. That exception doesn't propagate to this function's return
    value; the practical effect was captured output silently coming back
    empty/truncated, which then failed the "Online" in status_out check
    even on a genuinely successful deploy. errors="replace" is defense
    in depth for any future byte sequence that isn't valid UTF-8 either
    — it substitutes U+FFFD rather than raising, so a real decoding
    anomaly becomes visible in the returned text instead of crashing a
    background thread invisibly again."""
    resolved = shutil.which(argv[0])
    argv = [resolved or argv[0], *argv[1:]]
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout_s, shell=False,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout_s}s"
    except OSError as exc:
        return False, str(exc)


def _fetch_public_app(timeout_s=15):
    try:
        with urllib.request.urlopen(PUBLIC_CUSTOMER_APP_URL, timeout=timeout_s) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        return None, str(exc)


def _run_trainer_thread(run: "Run", requirement: str, assessment: dict) -> None:
    global _CURRENT_RUN_ID
    run.trainer_changed_path = None
    execution_tools.set_approval_prompt(_trainer_approval_prompt_factory(run))
    baseline_status, baseline_html = _fetch_public_app()
    _CURRENT_RUN_ID = run.id

    try:
        run.status = "PLANNING"
        run.emit("stage", {"stage": "PLANNING"})
        result = run_agent_loop(
            requirement, API_KEY,
            tool_schemas=execution_tools.EXECUTION_TOOL_SCHEMAS,
            dispatch_fn=_make_dispatch_fn(run),
            system_prompt_suffix=EXECUTION_SYSTEM_PROMPT_SUFFIX + TRAINER_SYSTEM_PROMPT_SUFFIX,
        )
        run.result_text = result

        # An edit was PROPOSED (regardless of whether it was later applied) —
        # this is the deterministic signal for "the agent attempted a code
        # change" vs. "the agent investigated and made a deliberate decision
        # not to change anything." Only the latter can ever be a legitimate
        # no-op; it is never inferred from apply/compile/test outcomes alone.
        apply_attempted = any(e for e in run.events if e["type"] == "tool_call" and e.get("tool") == "propose_source_change")

        if not apply_attempted:
            # No write authority was ever exercised either way — nothing was
            # proposed, so nothing could have been applied/compiled/deployed.
            # The only question is how to LABEL this to the trainer: a
            # keyword check on the agent's own investigation summary decides
            # ALREADY SATISFIED vs. a genuine inconclusive failure. This
            # check only picks a UI label — it grants no additional
            # capability in either branch.
            if risk_policy.looks_already_satisfied(result):
                run.status = "NO_CHANGE_NEEDED"
                run.emit("no_change_needed", {
                    "reason": "Repository investigation showed the requirement is already implemented. No code was modified, nothing was compiled, nothing was deployed.",
                })
                run.emit("stage", {"stage": "NO_CHANGE_NEEDED"})
                run.emit("final_result", {"text": result})
                return
            run.emit("error", {"message": "Agent investigated the repository but did not propose a code change and did not indicate the requirement was already satisfied — inconclusive, not deploying."})
            run.status = "FAILED"
            run.emit("stage", {"stage": "FAILED"})
            return

        apply_ok = any(e for e in run.events if e["type"] == "tool_result" and e.get("tool") == "apply_approved_source_change" and e.get("success"))
        compile_ok = any(e for e in run.events if e["type"] == "tool_result" and e.get("tool") == "run_controlled_compile" and e.get("success"))
        test_events = [e for e in run.events if e["type"] == "tool_result" and e.get("tool") == "run_controlled_tests"]
        test_ok = (not test_events) or all(e.get("success") for e in test_events)

        if not (apply_ok and compile_ok and test_ok):
            run.emit("error", {"message": "Implementation did not pass verification (apply/compile/test) — not deployed. Production is unchanged."})
            run.status = "FAILED"
            run.emit("stage", {"stage": "FAILED"})
            return

        if run.trainer_changed_path is None:
            run.emit("error", {"message": "No file change was actually applied — nothing to deploy."})
            run.status = "FAILED"
            run.emit("stage", {"stage": "FAILED"})
            return

        # COMMIT — only the exact file the agent changed, never a blanket `git add -A`.
        run.status = "COMMITTING"
        run.emit("stage", {"stage": "COMMITTING"})
        ok, out = _run_controlled(["git", "add", "--", run.trainer_changed_path], REPO_ROOT, 30)
        if ok:
            commit_msg = f"Trainer demo: {requirement.strip()[:100]}"
            ok, out = _run_controlled(["git", "commit", "-m", commit_msg], REPO_ROOT, 30)
        if not ok:
            run.emit("error", {"message": f"Git commit failed, deployment aborted: {out[-400:]}"})
            run.status = "FAILED"
            run.emit("stage", {"stage": "FAILED"})
            return
        _, sha_out = _run_controlled(["git", "rev-parse", "--short", "HEAD"], REPO_ROOT, 15)
        production_commit = sha_out.strip()
        run.emit("commit", {"sha": production_commit, "path": run.trainer_changed_path})

        # DEPLOY
        run.status = "DEPLOYING"
        run.emit("stage", {"stage": "DEPLOYING"})
        deploy_ok, deploy_out = _run_controlled(
            ["railway", "up", "--detach", "--service", RAILWAY_SERVICE_NAME], APP_DIR, 60)
        if not deploy_ok:
            run.emit("error", {"message": f"Railway deploy upload failed: {deploy_out[-400:]}"})
            run.status = "FAILED"
            run.emit("stage", {"stage": "FAILED"})
            return

        deploy_online = False
        deploy_explicit_failure = False
        # A cold Nixpacks/Maven build on this Railway project (no layer
        # cache reuse between deploys) has been observed taking as long
        # as ~11.5 minutes for real. 90 x 10s = 15 minutes gives real
        # margin. This loop is a SIGNAL for the decision below, never the
        # sole verdict — see the production-verification step that
        # always runs next regardless of what this loop saw.
        for _ in range(90):  # up to ~15 minutes
            time.sleep(10)
            _, status_out = _run_controlled(["railway", "status"], APP_DIR, 20)
            if "Online" in status_out:
                deploy_online = True
                break
            if "Failed" in status_out or "Crashed" in status_out:
                deploy_explicit_failure = True
                break

        # VERIFY — production reality is the primary source of truth.
        # Permanent rule (docs/LESSONS.md): a CLI decoding glitch or a
        # poll timeout is NOT the same as a verified deployment failure.
        # This independent HTTP check runs regardless of what the loop
        # above concluded, and its result decides the outcome below.
        run.status = "VERIFYING PRODUCTION"
        run.emit("stage", {"stage": "VERIFYING PRODUCTION"})
        after_status, after_html = _fetch_public_app()
        verified = after_status == 200
        content_changed = bool(after_html) and after_html != baseline_html
        run.emit("deployment", {
            "production_commit": production_commit,
            "public_url": PUBLIC_CUSTOMER_APP_URL,
            "http_status": after_status,
            "content_changed_from_baseline": content_changed,
            "verified": verified,
            "railway_cli_reported_online": deploy_online,
            "railway_cli_reported_failure": deploy_explicit_failure,
        })

        outcome = _decide_deployment_outcome(deploy_online, deploy_explicit_failure, verified)
        if outcome == "COMPLETED":
            run.status = "COMPLETED"
            run.emit("stage", {"stage": "COMPLETED"})
            run.emit("final_result", {"text": result})
        elif outcome == "FAILED":
            run.emit("error", {"message": "Railway reported a failed/crashed deployment, and production is not reachable."})
            run.status = "FAILED"
            run.emit("stage", {"stage": "FAILED"})
        else:  # DEPLOYMENT_STATUS_UNKNOWN — genuinely inconclusive, not a confirmed failure
            run.emit("error", {"message": "Deployment status could not be confirmed: Railway CLI polling did not report Online within the wait window, and production verification did not return HTTP 200. This is NOT a confirmed failure — check manually."})
            run.status = "DEPLOYMENT_STATUS_UNKNOWN"
            run.emit("stage", {"stage": "DEPLOYMENT_STATUS_UNKNOWN"})
    except Exception as exc:  # noqa: BLE001
        run.emit("error", {"message": str(exc)})
        run.status = "FAILED"
        run.emit("stage", {"stage": "FAILED"})
    finally:
        execution_tools.set_approval_prompt(execution_tools._default_approval_prompt)
        _CURRENT_RUN_ID = None
        commit_event = next((e for e in run.events if e["type"] == "commit"), None)
        deploy_event = next((e for e in run.events if e["type"] == "deployment"), None)
        _persist_run_history(run, usage_start_index=run.trainer_usage_start_index, extra={
            "session_type": "trainer_demo",
            "requirement": requirement,
            "risk_assessment": assessment,
            "production_commit": commit_event["sha"] if commit_event else None,
            "deployment": deploy_event if deploy_event else None,
        })


# --- HTTP routes ---------------------------------------------------------

async def start_run(request: Request):
    body = await request.json()
    requirement = (body.get("requirement") or "").strip()
    if not requirement:
        return JSONResponse({"error": "requirement is required"}, status_code=400)

    run_id = uuid.uuid4().hex[:8]
    run = Run(run_id, requirement)
    RUNS[run_id] = run

    thread = threading.Thread(target=_run_agent_thread, args=(run,), daemon=True)
    thread.start()
    return JSONResponse({"run_id": run_id})


async def start_mock_run(request: Request):
    """DEV/VERIFICATION ONLY: re-exercise the SSE/UI plumbing (including a
    real human approval click) without any Anthropic API call. See
    _run_mock_thread's docstring."""
    run_id = "mock-" + uuid.uuid4().hex[:8]
    run = Run(run_id, "[MOCK RUN] UI verification — no real agent call")
    RUNS[run_id] = run
    thread = threading.Thread(target=_run_mock_thread, args=(run,), daemon=True)
    thread.start()
    return JSONResponse({"run_id": run_id})


async def assess_trainer_requirement(request: Request):
    """Cheap, synchronous, zero-API-cost — lets the trainer UI show the
    risk/complexity decision before committing to a real agent run."""
    body = await request.json()
    requirement = (body.get("requirement") or "").strip()
    return JSONResponse(risk_policy.classify(requirement))


async def start_trainer_run(request: Request):
    body = await request.json()
    requirement = (body.get("requirement") or "").strip()
    if not requirement:
        return JSONResponse({"error": "requirement is required"}, status_code=400)

    # Re-classify server-side — never trust a client-displayed assessment
    # as the actual authorization decision.
    assessment = risk_policy.classify(requirement)
    if assessment["decision"] != "auto":
        return JSONResponse({"blocked": True, "assessment": assessment})

    run_id = "trainer-" + uuid.uuid4().hex[:8]
    run = Run(run_id, requirement)
    run.trainer_usage_start_index = len(metrics.get_model_usage_events())
    RUNS[run_id] = run
    run.emit("risk_assessment", assessment)

    thread = threading.Thread(target=_run_trainer_thread, args=(run, requirement, assessment), daemon=True)
    thread.start()
    return JSONResponse({"blocked": False, "run_id": run_id, "assessment": assessment})


async def workbench_page(request: Request):
    return FileResponse(str(WEB_DIR / "workbench.html"))


async def control_plane_page(request: Request):
    """Internal/debug human-approval tool — not linked from public
    navigation (see docs/DECISIONS.md), but deliberately not deleted."""
    return FileResponse(str(WEB_DIR / "control-plane.html"))


async def redirect_trainer_to_workbench(request: Request):
    return RedirectResponse(url="/workbench", status_code=308)


async def redirect_sessions_to_usage(request: Request):
    return RedirectResponse(url="/usage", status_code=308)


async def learn_page(request: Request):
    return FileResponse(str(WEB_DIR / "learn.html"))


async def profile_page(request: Request):
    return FileResponse(str(WEB_DIR / "profile.html"))


async def get_run(request: Request):
    run = RUNS.get(request.path_params["run_id"])
    if run is None:
        return JSONResponse({"error": "no such run"}, status_code=404)
    return JSONResponse({
        "id": run.id, "status": run.status,
        "events": run.events, "result": run.result_text,
    })


async def _generate_run_events(run: "Run", is_disconnected):
    """is_disconnected: async callable, () -> bool (normally
    request.is_disconnected). Extracted from stream_events as a top-level
    function so this exact termination logic — the thing that was
    actually broken — can be driven directly in a test with a fake Run
    and a fake is_disconnected, without needing a real ASGI request."""
    sent = 0
    while True:
        if await is_disconnected():
            break
        new_events, sent = run.events_from(sent)
        for evt in new_events:
            yield {"event": evt["type"], "data": json.dumps(evt)}
        if _run_is_terminal(run) and not new_events:
            break
        await asyncio.sleep(0.3)


async def stream_events(request: Request):
    run = RUNS.get(request.path_params["run_id"])
    if run is None:
        return JSONResponse({"error": "no such run"}, status_code=404)

    return EventSourceResponse(_generate_run_events(run, request.is_disconnected))


async def decide(request: Request):
    run = RUNS.get(request.path_params["run_id"])
    if run is None:
        return JSONResponse({"error": "no such run"}, status_code=404)

    body = await request.json()
    edit_id = body.get("edit_id")
    decision = body.get("decision")
    if decision not in ("approve", "reject"):
        return JSONResponse({"error": "decision must be 'approve' or 'reject'"}, status_code=400)

    pending = run.pending_approvals.get(edit_id)
    if pending is None:
        return JSONResponse({"error": "no pending approval for that edit_id"}, status_code=404)

    pending.put(decision)
    return JSONResponse({"ok": True})


async def get_dashboard_data(request: Request):
    return JSONResponse(dashboard_data.build_dashboard_snapshot())


async def dashboard_page(request: Request):
    return FileResponse(str(WEB_DIR / "dashboard.html"))


async def get_sessions_data(request: Request):
    return JSONResponse(sessions_data.build_sessions_snapshot())


async def usage_page(request: Request):
    return FileResponse(str(WEB_DIR / "usage.html"))


async def start_dev_session_route(request: Request):
    body = await request.json()
    goal = (body.get("goal") or "").strip()
    if not goal:
        return JSONResponse({"error": "goal is required"}, status_code=400)
    rec = sessions_data.start_dev_session(
        goal, ai_assistant=body.get("ai_assistant"), model=body.get("model"))
    return JSONResponse(rec)


async def stop_dev_session_route(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        return JSONResponse({"error": "session_id is required"}, status_code=400)
    rec = sessions_data.stop_dev_session(session_id)
    status_code = 404 if "error" in rec else 200
    return JSONResponse(rec, status_code=status_code)


routes = [
    Route("/api/runs", start_run, methods=["POST"]),
    Route("/api/runs/mock", start_mock_run, methods=["POST"]),
    Route("/api/dashboard", get_dashboard_data, methods=["GET"]),
    Route("/api/sessions", get_sessions_data, methods=["GET"]),
    Route("/api/dev-sessions/start", start_dev_session_route, methods=["POST"]),
    Route("/api/dev-sessions/stop", stop_dev_session_route, methods=["POST"]),
    Route("/api/trainer/assess", assess_trainer_requirement, methods=["POST"]),
    Route("/api/trainer/runs", start_trainer_run, methods=["POST"]),
    Route("/api/runs/{run_id}", get_run, methods=["GET"]),
    Route("/api/runs/{run_id}/events", stream_events, methods=["GET"]),
    Route("/api/runs/{run_id}/decide", decide, methods=["POST"]),
    # Five public surfaces (see docs/COMPANY_VISION.md's public product
    # structure decision). "/" and "/workbench" both serve the same public
    # preview page — Workbench is the flagship/default landing surface.
    Route("/", workbench_page, methods=["GET"]),
    Route("/workbench", workbench_page, methods=["GET"]),
    Route("/dashboard", dashboard_page, methods=["GET"]),
    Route("/usage", usage_page, methods=["GET"]),
    Route("/learn", learn_page, methods=["GET"]),
    Route("/profile", profile_page, methods=["GET"]),
    # Retired public terminology — kept as redirects, not dead links.
    Route("/trainer", redirect_trainer_to_workbench, methods=["GET"]),
    Route("/sessions", redirect_sessions_to_usage, methods=["GET"]),
    # Internal/debug tool — deliberately not in public navigation.
    Route("/control-plane", control_plane_page, methods=["GET"]),
    Mount("/", app=StaticFiles(directory=str(WEB_DIR), html=True), name="static"),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    API_KEY = get_api_key()  # fails fast here, not mid-request, if missing
    print("Agentic Software Delivery: http://127.0.0.1:8420 (Workbench/Dashboard/Usage/Learn/Profile)", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=8420)
