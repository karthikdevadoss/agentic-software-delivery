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

import yaml

import event_ledger
import metrics
import showcase_data

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_STATE_PATH = REPO_ROOT / "docs" / "PROJECT_STATE.json"
RAG_INDEX_PATH = REPO_ROOT / "agent" / ".rag_index" / "index.json"
RUN_HISTORY_PATH = REPO_ROOT / "agent" / "web_run_history.jsonl"
LEDGER_PATH = REPO_ROOT / "docs" / "ai" / "AI_ENGINEERING_QUALITY_LEDGER.yaml"

# Hand-verified by a live `python -m unittest ...` / `mvnw test` run at the
# commits noted below (this project's most recent full-suite runs — see
# docs/PROJECT_STATE.json's verification_state for the exact evidence
# entries). Re-run and update these constants (do not guess) the next time
# a full regression pass is performed.
TEST_EVIDENCE = {
    "python": {"total": 531, "passed": 530, "skipped": 1, "failed": 0,
               "skip_reason": "Windows lacks the privilege to create symlinks in this test environment (platform limitation, not a bug)",
               "as_of_commit": "b3d6856",
               "note": "STALE COUNT (Priority-3 truth audit, 2026-09-15): a real full run was re-verified this session (see docs/PROJECT_STATUS.md) but genuinely NEW test files were added afterward (test_triage_execution.py, test_environment_preflight.py) -- this number predates them. Re-verify and update rather than trust this count as current."},
    "java": {"total": 109, "passed": 97, "skipped": 12, "failed": 0,
             "skip_reason": "Testcontainers-backed Postgres tests skip on this dev machine (no local Docker daemon) but run for real in GitHub Actions CI",
             "as_of_commit": "3c2ad64"},
    "node_frontend": {"total": 92, "passed": 92, "skipped": 0, "failed": 0,
                       "as_of_commit": "3c2ad64"},
    "command": "python -m unittest discover  (agent/)   |   mvnw test  (app/)   |   node --test (agent/test_*_frontend.js)",
    "ci": "GitHub Actions (.github/workflows/ci.yml) runs the real Testcontainers-backed Postgres suite on every push — this dev machine has no local Docker daemon, so those tests can only be genuinely exercised in CI.",
}


def _capability_matrix() -> list:
    """Single source of truth: docs/PORTFOLIO_CAPABILITIES.yaml, the same
    registry the job-specific showcase factory reads. Never a second,
    independently-maintained copy — that was the root cause of this
    section going stale for a long time (it previously named "V4 tool-use
    budget" concepts from the earliest sessions while the actual product
    had since shipped Postgres/JWT/Kafka/Resilience4j/RAG/MCP/evals)."""
    registry = showcase_data.load_capability_registry()
    state_labels = {
        "PRODUCTION_ACTIVE": "PRODUCTION ACTIVE",
        "DEMO_AVAILABLE": "DEMO AVAILABLE",
        "NOT_PRODUCTION_PROVISIONED": "IMPLEMENTED — NOT PRODUCTION PROVISIONED",
    }
    rows = []
    for cap in registry.values():
        status = state_labels.get(cap.get("production_state"), cap.get("production_state", "NOT CAPTURED YET"))
        evidence = "; ".join(cap.get("evidence_links") or []) or cap.get("engineering_problem_solved", "-")
        gap = "-" if cap.get("production_state") == "PRODUCTION_ACTIVE" else (cap.get("production_state") or "").replace("_", " ")
        rows.append({"area": cap.get("display_name", cap.get("id")), "status": status, "evidence": evidence, "gap": gap or "-"})
    return rows

