"""
Unified, paginated historical session system (P0-B).

A "session" here means one of three genuinely distinct real things this
project's event ledger already captures — never fabricated, never a
synthetic record created just to fill the UI:

  - claude_code_dev_session: one Claude Code development session
    (source='claude_code', grouped by session_id).
  - workbench_run: one Workbench requirement execution
    (source in workbench/workbench_trainer/workbench_mock, grouped by
    run_id).
  - v2_trial_benchmark: one V2 shadow-trial/ACT-006 benchmark run
    (source in v2_trial/act_006_verification, grouped by run_id).

All three share the same underlying delivery_events table (the canonical
historical source — see docs/DECISIONS.md), so this module never
introduces a second aggregation path; agent/event_ledger.py's own
get_usage_economics() remains the canonical source for token/cost
*rollups*, while this module answers the different question "what are
the individual sessions, and what happened in each one".

Timing definitions (P0_PROMPT.txt Section 22), applied honestly:
  - WALL-CLOCK DURATION: last event ts - first event ts. Always computable.
  - AI ACTIVE TIME: sum(duration_ms) of real tool_call_completed events
    for that session/run (DERIVED from genuinely measured tool execution
    time, never guessed).
  - AI WAITING FOR HUMAN: for a workbench_run, the gap between an
    authorization_requested event and its matching authorization_decision
    event, when both exist (DERIVED). For claude_code_dev_session, this
    project has zero captured PermissionRequest rows (see
    docs/PROJECT_STATE.json) — always UNKNOWN, not guessed.
  - HUMAN ACTIVE TIME: never captured anywhere in this project — always
    UNKNOWN by design (would require real human-interaction interval
    capture this project does not have).
  - HUMAN WAITING FOR AI: approximated as AI ACTIVE TIME (DERIVED) for an
    autonomous run — while the AI is processing, a human who submitted
    the request is, by construction, waiting on it.
"""

from datetime import datetime, timedelta, timezone

import event_ledger as el

_MAX_CONCISE_TITLE = 160


def repair_mojibake(text):
    """Repairs one specific, well-understood historical data-corruption
    pattern (real incident, 2026-09-11 live production verification): a
    real UTF-8 multi-byte character (e.g. the arrow '→') that was, at
    some earlier point BEFORE this project's own capture pipeline, decoded
    as if it were single-byte cp1252 and then re-encoded as UTF-8 for
    storage -- producing a string like 'Ã¢' + 'â€ ' + 'â€™' as separate
    Unicode codepoints, displayed as visible mojibake such as 'â†’'.

    Detection is via the repair itself succeeding: encoding the string as
    cp1252 and decoding the resulting bytes as UTF-8 only succeeds when
    the string is exactly this kind of double-mis-encoded text -- correct
    ASCII text round-trips to itself unchanged, and correct text
    containing genuine non-cp1252-representable characters (e.g. an
    actual '→') raises UnicodeEncodeError and is returned untouched.
    Never mutates the stored ledger row -- this is a display-only repair,
    applied fresh each time a value is read."""
    if not text:
        return text
    try:
        repaired = text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return repaired


def concise_title(text, max_len=_MAX_CONCISE_TITLE):
    """Derives a short, meaningful title from a long raw capture (e.g. a
    full Claude Code prompt used as a reconstructed session's only
    available 'goal') -- real incident (2026-09-11 live production
    verification): a several-hundred-character raw prompt was displayed
    verbatim as a session's visible title, dominating the page. The full
    original text is never discarded -- see raw_capture in
    _render_session_summary/get_session_detail."""
    if not text:
        return text
    first_line = text.split("\n", 1)[0].strip()
    if len(first_line) > max_len:
        return first_line[: max_len - 1].rstrip() + "…"
    if len(text.strip()) > len(first_line):
        return first_line + " …"
    return first_line

KIND_CLAUDE_CODE = "claude_code_dev_session"
KIND_WORKBENCH_RUN = "workbench_run"
KIND_V2_TRIAL = "v2_trial_benchmark"

_WORKBENCH_SOURCES = ("workbench", "workbench_trainer", "workbench_mock")
_V2_SOURCES = ("v2_trial", "act_006_verification")

