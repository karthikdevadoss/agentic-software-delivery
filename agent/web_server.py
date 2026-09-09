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
import sys
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from main import get_api_key
from agent_loop import run_agent_loop
from execution_agent import EXECUTION_SYSTEM_PROMPT_SUFFIX
import dashboard_data
import execution_tools
import metrics
import sessions_data
import write_tools

WEB_DIR = Path(__file__).resolve().parent / "web"
RUN_HISTORY_PATH = Path(__file__).resolve().parent / "web_run_history.jsonl"

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

API_KEY = None
RUNS = {}


class Run:
    def __init__(self, run_id: str, requirement: str):
        self.id = run_id
        self.requirement = requirement
        self.status = "UNDERSTANDING REQUIREMENT"
        self.events = []
        self.result_text = None
        self.pending_approvals = {}
        self._lock = threading.Lock()

    def emit(self, event_type: str, data: dict) -> None:
        with self._lock:
            self.events.append({"type": event_type, "ts": time.time(), **data})

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


def _persist_run_history(run: Run, usage_start_index: int = None) -> None:
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
    execution_tools.set_approval_prompt(_web_approval_prompt_factory(run))
    usage_start_index = len(metrics.get_model_usage_events())
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


async def get_run(request: Request):
    run = RUNS.get(request.path_params["run_id"])
    if run is None:
        return JSONResponse({"error": "no such run"}, status_code=404)
    return JSONResponse({
        "id": run.id, "status": run.status,
        "events": run.events, "result": run.result_text,
    })


async def stream_events(request: Request):
    run = RUNS.get(request.path_params["run_id"])
    if run is None:
        return JSONResponse({"error": "no such run"}, status_code=404)

    async def event_generator():
        sent = 0
        while True:
            if await request.is_disconnected():
                break
            new_events, sent = run.events_from(sent)
            for evt in new_events:
                yield {"event": evt["type"], "data": json.dumps(evt)}
            if run.status in ("COMPLETED", "FAILED") and not new_events:
                break
            await asyncio.sleep(0.3)

    return EventSourceResponse(event_generator())


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


async def sessions_page(request: Request):
    return FileResponse(str(WEB_DIR / "sessions.html"))


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
    Route("/api/runs/{run_id}", get_run, methods=["GET"]),
    Route("/api/runs/{run_id}/events", stream_events, methods=["GET"]),
    Route("/api/runs/{run_id}/decide", decide, methods=["POST"]),
    Route("/dashboard", dashboard_page, methods=["GET"]),
    Route("/sessions", sessions_page, methods=["GET"]),
    Mount("/", app=StaticFiles(directory=str(WEB_DIR), html=True), name="static"),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    API_KEY = get_api_key()  # fails fast here, not mid-request, if missing
    print("Agentic Software Delivery Control Plane: http://127.0.0.1:8420", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=8420)