KNOWN_LIMITATIONS = [
    "No compile/test self-correction loop for the read/plan-only V3 CLI agent — a failure is reported, not automatically retried (the live Workbench pipeline DOES retry production-content verification within a bounded window; see production-deployment-verification).",
    "No multi-agent architecture — one reasoning agent plus deterministic tools/services, by design, until a measured need justifies more.",
    "No enterprise-scale RAG benchmark — local index is sized for this repo; would need a real vector DB (pgvector/Qdrant) at meaningfully larger scale.",
    "Kafka (transactional outbox) and Redis (cache-aside) are both implemented and integration-tested, but deliberately NOT production-provisioned — no persistent broker/cache instance is running, to avoid paying for infrastructure a portfolio project doesn't yet need under real load.",
    "MCP Streamable HTTP transport is implemented but not runtime-verified over real HTTP (only stdio / in-process Client tested).",
    "Cost-per-verified-change is INSUFFICIENT DATA until enough real COMPLETED runs with known cost exist in the event ledger window being queried.",
    "The Dashboard's own data layer (agent/dashboard_data.py) and the showcase factory (agent/showcase_data.py) have no dedicated automated test files yet — verified via live curl checks against the real endpoints and the existing web_server.py route-registration suite, not a unit test suite of their own.",
    "The custom domain (agentic.karthikdevadoss.com) has DNS configured but TLS certificate provisioning is still not confirmed live (independently re-checked 2026-09-14: a direct TLS handshake to the domain fails certificate validation) — the Railway *.up.railway.app URLs remain the correct links to share.",
]

def _economics_snapshot() -> dict:
    """Real, ledger-backed token/cost economics (event_ledger.get_usage_economics()).

    ROOT-CAUSED REAL INCIDENT (2026-09-11): this used to be a static
    ECONOMICS dict hardcoded to "NOT CAPTURED YET"/"NOT CALCULATED YET" —
    written before agent/pricing_config.py and the real run_usage_summary
    event existed, and never updated afterward. The Creator observed a
    real run showing real captured tokens (e.g. 31,573 input / 2,797
    output / 5 API calls) elsewhere in the product while this exact
    surface still claimed nothing was captured — the capture was real,
    only this display was stale and disconnected from it. Never again:
    this now queries the same canonical event ledger every other real
    usage display reads from."""
    try:
        return event_ledger.get_usage_economics()
    except Exception as exc:  # noqa: BLE001 - Dashboard must never break because the ledger is unreachable
        return {"status": "UNREACHABLE", "error": str(exc)}

# A single manually-observed fact about the live public Customer app,
# captured by directly querying the deployed instance — NOT a durable
# audit event (no persistent event store exists yet). Update this by hand
# when a new observation is made; do not let it silently go stale-looking
# — the "observed_at" field says exactly when this was true.
VERIFIED_ACTIVITY = {
    "environment": "customer_production (public Railway deployment)",
    "action": "POST /customers (create) then GET /customers/{id} (find) against the live app",
    "result": "Customer id=2 created and independently re-verified reachable",
    "observed_at": "2026-09-09 (manual curl verification against the live Railway URL)",
    "evidence_type": "MANUALLY VERIFIED OBSERVATION — not a durably captured audit event. H2 is in-memory, so this record will not survive a redeploy/restart.",
}


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def read_project_state() -> dict:
    """Public: also used by sessions_data.py so both modules read the one
    real durable-state file the same way, instead of duplicating parsing."""
    return _read_json(PROJECT_STATE_PATH) or {}


_project_state = read_project_state  # internal alias, unchanged call sites below


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


def _event_ledger_summary() -> dict:
    """Minimal live proof that the durable event ledger (agent/event_ledger.py,
    Railway Postgres — see docs/RESOURCE_REGISTRY.md) is real and queryable.
    Deliberately NOT a redesign of this page: one small additional key,
    read-only, honest about UNREACHABLE rather than hiding a real outage."""
    try:
        recent = event_ledger.get_recent_events(limit=1)
        count = event_ledger.count_events()
        last = recent[0] if recent else None
        return {
            "evidence_source": "REMOTE EVENT LEDGER (Railway Postgres, agent/event_ledger.py)",
            "status": "REACHABLE",
            "events_captured": count,
            "last_event_timestamp_utc": last["timestamp_utc"].isoformat() if last else None,
            "last_event_type": last["event_type"] if last else None,
        }
    except Exception as exc:  # noqa: BLE001 - dashboard must never break because the ledger is down
        return {
            "evidence_source": "REMOTE EVENT LEDGER (Railway Postgres, agent/event_ledger.py)",
            "status": "UNREACHABLE",
            "error": str(exc),
        }


