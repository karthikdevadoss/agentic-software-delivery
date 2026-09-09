"""
Dashboard MVP data layer — evidence/intelligence surface, not the control
surface (that's web_server.py's /api/runs*). Reads only REAL, already-
captured state:

  - docs/PROJECT_STATE.json      durable, human-reviewed verified facts
  - agent/.rag_index/index.json  the actual persisted RAG index
  - agent/web_run_history.jsonl  small local log of Control UI runs
                                  (this process's own record, gitignored)
  - agent/metrics.py             in-memory counters for the current process

No network calls, no Anthropic API calls, no fabricated numbers. Anything
not actually captured is reported as such (NOT CAPTURED YET / NOT
IMPLEMENTED / NOT VERIFIED) rather than invented.
"""

import json
from pathlib import Path

import metrics

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_STATE_PATH = REPO_ROOT / "docs" / "PROJECT_STATE.json"
RAG_INDEX_PATH = REPO_ROOT / "agent" / ".rag_index" / "index.json"
RUN_HISTORY_PATH = REPO_ROOT / "agent" / "web_run_history.jsonl"

# Hand-verified by a live `python -m unittest ...` run this session, at the
# commit noted below. Re-run and update this constant (do not guess) if
# agent/*.py or agent/test_*.py change after that commit.
TEST_EVIDENCE = {
    "total": 60,
    "passed": 59,
    "skipped": 1,
    "failed": 0,
    "skip_reason": "Windows lacks the privilege to create symlinks in this test environment (platform limitation, not a bug)",
    "command": "python -m unittest test_agent_loop test_rag_index test_mcp_server test_write_tools test_build_tools test_execution_tools",
    "as_of_commit": "113b016",
}

# Manually curated, but every field must trace to a verification_state /
# completed_capabilities / missing_capabilities entry in PROJECT_STATE.json
# — this is a restructuring of already-recorded truth for display, not new
# claims. Keep in sync when PROJECT_STATE.json's capability lists change.
CAPABILITY_MATRIX = [
    {"area": "LLM / API tool-calling loop", "status": "IMPLEMENTED",
     "evidence": "agent_loop.py generic run_agent_loop(tool_schemas, dispatch_fn); thinking/tool_use round-trip unit-tested",
     "gap": "no automatic model routing / FinOps layer"},
    {"area": "Repository-aware planning", "status": "IMPLEMENTED",
     "evidence": "V3 controlled read-only planning agent; safe list_repository_files/read_file/search_code tools",
     "gap": "-"},
    {"area": "RAG (semantic retrieval)", "status": "IMPLEMENTED",
     "evidence": "local fastembed (BAAI/bge-small-en-v1.5) + numpy cosine similarity; hybrid-verified via read_file/search_code",
     "gap": "no production embedding provider (Voyage AI coded but needs API key); no vector DB at scale"},
    {"area": "Incremental RAG indexing", "status": "IMPLEMENTED",
     "evidence": "content-hash based reuse; 7 unit tests + live add/modify/delete/no-op proof",
     "gap": "-"},
    {"area": "MCP (Model Context Protocol)", "status": "PARTIALLY IMPLEMENTED",
     "evidence": "official modelcontextprotocol/python-sdk; stdio + in-process Client discovery/invocation/security unit-tested",
     "gap": "Streamable HTTP transport is coded but NOT runtime-verified over real HTTP; only read-only tools exposed via MCP"},
    {"area": "Safe writes (propose/approve/apply)", "status": "IMPLEMENTED",
     "evidence": "write_tools.py: scope-restricted to app/src/{main,test}/java .java files; approval bound to sha256(path+content), not just a boolean",
     "gap": "-"},
    {"area": "Human approval boundary", "status": "IMPLEMENTED",
     "evidence": "approve/reject never exposed as an LLM tool schema or reachable via dispatch (verified by exact set membership); fails closed on EOF; real browser APPROVE click verified end to end",
     "gap": "single approval registry (one run at a time) — fine for this single-operator MVP"},
    {"area": "Controlled build/test verification", "status": "IMPLEMENTED",
     "evidence": "allowlist-only Maven compile/test, no shell, argv-list subprocess; real run: compile ~15.3s, tests ~19.0s, both PASS",
     "gap": "-"},
    {"area": "Browser Control UI", "status": "IMPLEMENTED",
     "evidence": "Starlette+SSE; first genuine human-approved browser run reached VERIFIED SUCCESS; two real UI defects found live and fixed, creator-confirmed",
     "gap": "no automated browser test suite (verified manually)"},
    {"area": "Metrics hooks", "status": "IMPLEMENTED (minimal)",
     "evidence": "agent/metrics.py: structured tool-call/RAG-index/retrieval events",
     "gap": "in-memory only — resets on process restart; no persisted long-term analytics store"},
    {"area": "Dashboard (evidence surface)", "status": "IN PROGRESS",
     "evidence": "this MVP", "gap": "no auth/tenancy yet (not needed at this stage)"},
    {"area": "Compile/test self-correction loop", "status": "NOT IMPLEMENTED",
     "evidence": "-", "gap": "tools exist and are wired in; no automatic retry-on-failure loop yet"},
    {"area": "Multi-agent architecture", "status": "NOT IMPLEMENTED",
     "evidence": "-", "gap": "current baseline is deliberately 1 reasoning agent + deterministic tools, pending a measured need"},
    {"area": "Deployment", "status": "NOT IMPLEMENTED", "evidence": "-", "gap": "no deployment pipeline exists"},
    {"area": "YogaCRM / customer pilot", "status": "NOT STARTED", "evidence": "-", "gap": "future strategic pilot; not begun"},
]