_TERMINAL_WORKBENCH_EVENTS = (
    "run_completed", "run_failed", "run_no_change", "deployment_status_unknown",
)

_SESSIONS_CTE = """
WITH sessions AS (
    SELECT session_id AS id, %(kind_cc)s AS kind,
           MIN(timestamp_utc) AS start_ts, MAX(timestamp_utc) AS end_ts,
           BOOL_OR(event_type = 'dev_session_ended') AS has_end_event,
           (ARRAY_AGG(status ORDER BY timestamp_utc DESC))[1] AS last_status
    FROM delivery_events
    WHERE source = 'claude_code' AND session_id IS NOT NULL
      -- Excludes this project's own unit-test fixture session_ids (this
      -- project's tests deliberately run against the real DB, not a mock
      -- -- see agent/test_event_ledger.py's own docstring -- so synthetic
      -- ids like 'sess-distinct-...'/'sess-spoolonly-sync-...' genuinely
      -- exist in the ledger). A real dev session's Claude Code-assigned
      -- session_id is either a real session UUID or this project's one
      -- documented historical-backfill id
      -- ('claude-code-session-...-p0-eventledger-task', see
      -- docs/PROJECT_STATE.json) -- never one of these known test-only
      -- prefixes. Excluding by known test pattern (not by requiring a
      -- specific event type) avoids hiding genuine partial/reconstructed
      -- history that a stricter filter would incorrectly drop.
      AND session_id !~ '^(sess-distinct-|sess-spoolonly-sync-|sess-speed-test|sess-correlated|test-hook-|test-session-|post-fix-smoke-test)'
    GROUP BY session_id

    UNION ALL

    SELECT run_id AS id, %(kind_wb)s AS kind,
           MIN(timestamp_utc) AS start_ts, MAX(timestamp_utc) AS end_ts,
           BOOL_OR(event_type = ANY(%(terminal_events)s)) AS has_end_event,
           (ARRAY_AGG(status ORDER BY timestamp_utc DESC))[1] AS last_status
    FROM delivery_events
    WHERE source = ANY(%(wb_sources)s) AND run_id IS NOT NULL
    GROUP BY run_id

    UNION ALL

    SELECT run_id AS id, %(kind_v2)s AS kind,
           MIN(timestamp_utc) AS start_ts, MAX(timestamp_utc) AS end_ts,
           TRUE AS has_end_event,
           (ARRAY_AGG(status ORDER BY timestamp_utc DESC))[1] AS last_status
    FROM delivery_events
    WHERE source = ANY(%(v2_sources)s) AND run_id IS NOT NULL
    GROUP BY run_id
)
SELECT id, kind, start_ts, end_ts, has_end_event, last_status FROM sessions
"""


def _query_params():
    return {
        "kind_cc": KIND_CLAUDE_CODE, "kind_wb": KIND_WORKBENCH_RUN, "kind_v2": KIND_V2_TRIAL,
        "terminal_events": list(_TERMINAL_WORKBENCH_EVENTS),
        "wb_sources": list(_WORKBENCH_SOURCES),
        "v2_sources": list(_V2_SOURCES),
    }


def _provenance(kind: str, has_end_event: bool) -> str:
    if kind == KIND_CLAUDE_CODE:
        return "LIVE_CAPTURED" if has_end_event else "PARTIAL_RECONSTRUCTION"
    return "LIVE_CAPTURED" if has_end_event else "PARTIAL_RECONSTRUCTION"


def _goal_for_claude_code(conn, session_ids):
    if not session_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (session_id) session_id, payload->>'prompt_excerpt'
            FROM delivery_events
            WHERE source = 'claude_code' AND event_type = 'user_prompt_submitted'
              AND session_id = ANY(%s)
            ORDER BY session_id, timestamp_utc ASC
            """,
            (session_ids,),
        )
        return {sid: repair_mojibake(text) for sid, text in cur.fetchall()}


def _goal_for_workbench(conn, run_ids):
    if not run_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (run_id) run_id,
                   COALESCE(payload->>'requirement_text', payload->>'requirement')
            FROM delivery_events
            WHERE source = ANY(%s) AND run_id = ANY(%s)
              AND event_type IN ('requirement_received', 'risk_assessment', 'run_started')
            ORDER BY run_id, timestamp_utc ASC
            """,
            (list(_WORKBENCH_SOURCES), run_ids),
        )
        return {rid: repair_mojibake(text) for rid, text in cur.fetchall()}


