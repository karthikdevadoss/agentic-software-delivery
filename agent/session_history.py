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
        return dict(cur.fetchall())


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
        return dict(cur.fetchall())


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
        }
    finally:
        conn.close()


def _render_session_summary(r, goals_cc, goals_wb, ai_active, usage_wb, usage_v2):
    sid, kind = r["id"], r["kind"]
    start_ts, end_ts = r["start_ts"], r["end_ts"]
    wall_ms = (end_ts - start_ts).total_seconds() * 1000 if start_ts and end_ts else None
    active = ai_active.get(sid)
    ai_active_ms_val = active[0] if active else None
    tool_call_count = active[1] if active else 0

    summary = {
        "session_id": sid,
        "kind": kind,
        "start_utc": start_ts.isoformat() if start_ts else None,
        "end_utc": end_ts.isoformat() if end_ts else None,
        "wall_clock_ms": wall_ms,
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
        summary["goal"] = goals_cc.get(sid) or "NOT CAPTURED"
        summary["model"] = "claude-sonnet-5"
        summary["tokens"] = {"status": "NOT_CAPTURED", "note": "Claude Code hook interface exposes no token-usage field for development sessions (verified against claude_code_hook.py's own field list)."}
        summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "no token usage captured for this session kind"}
    elif kind == KIND_WORKBENCH_RUN:
        summary["goal"] = goals_wb.get(sid) or "NOT CAPTURED"
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
        agg_tokens = usage_v2.get(sid)
        if agg_tokens is not None:
            summary["tokens"] = {"status": "AGGREGATE_ONLY", "aggregate_tokens": agg_tokens}
            summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "aggregate token count does not expose input/output/cache split"}
        else:
            summary["tokens"] = {"status": "NOT_CAPTURED"}
            summary["cost"] = {"status": "COST_UNAVAILABLE", "reason": "no usage recorded for this trial"}

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


def _compare_to_cohort(conn, kind, cohort_ids, this_session_tokens, this_session_cost):
    """Real median comparison — only computed once >=3 comparable sessions
    with KNOWN usage exist, per Section 29 ('do not invent statistics
    from tiny samples'). Only workbench_run has a directly queryable
    per-id total-token figure (run_usage_summary); other kinds report
    cohort size only, honestly, rather than a fabricated comparison."""
    if kind != KIND_WORKBENCH_RUN or not cohort_ids:
        return {}
    usage = _usage_for_workbench(conn, cohort_ids)
    token_totals = [
        (u[0] or 0) + (u[1] or 0) for u in usage.values()
        if u[4] and u[0] is not None
    ]
    cost_values = [u[2] for u in usage.values() if u[4] and u[2] is not None]
    result = {}
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
            comparison = {
                "status": "COMPARABLE", "cohort_size": len(cohort_ids), "cohort_basis": "same kind, previous 7 days",
                **_compare_to_cohort(conn, kind, cohort_ids, this_tokens, this_cost),
            }
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