KNOWN_LIMITATIONS = [
    "No compile/test self-correction loop — a failure is reported, not automatically retried.",
    "No automated browser/UI test suite — the two Control UI fixes were verified by code inspection, HTTP-level mock replay, and the creator's own manual visual check, not CI.",
    "No production deployment pipeline.",
    "No multi-agent architecture — one reasoning agent plus deterministic tools, by design, until a measured need justifies more.",
    "No enterprise-scale RAG benchmark — local index is sized for this repo (21 files / 56 chunks); would need a real vector DB at scale.",
    "No real customer pilot yet (YogaCRM is a future strategic target, not started).",
    "Metrics are in-memory (reset on restart) plus a small local run-history log — no persisted long-term analytics store.",
    "MCP Streamable HTTP transport is implemented but not runtime-verified over real HTTP (only stdio / in-process Client tested).",
    "Token usage and API cost are NOT captured — no instrumentation exists; Claude Code's own context display was deliberately not used as a substitute, since it is not a reliable per-run cost source.",
    "The Dashboard's own data layer (agent/dashboard_data.py) has no automated tests yet — it was verified this session via live curl checks against the real endpoints, not a unit test suite.",
]


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _project_state() -> dict:
    return _read_json(PROJECT_STATE_PATH) or {}


def _rag_index_summary() -> dict:
    idx = _read_json(RAG_INDEX_PATH)
    if idx is None:
        return {"status": "NOT CAPTURED YET", "note": "no persisted index found at agent/.rag_index/index.json"}
    return {
        "status": "INDEX PRESENT",
        "embedding_model": idx.get("model_id", "NOT CAPTURED YET"),
        "chunking_version": idx.get("chunking_version", "NOT CAPTURED YET"),
        "files_indexed": len(idx.get("files", {})),
        "chunks_indexed": len(idx.get("chunks", {})),
    }


def _read_run_history(limit: int = 10) -> list:
    if not RUN_HISTORY_PATH.exists():
        return []
    records = []
    for line in RUN_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records[-limit:][::-1]  # most recent first


def _session_metrics() -> dict:
    """Counters for THIS server process only — resets on restart. Labeled
    explicitly so it is never confused with the persisted run-history log."""
    events = metrics.get_tool_call_events()
    if not events:
        return {"status": "NOT CAPTURED YET", "note": "no tool calls recorded in this server process since it started"}
    succeeded = sum(1 for e in events if e["success"])
    failed = len(events) - succeeded
    blocked = sum(1 for e in events if e.get("blocked_unsafe"))
    return {
        "status": "CAPTURED (current process only)",
        "tool_calls_total": len(events),
        "tool_calls_succeeded": succeeded,
        "tool_calls_failed": failed,
        "security_blocked": blocked,
    }