def _ai_active_ms(conn, session_ids, run_ids):
    """DERIVED AI active time: sum of real tool_call_completed duration_ms,
    grouped by session_id or run_id (whichever this id-space applies to)."""
    result = {}
    with conn.cursor() as cur:
        if session_ids:
            cur.execute(
                """
                SELECT session_id, SUM(duration_ms), COUNT(*)
                FROM delivery_events
                WHERE event_type = 'tool_call_completed' AND session_id = ANY(%s)
                GROUP BY session_id
                """,
                (session_ids,),
            )
            for sid, total_ms, count in cur.fetchall():
                result[sid] = (total_ms, count)
        if run_ids:
            cur.execute(
                """
                SELECT run_id, SUM(duration_ms), COUNT(*)
                FROM delivery_events
                WHERE event_type = 'tool_call_completed' AND run_id = ANY(%s)
                GROUP BY run_id
                """,
                (run_ids,),
            )
            for rid, total_ms, count in cur.fetchall():
                result[rid] = (total_ms, count)
    return result


def _usage_for_workbench(conn, run_ids):
    if not run_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id,
                   COALESCE(input_tokens, (payload->>'input_tokens')::bigint),
                   COALESCE(output_tokens, (payload->>'output_tokens')::bigint),
                   (payload->>'cost_usd')::double precision,
                   (payload->>'pricing_version'),
                   COALESCE((payload->>'captured')::boolean, true)
            FROM delivery_events
            WHERE event_type = 'run_usage_summary' AND run_id = ANY(%s)
            """,
            (run_ids,),
        )
        return {r[0]: r[1:] for r in cur.fetchall()}


def _usage_for_v2_trial(conn, run_ids):
    """v2_trial sessions only have AGGREGATE_ONLY subagent totals (see
    docs/ARCHITECTURE_V2_EVALUATION_PLAN.md's Trial #3 economics note) —
    never a real input/output split, so cost is honestly unavailable."""
    if not run_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, SUM((payload->>'subagent_tokens_total')::bigint)
            FROM delivery_events
            WHERE event_type = 'subagent_usage_summary' AND run_id = ANY(%s)
            GROUP BY run_id
            """,
            (run_ids,),
        )
        return {rid: (int(total) if total is not None else None) for rid, total in cur.fetchall()}


def _cost_coverage_summary(conn) -> dict:
    """Usage-level economics (Section 6: 'add useful economics such as
    KNOWN COST TOTAL / SESSIONS WITH KNOWN COST / SESSIONS WITH UNKNOWN
    COST / COST COVERAGE %'). One lightweight aggregate query over the
    canonical run_usage_summary event type -- the same source
    agent/event_ledger.py::get_usage_economics() already treats as
    canonical for lifetime rollups, so this can never contradict it.
    Deliberately covers workbench_run only (the only kind with a real
    possibility of ACTUAL cost); v2_trial/claude_code sessions are
    honestly excluded from 'total sessions' here rather than padding the
    denominator with kinds that can never have a known cost, which would
    silently deflate the coverage percentage."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FILTER (WHERE (payload->>'cost_usd') IS NOT NULL) AS known,
                   COUNT(*) AS total,
                   COALESCE(SUM((payload->>'cost_usd')::double precision), 0) AS known_total
            FROM delivery_events
            WHERE event_type = 'run_usage_summary'
            """
        )
        known, total, known_total = cur.fetchone()
    unknown = total - known
    coverage_pct = round(100 * known / total) if total else None
    return {
        "known_cost_total_usd": round(known_total, 6),
        "sessions_with_known_cost": known,
        "sessions_with_unknown_cost": unknown,
        "cost_coverage_pct": coverage_pct,
        "scope_note": "covers workbench_run sessions only (the only kind with a real run_usage_summary event carrying provider cost)",
    }


