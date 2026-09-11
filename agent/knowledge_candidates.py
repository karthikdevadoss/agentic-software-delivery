"""
Knowledge-candidate pipeline (Phase E14: "implement a small REAL version").

Previously the idea of deriving reusable knowledge from a completed run was
only conceptual. This is the smallest real, evidence-backed implementation:
derive a KNOWLEDGE CANDIDATE from a run/incident's already-observable
evidence (requirement, run_id, git commit, decisions, tests,
failure/root cause, actors, human intervention, tokens/cost, lessons),
store it durably via the EXISTING event ledger (new event_type strings,
existing JSONB payload column -- no schema migration), and require an
explicit, separately-recorded state transition before anything is treated
as canonical knowledge.

States: CANDIDATE -> VERIFIED / STALE / SUPERSEDED.

Non-negotiable rules (per this project's constitution/task instructions):
  - NEVER store hidden chain-of-thought -- only the structured,
    already-observable fields the caller explicitly passes in.
  - NEVER auto-promote a candidate to VERIFIED. create_candidate() always
    lands in CANDIDATE. Only set_candidate_state(), called by a human
    reviewer or an explicit reviewer-approved step, can change that.
  - The ledger is append-only: a state change is recorded as a NEW event,
    never an in-place mutation of the original candidate event, so the
    full review history (who changed it, when, why) is preserved.
"""

import event_ledger as el

CANDIDATE = "CANDIDATE"
VERIFIED = "VERIFIED"
STALE = "STALE"
SUPERSEDED = "SUPERSEDED"

VALID_STATES = frozenset({CANDIDATE, VERIFIED, STALE, SUPERSEDED})

CANDIDATE_EVENT_TYPE = "knowledge_candidate"
STATE_CHANGE_EVENT_TYPE = "knowledge_candidate_state_change"


def create_candidate(*, run_id, requirement_text=None, git_commit=None,
                      decisions=None, tests=None, failure_root_cause=None,
                      actors=None, human_intervention=None,
                      tokens_cost=None, lessons=None,
                      source="knowledge_candidate_pipeline"):
    """Derive and durably record ONE knowledge candidate from real,
    already-observed evidence. Always created in state CANDIDATE."""
    payload = {
        "state": CANDIDATE,
        "requirement_text": requirement_text,
        "git_commit": git_commit,
        "decisions": decisions or [],
        "tests": tests or [],
        "failure_root_cause": failure_root_cause,
        "actors": actors or [],
        "human_intervention": human_intervention,
        "tokens_cost": tokens_cost,
        "lessons": lessons or [],
    }
    result = el.record_event(
        CANDIDATE_EVENT_TYPE, run_id=run_id, source=source,
        activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
        status=CANDIDATE, payload=payload,
    )
    return {**result, "state": CANDIDATE}


def set_candidate_state(run_id, new_state, *, reviewer=None, reason=None):
    """Explicit, human/reviewer-driven state transition. This is the ONLY
    function in this module that can move a candidate out of CANDIDATE.
    Raises ValueError for an invalid state rather than silently coercing
    it, since a candidate's review status must never be ambiguous."""
    if new_state not in VALID_STATES:
        raise ValueError(f"invalid knowledge candidate state: {new_state!r}")
    return el.record_event(
        STATE_CHANGE_EVENT_TYPE, run_id=run_id,
        source="knowledge_candidate_pipeline",
        activity_class=el.ACTIVITY_CLASS_PRODUCT_DEVELOPMENT,
        status=new_state,
        payload={"new_state": new_state, "reviewer": reviewer, "reason": reason},
    )


def list_candidates_for_review(limit=50):
    """Read-only projection: every knowledge_candidate event, each
    annotated with its CURRENT state (the most recent state_change event
    for that run_id, or CANDIDATE if none has ever been recorded). Never
    reports something as VERIFIED unless an explicit state-change event
    for that exact run_id says so."""
    conn = el._connect()
    try:
        el.ensure_schema()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT run_id, timestamp_utc, payload
                FROM delivery_events
                WHERE event_type = %s
                ORDER BY timestamp_utc DESC
                LIMIT %s
                """,
                (CANDIDATE_EVENT_TYPE, limit),
            )
            candidates = cur.fetchall()

            cur.execute(
                """
                SELECT DISTINCT ON (run_id) run_id, status, timestamp_utc, payload
                FROM delivery_events
                WHERE event_type = %s
                ORDER BY run_id, timestamp_utc DESC
                """,
                (STATE_CHANGE_EVENT_TYPE,),
            )
            latest_state_by_run = {row[0]: row for row in cur.fetchall()}
    finally:
        conn.close()

    results = []
    for run_id, ts, payload in candidates:
        state_row = latest_state_by_run.get(run_id)
        current_state = state_row[1] if state_row else CANDIDATE
        results.append({
            "run_id": run_id,
            "created_at_utc": ts.isoformat(),
            "current_state": current_state,
            "candidate": payload,
            "last_reviewed_at_utc": state_row[2].isoformat() if state_row else None,
            "review_note": (state_row[3] or {}) if state_row else None,
        })
    return results