# Curated, recruiter-first framing (Priority 5's "hiring manager" lens):
# each row names the real engineering PROBLEM first, the technique second
# — never a bare technology badge list. Every capability_id must exist in
# docs/PORTFOLIO_CAPABILITIES.yaml; an id that no longer resolves is
# reported honestly (see the "missing" list below) rather than silently
# dropped, the same discipline showcase_data.py already applies.
ENGINEERING_PROBLEMS_SOLVED_ORDER = [
    "security-jwt-rbac",
    "postgres-jpa-flyway",
    "downstream-resilience",
    "kafka-outbox",
    "redis-cache",
    "agentic-ai-delivery-pipeline",
    "rag-mcp-embeddings",
    "production-deployment-verification",
]


def _engineering_problems_solved() -> dict:
    registry = showcase_data.load_capability_registry()
    rows, missing = [], []
    for cap_id in ENGINEERING_PROBLEMS_SOLVED_ORDER:
        cap = registry.get(cap_id)
        if cap is None:
            missing.append(cap_id)
            continue
        rows.append({
            "problem": cap["engineering_problem_solved"],
            "technique": cap["display_name"],
            "production_state": cap["production_state"],
            "evidence_links": cap.get("evidence_links", []),
        })
    return {"rows": rows, "missing_capability_ids": missing}


# Curated subset of the full AI Engineering Quality Ledger for a
# recruiter-safe first view — the mega-prompt's own instruction is "do NOT
# dump giant raw logs on the first page." The full ledger remains at
# docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml for anyone who wants the raw
# structured record (all fields, all entries).
LEARNING_LEDGER_HIGHLIGHT_IDS = ["AEQ-013", "AEQ-010", "AEQ-011", "AEQ-012", "AEQ-004", "RWY-001"]


def _ai_engineering_learning() -> dict:
    if not LEDGER_PATH.exists():
        return {"status": "NOT CAPTURED YET", "highlights": [], "total_defects": 0}
    try:
        ledger = yaml.safe_load(LEDGER_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return {"status": "UNREADABLE", "error": str(exc), "highlights": [], "total_defects": 0}

    defects = {d["defect_id"]: d for d in ledger.get("defects", [])}
    highlights = []
    for defect_id in LEARNING_LEDGER_HIGHLIGHT_IDS:
        d = defects.get(defect_id)
        if d is None:
            continue
        highlights.append({
            "defect_id": d["defect_id"],
            "title": d["title"],
            "root_cause": d["root_cause"],
            "product_fix": d["product_fix"],
            "harness_improvement": d["new_harness_process_regression"],
            "confidence": d["analysis_confidence"],
            "recurrence_status": d["recurrence_status"],
        })
    return {
        "status": "CAPTURED",
        "total_defects": len(defects),
        "highlights": highlights,
        "full_ledger_path": "docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml",
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
        "engineering_problems_solved": _engineering_problems_solved(),
        "last_documented_milestone": _milestone_from_state(state),
        "event_ledger": _event_ledger_summary(),
        "run_history": _read_run_history(),
        "session_metrics": _session_metrics(),
        "economics": _economics_snapshot(),
        "verified_activity": VERIFIED_ACTIVITY,
        "rag": _rag_index_summary(),
        "mcp": _mcp_summary(state),
        "security": _security_summary(state),
        "quality": TEST_EVIDENCE,
        "capability_matrix": _capability_matrix(),
        "ai_engineering_learning": _ai_engineering_learning(),
        "known_limitations": KNOWN_LIMITATIONS,
    }