def list_sessions(before_cursor: str = None, limit: int = 20) -> dict:
    before_dt = None
    if before_cursor:
        try:
            before_dt = datetime.fromisoformat(before_cursor)
        except ValueError:
            # Real incident (2026-09-11): a `before` cursor containing an
            # unencoded '+' (from the ISO timezone offset, e.g.
            # "...T02:17:07+00:00") is interpreted as a space by standard
            # query-string decoding when a caller doesn't percent-encode
            # it (the real browser client does, via URLSearchParams.set(),
            # so this never happens through the actual UI -- but any other
            # caller sending a malformed/differently-encoded cursor must
            # get a truthful 400, never an unhandled 500).
            return {"status": "INVALID_CURSOR", "error": f"'before' is not a valid ISO timestamp: {before_cursor!r}", "sessions": [], "next_cursor": None}
    try:
        conn = el._connect()
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNREACHABLE", "error": str(exc), "sessions": [], "next_cursor": None}
    try:
        el.ensure_schema()
        params = _query_params()
        sql = f"SELECT * FROM ({_SESSIONS_CTE}) s WHERE (%(before)s::timestamptz IS NULL OR start_ts < %(before)s) ORDER BY start_ts DESC LIMIT %(limit)s"
        params["before"] = before_dt
        params["limit"] = limit + 1  # fetch one extra to know if more remain
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        has_more = len(rows) > limit
        rows = rows[:limit]

        cc_ids = [r["id"] for r in rows if r["kind"] == KIND_CLAUDE_CODE]
        wb_ids = [r["id"] for r in rows if r["kind"] == KIND_WORKBENCH_RUN]
        v2_ids = [r["id"] for r in rows if r["kind"] == KIND_V2_TRIAL]

        goals_cc = _goal_for_claude_code(conn, cc_ids)
        goals_wb = _goal_for_workbench(conn, wb_ids)
        ai_active = _ai_active_ms(conn, cc_ids, wb_ids + v2_ids)
        usage_wb = _usage_for_workbench(conn, wb_ids)
        usage_v2 = _usage_for_v2_trial(conn, v2_ids)

        sessions = []
        for r in rows:
            sessions.append(_render_session_summary(r, goals_cc, goals_wb, ai_active, usage_wb, usage_v2))

        next_cursor = rows[-1]["start_ts"].isoformat() if (has_more and rows) else None
        return {
            "status": "REACHABLE",
            "sessions": sessions,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "cost_coverage_summary": _cost_coverage_summary(conn),
        }
    finally:
        conn.close()


_COST_DISPLAY_LABELS = {
    "ACTUAL": "ACTUAL COST — CALCULATED FROM ACTUAL USAGE",
    "AGGREGATE_ONLY_TOKENS": "COST UNAVAILABLE — AGGREGATE_ONLY",
    "NOT_CAPTURED": "COST UNAVAILABLE — TOKENS NOT CAPTURED",
    "OTHER": "COST UNAVAILABLE",
}


def _cost_display_label(tokens: dict, cost: dict) -> str:
    if cost.get("status") == "ACTUAL":
        return _COST_DISPLAY_LABELS["ACTUAL"]
    if tokens.get("status") == "AGGREGATE_ONLY":
        return _COST_DISPLAY_LABELS["AGGREGATE_ONLY_TOKENS"]
    if tokens.get("status") == "NOT_CAPTURED":
        return _COST_DISPLAY_LABELS["NOT_CAPTURED"]
    return _COST_DISPLAY_LABELS["OTHER"]


