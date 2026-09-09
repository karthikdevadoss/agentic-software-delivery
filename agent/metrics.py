"""
Minimal structured metrics hooks (not a dashboard).

Purpose: let the future AI Engineering Intelligence layer consume clean,
structured events from MCP/RAG without needing tools.py, agent_loop.py,
rag_index.py, or mcp_server.py rewritten later. In-memory only for now —
no file/DB writes, no secrets, no raw file contents, no thinking content.

If/when a real metrics backend exists, only this module's storage should
need to change; record_*()/get_*() call sites elsewhere should not.
"""

_SECURITY_MARKERS = (
    "traversal", "absolute path", "symlink", "blocked director",
    "blocked for safety", "outside the repository",
)

_tool_call_events = []
_rag_index_events = []
_retrieval_events = []
_model_usage_events = []


def is_security_block(error_message: str) -> bool:
    """Best-effort, deterministic classification: was this error a security
    boundary rejection (path traversal, symlink, blocked name/dir/ext), as
    opposed to an ordinary validation error (empty query, not found, etc.)?
    Based on tools.py's own RepoToolError message text, not fabricated."""
    lowered = (error_message or "").lower()
    return any(marker in lowered for marker in _SECURITY_MARKERS)


def record_tool_call(*, tool, input_summary, success, duration_ms,
                      result_size, truncated=False, blocked_unsafe=False):
    _tool_call_events.append({
        "tool": tool,
        "input_summary": input_summary,
        "success": success,
        "duration_ms": duration_ms,
        "result_size": result_size,
        "truncated": truncated,
        "blocked_unsafe": blocked_unsafe,
    })


def record_rag_index(stats: dict):
    _rag_index_events.append(dict(stats))


def record_retrieval(*, query, top_k, candidates_count, duration_ms):
    _retrieval_events.append({
        "query": query,
        "top_k": top_k,
        "candidates_count": candidates_count,
        "duration_ms": duration_ms,
    })


def record_model_usage(*, provider, model, input_tokens, output_tokens,
                        cache_creation_input_tokens=None, cache_read_input_tokens=None):
    """Captured directly from the API response's own `.usage` field
    (Anthropic SDK's Usage type) — never estimated, never scraped from a
    UI counter. cache_* fields are None when the SDK response doesn't
    report them, not silently coerced to 0, so callers can distinguish
    "no cache activity" from "not reported by this response"."""
    _model_usage_events.append({
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
    })


def get_tool_call_events() -> list:
    return list(_tool_call_events)


def get_rag_index_events() -> list:
    return list(_rag_index_events)


def get_retrieval_events() -> list:
    return list(_retrieval_events)


def get_model_usage_events() -> list:
    return list(_model_usage_events)


def reset():
    """Test-only: clear all in-memory events."""
    _tool_call_events.clear()
    _rag_index_events.clear()
    _retrieval_events.clear()
    _model_usage_events.clear()