def _milestone_from_state(state: dict) -> dict:
    vs = state.get("verification_state", {})
    run = vs.get("control_ui_real_browser_human_approved_run")
    scroll = vs.get("control_ui_scroll_bug_fixed")
    panel = vs.get("control_ui_build_test_panel_fixed")
    if not run:
        return {"status": "NOT CAPTURED YET"}
    return {
        "status": "DOCUMENTED (durable project state, not live telemetry)",
        "summary": run.get("evidence"),
        "as_of_commit": run.get("as_of_commit"),
        "ui_fixes_creator_confirmed": {
            "scroll_fix": scroll.get("status") if scroll else "NOT CAPTURED YET",
            "build_test_panel_fix": panel.get("status") if panel else "NOT CAPTURED YET",
        },
    }


def _mcp_summary(state: dict) -> dict:
    vs = state.get("verification_state", {})

    def status_of(key):
        entry = vs.get(key)
        return entry.get("status") if entry else "NOT CAPTURED YET"

    return {
        "sdk": "official modelcontextprotocol/python-sdk (MCPServer class)",
        "tool_discovery": status_of("mcp_tool_discovery"),
        "tool_invocation": status_of("mcp_tool_invocation"),
        "security_passthrough": status_of("mcp_security_passthrough"),
        "no_duplicated_security_logic": status_of("mcp_no_duplicated_security_logic"),
        "tools_exposed": ["list_repository_files", "read_file", "search_code", "semantic_repository_search"],
        "write_build_deploy_via_mcp": "NOT IMPLEMENTED (read-only tools only, by design)",
        "stdio_transport": "RUNTIME VERIFIED (in-process Client + stdio)",
        "streamable_http_transport": "IMPLEMENTED / DOCUMENTED — NOT RUNTIME VERIFIED over real HTTP",
    }


def _security_summary(state: dict) -> dict:
    vs = state.get("verification_state", {})

    def status_of(key):
        entry = vs.get(key)
        return entry.get("status") if entry else "NOT CAPTURED YET"

    return {
        "human_approval_outside_llm_tool_surface": status_of("v41_approval_not_model_callable"),
        "model_cannot_self_approve": status_of("v41_approval_not_model_callable"),
        "approval_bound_to_exact_path_and_content": status_of("v4_approval_binding_integrity"),
        "modified_or_substituted_proposal_rejected": status_of("v4_approval_binding_integrity"),
        "unapproved_or_duplicate_apply_blocked": status_of("v4_write_boundary_propose_approve_apply"),
        "fails_closed_without_a_human_present": status_of("v41_fail_closed_without_human"),
        "scope_and_secret_path_protections": status_of("v4_write_boundary_scope_and_secret_rejection"),
        "no_arbitrary_shell": status_of("v4_build_tool_allowlist"),
        "real_browser_human_approval_verified": status_of("control_ui_real_browser_human_approved_run"),
        "disclaimer": "NOT claimed to be \"100% secure\" — this is a scoped, evidenced set of boundaries verified by tests and live runs, not a general security certification.",
    }


def build_dashboard_snapshot() -> dict:
    state = _project_state()

    return {
        "system_snapshot": {
            "system": state.get("project", "Agentic Software Delivery System"),
            "version": state.get("current_version", "NOT CAPTURED YET"),
            "agent_architecture": "1 reasoning agent (Claude, tool-calling loop) + deterministic tools/services",
            "last_verified_code_commit": state.get("last_verified_code_commit", "NOT CAPTURED YET"),
            "current_ticket": state.get("current_ticket", "NOT CAPTURED YET"),
            "current_ticket_implemented": state.get("current_ticket_implemented", False),
            "next_phase": state.get("next_phase", "NOT CAPTURED YET"),
        },
        "last_documented_milestone": _milestone_from_state(state),
        "run_history": _read_run_history(),
        "session_metrics": _session_metrics(),
        "rag": _rag_index_summary(),
        "mcp": _mcp_summary(state),
        "security": _security_summary(state),
        "quality": TEST_EVIDENCE,
        "capability_matrix": CAPABILITY_MATRIX,
        "known_limitations": KNOWN_LIMITATIONS,
    }