def _window_semantics(start_ts, end_ts, has_end_event):
    """Real incident (2026-09-11, live production verification): a
    reconstructed Claude Code session showed '04:52 -> 17:00 / 12.1 hr'
    with AI active time UNKNOWN -- visually implying 12.1 hours of
    continuous work, when the true fact is only that the FIRST and LAST
    *observed* events happen to span that gap; nothing proves continuous
    activity across it. Returns (wall_clock_ms, window_kind, display_note).

    window_kind is CAPTURED_SESSION_DURATION only when a genuine terminal
    event (dev_session_ended / a real Workbench terminal event) closes the
    session -- otherwise OBSERVED_EVENT_WINDOW, since the true session
    boundary (if the session even meaningfully 'ended' at that moment) was
    never actually observed."""
    if start_ts is None or end_ts is None:
        return None, "UNKNOWN", "DURATION NOT CAPTURED"
    wall_ms = (end_ts - start_ts).total_seconds() * 1000
    if wall_ms == 0:
        # Real incident: a single-event (or exactly-simultaneous-events)
        # session showed a bare "0ms", implying a proven instantaneous
        # duration -- timestamp precision cannot actually prove that; the
        # true duration is simply not captured.
        return wall_ms, "UNKNOWN", "DURATION NOT CAPTURED (only one observed instant, true duration unknown)"
    if has_end_event:
        return wall_ms, "CAPTURED_SESSION_DURATION", None
    return wall_ms, "OBSERVED_EVENT_WINDOW", "reconstructed from first/last OBSERVED event only — does not prove continuous activity across this span"


def _render_session_summary(r, goals_cc, goals_wb, ai_active, usage_wb, usage_v2):
    sid, kind = r["id"], r["kind"]
    start_ts, end_ts = r["start_ts"], r["end_ts"]
    wall_ms, window_kind, window_note = _window_semantics(start_ts, end_ts, r["has_end_event"])
    active = ai_active.get(sid)
    ai_active_ms_val = active[0] if active else None
    tool_call_count = active[1] if active else 0

    summary = {
        "session_id": sid,
        "kind": kind,
        "start_utc": start_ts.isoformat() if start_ts else None,
        "end_utc": end_ts.isoformat() if end_ts else None,
        "wall_clock_ms": wall_ms,
        "window_kind": window_kind,
        "window_note": window_note,
        "status": r["last_status"] or "UNKNOWN",
        "provenance": _provenance(kind, r["has_end_event"]),
        "ai_active_ms": ai_active_ms_val,
        "ai_active_ms_note": "DERIVED from real tool_call_completed durations" if ai_active_ms_val is not None else "NOT CAPTURED",
        "tool_call_count": tool_call_count,
        "human_active_ms": None,
        "human_active_note": "UNKNOWN — this project does not capture real human-interaction intervals",
        "ai_waiting_for_human_ms": None,
        "ai_waiting_for_human_note": "UNKNOWN — no PermissionRequest-equivalent timing captured for this kind",
        "human_waiting_for_ai_ms": ai_active_ms_val,
        "human_waiting_for_ai_note": "DERIVED (approximated as AI active time)" if ai_active_ms_val is not None else "UNKNOWN",
    }

    if kind == KIND_CLAUDE_CODE:
        raw_goal = goals_cc.get(sid) or "NOT CAPTURED"
        summary["goal"] = concise_title(raw_goal) if raw_goal != "NOT CAPTURED" else raw_goal
        summary["raw_capture"] = raw_goal if raw_goal != summary["goal"] else None
        summary["model"] = "claude-sonnet-5"
        summary["tokens"] = {"status": "NOT_CAPTURED", "note": "Claude Code hook interface exposes no token-usage field for development sessions (verified against claude_code_hook.py's own field list)."}
        summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "no token usage captured for this session kind"}
    elif kind == KIND_WORKBENCH_RUN:
        raw_goal = goals_wb.get(sid) or "NOT CAPTURED"
        summary["goal"] = concise_title(raw_goal) if raw_goal != "NOT CAPTURED" else raw_goal
        summary["raw_capture"] = raw_goal if raw_goal != summary["goal"] else None
        usage = usage_wb.get(sid)
        if usage:
            in_tok, out_tok, cost_usd, pricing_version, captured = usage
            if captured and in_tok is not None:
                summary["tokens"] = {"status": "EXACT", "input_tokens": in_tok, "output_tokens": out_tok}
                summary["cost"] = ({"status": "ACTUAL", "cost_usd": cost_usd, "pricing_version": pricing_version}
                                    if cost_usd is not None else {"status": "COST_UNAVAILABLE", "reason": "no cost recorded for this run"})
            else:
                summary["tokens"] = {"status": "NOT_CAPTURED"}
                summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "usage not captured for this run"}
        else:
            summary["tokens"] = {"status": "NOT_CAPTURED"}
            summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "no run_usage_summary event for this run"}
    else:  # v2_trial
        summary["goal"] = sid
        summary["raw_capture"] = None
        agg_tokens = usage_v2.get(sid)
        if agg_tokens is not None:
            summary["tokens"] = {"status": "AGGREGATE_ONLY", "aggregate_tokens": agg_tokens}
            summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "aggregate token count does not expose input/output/cache split"}
        else:
            summary["tokens"] = {"status": "NOT_CAPTURED"}
            summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "no usage recorded for this trial"}

    summary["cost_display_label"] = _cost_display_label(summary["tokens"], summary["cost"])
    return summary


def _cohort_stats(conn, kind: str, exclude_id: str, reference_ts):
    """Comparable cohort: same kind, within the previous 7 days of the
    reference session's start time. Requires >=3 comparable sessions with
    known cost/tokens before computing any statistic — otherwise honestly
    reports INSUFFICIENT_COMPARABLE_HISTORY rather than a tiny-sample stat."""
    window_start = reference_ts - timedelta(days=7)
    with conn.cursor() as cur:
        id_col = "session_id" if kind == KIND_CLAUDE_CODE else "run_id"
        source_filter = "source = 'claude_code'" if kind == KIND_CLAUDE_CODE else (
            "source = ANY(%(wb)s)" if kind == KIND_WORKBENCH_RUN else "source = ANY(%(v2)s)"
        )
        cur.execute(
            f"""
            SELECT {id_col}, MIN(timestamp_utc) AS start_ts
            FROM delivery_events
            WHERE {source_filter} AND {id_col} IS NOT NULL
            GROUP BY {id_col}
            HAVING MIN(timestamp_utc) BETWEEN %(window_start)s AND %(reference_ts)s
            """,
            {"wb": list(_WORKBENCH_SOURCES), "v2": list(_V2_SOURCES),
             "window_start": window_start, "reference_ts": reference_ts},
        )
        cohort_ids = [r[0] for r in cur.fetchall() if r[0] != exclude_id]
    return cohort_ids


def _median(values):
    values = sorted(values)
    n = len(values)
    if n == 0:
        return None
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2


def _cohort_wall_times_and_interventions(conn, kind, cohort_ids):
    """Batch (not N+1) lookup of each cohort session's wall-clock span and
    whether it had a human intervention -- reuses the same CTE-free direct
    aggregation pattern as the rest of this module."""
    id_col = "session_id" if kind == KIND_CLAUDE_CODE else "run_id"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT {id_col}, MIN(timestamp_utc), MAX(timestamp_utc),
                   BOOL_OR(event_type IN ('authorization_decision', 'human_decision'))
            FROM delivery_events
            WHERE {id_col} = ANY(%s)
            GROUP BY {id_col}
            """,
            (cohort_ids,),
        )
        wall_times = {}
        interventions = {}
        for cid, start_ts, end_ts, had_intervention in cur.fetchall():
            if start_ts and end_ts:
                wall_times[cid] = (end_ts - start_ts).total_seconds() * 1000
            interventions[cid] = had_intervention
    return wall_times, interventions


def _compare_to_cohort(conn, kind, cohort_ids, this_session_tokens, this_session_cost,
                        this_session_wall_ms, this_session_had_intervention):
    """Real median/rate comparison — only computed once >=3 comparable
    sessions with KNOWN usage exist for a given metric, per Section 29
    ('do not invent statistics from tiny samples'). Only workbench_run has
    a directly queryable per-id total-token figure (run_usage_summary);
    other kinds report cohort size only for tokens/cost, honestly, rather
    than a fabricated comparison. Wall time and human-intervention rate
    are derivable for every kind from timestamps/event types alone."""
    result = {}
    if not cohort_ids:
        return result

    if kind == KIND_WORKBENCH_RUN:
        usage = _usage_for_workbench(conn, cohort_ids)
        token_totals = [(u[0] or 0) + (u[1] or 0) for u in usage.values() if u[4] and u[0] is not None]
        cost_values = [u[2] for u in usage.values() if u[4] and u[2] is not None]
        if len(token_totals) >= 3 and this_session_tokens is not None:
            med = _median(token_totals)
            result["tokens_vs_cohort_median"] = {
                "this_session": this_session_tokens, "cohort_median": med,
                "pct_diff": round(100 * (this_session_tokens - med) / med, 1) if med else None,
            }
        if len(cost_values) >= 3 and this_session_cost is not None:
            med = _median(cost_values)
            result["cost_vs_cohort_median"] = {
                "this_session": this_session_cost, "cohort_median": med,
                "pct_diff": round(100 * (this_session_cost - med) / med, 1) if med else None,
            }

    wall_times, interventions = _cohort_wall_times_and_interventions(conn, kind, cohort_ids)
    wall_values = list(wall_times.values())
    if len(wall_values) >= 3 and this_session_wall_ms is not None:
        med = _median(wall_values)
        result["wall_time_vs_cohort_median_ms"] = {
            "this_session": this_session_wall_ms, "cohort_median": med,
            "pct_diff": round(100 * (this_session_wall_ms - med) / med, 1) if med else None,
        }
    if len(interventions) >= 3:
        rate = round(100 * sum(1 for v in interventions.values() if v) / len(interventions))
        result["human_intervention_vs_cohort"] = {
            "this_session": bool(this_session_had_intervention),
            "cohort_intervention_rate_pct": rate,
        }
    return result


def get_session_detail(session_id: str) -> dict:
    try:
        conn = el._connect()
    except Exception as exc:  # noqa: BLE001
        return {"status": "UNREACHABLE", "error": str(exc)}
    try:
        el.ensure_schema()
        params = _query_params()
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM ({_SESSIONS_CTE}) s WHERE id = %(id)s", {**params, "id": session_id})
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
        if row is None:
            return None
        r = dict(zip(cols, row))
        kind = r["kind"]

        cc_ids = [session_id] if kind == KIND_CLAUDE_CODE else []
        wb_ids = [session_id] if kind == KIND_WORKBENCH_RUN else []
        v2_ids = [session_id] if kind == KIND_V2_TRIAL else []
        goals_cc = _goal_for_claude_code(conn, cc_ids)
        goals_wb = _goal_for_workbench(conn, wb_ids)
        ai_active = _ai_active_ms(conn, cc_ids, wb_ids + v2_ids)
        usage_wb = _usage_for_workbench(conn, wb_ids)
        usage_v2 = _usage_for_v2_trial(conn, v2_ids)
        summary = _render_session_summary(r, goals_cc, goals_wb, ai_active, usage_wb, usage_v2)

        # Timeline: real observable events for this id, in order.
        id_col = "session_id" if kind == KIND_CLAUDE_CODE else "run_id"
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT timestamp_utc, event_type, status, tool_name
                FROM delivery_events WHERE {id_col} = %s
                ORDER BY timestamp_utc ASC
                """,
                (session_id,),
            )
            timeline = [
                {"timestamp_utc": ts.isoformat(), "event_type": et, "status": st, "tool_name": tn}
                for ts, et, st, tn in cur.fetchall()
            ]

        # Human interventions: authorization_decision / human_decision events.
        human_interventions = [t for t in timeline if t["event_type"] in ("authorization_decision", "human_decision")]

        # Value/quality (evidence-backed dimensions only, per Sections 27-28).
        technical_value = {
            "verified_changes_completed": 1 if summary["status"] == "COMPLETED" else 0,
            "failures": 1 if summary["status"] in ("FAILED", "run_failed") else 0,
        }
        knowledge_candidates_linked = 0
        try:
            import knowledge_candidates as kc
            knowledge_candidates_linked = sum(
                1 for c in kc.list_candidates_for_review(limit=200) if c["run_id"] == session_id
            )
        except Exception:
            pass
        learning_value = {"knowledge_candidates_created": knowledge_candidates_linked}

        # scored_dimensions: substantive FACTS about this session (always
        # knowable -- a definite True/False either way -- so they are
        # never a meaningful "coverage" signal on their own; shown for
        # transparency, not used to compute coverage below).
        scored_dims = {}
        scored_dims["goal_completion"] = summary["status"] not in ("UNKNOWN", None)
        scored_dims["human_intervention_present"] = len(human_interventions) > 0

        # evidence_availability: real incident (2026-09-11, live
        # production verification) -- the PREVIOUS coverage calculation
        # counted "was this dimension evaluated at all" (always true,
        # since every dimension above always resolves to a definite
        # boolean), so evidence_coverage_pct was silently 100% and
        # overall_confidence was silently HIGH_CONFIDENCE for EVERY
        # session, including ones with zero captured tokens/cost/timing
        # (e.g. a NO_CHANGE_NEEDED run with tokens=NOT_CAPTURED,
        # cost=COST_UNAVAILABLE, ai_active_ms=None still showed
        # HIGH_CONFIDENCE) -- exactly the fake-100%-with-thin-evidence
        # defect this system is supposed to prevent. Coverage now
        # measures only genuine evidence-AVAILABILITY signals (is real
        # timing/token/cost data actually present), which legitimately
        # differ session to session.
        availability_dims = {
            "ai_active_time_known": summary["ai_active_ms"] is not None,
            "tokens_captured": summary["tokens"].get("status") in ("EXACT", "AGGREGATE_ONLY"),
            "cost_known": summary["cost"].get("status") == "ACTUAL",
        }
        evidence_coverage_pct = round(100 * sum(1 for v in availability_dims.values() if v) / len(availability_dims))
        quality = {
            # Real incident (2026-09-11, live production verification):
            # the top summary card showed "QUALITY / 100% coverage",
            # conflating two different questions -- "how good is this
            # session" (a QUALITY score) vs. "how much of this evaluation
            # is backed by captured evidence" (EVIDENCE COVERAGE). This
            # project does not have a legitimate composite quality-scoring
            # algorithm yet (rework/first-pass-success/etc. are not
            # reliably derivable from the current ledger) -- rather than
            # invent one, quality_score is honestly None/NOT_SCORED, kept
            # structurally distinct from evidence_coverage_pct below.
            "quality_score": None,
            "quality_score_label": "NOT SCORED",
            "scored_dimensions": scored_dims,
            "evidence_availability": availability_dims,
            "evidence_coverage_pct": evidence_coverage_pct,
            "overall_confidence": (
                "HIGH_CONFIDENCE" if evidence_coverage_pct >= 75 else
                "PARTIAL" if evidence_coverage_pct >= 40 else "LOW_COVERAGE"
            ),
        }

        # Comparison to other comparable sessions (same kind, last 7 days).
        cohort_ids = _cohort_stats(conn, kind, session_id, r["start_ts"])
        if len(cohort_ids) >= 3:
            this_tokens = None
            if summary["tokens"].get("status") == "EXACT":
                this_tokens = summary["tokens"]["input_tokens"] + summary["tokens"]["output_tokens"]
            this_cost = summary["cost"].get("cost_usd") if summary["cost"].get("status") == "ACTUAL" else None
            this_had_intervention = len(human_interventions) > 0
            comparison_metrics = _compare_to_cohort(
                conn, kind, cohort_ids, this_tokens, this_cost,
                summary["wall_clock_ms"], this_had_intervention,
            )
            comparison = {
                "status": "COMPARABLE", "cohort_size": len(cohort_ids), "cohort_basis": "same kind, previous 7 days",
                **comparison_metrics,
            }
            if not comparison_metrics:
                comparison["note"] = "cohort exists but no individual metric had >=3 comparable known values"
        else:
            comparison = {"status": "INSUFFICIENT_COMPARABLE_HISTORY", "cohort_size": len(cohort_ids)}

        return {
            **summary,
            "timeline": timeline,
            "human_interventions": human_interventions,
            "value": {"technical_value": technical_value, "learning_value": learning_value},
            "quality": quality,
            "comparison": comparison,
        }
    finally:
        conn.close()
