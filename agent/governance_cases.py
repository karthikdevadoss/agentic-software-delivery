"""The twenty governance acceptance cases, as structured requests.

The Owner specified these BEFORE this governance was mechanised, which is what
makes them acceptance cases rather than a description of whatever the code
happens to do. Cases 1-12 came with the main contract, 13-20 with the addendum
that established the company framework as the parent of the platform.

Each entry is: (number, name, Request, expected State, note).

Note on honesty of coverage: a case here is a check that the DECISION is right
given typed facts. Where a case depends on a judgement -- is this text private,
is this claim supported, is this genuinely required for system integrity -- that
judgement is an INPUT, resolved by a dedicated checker or by the Owner. These
cases do not prove those judgements are made correctly; they prove that once
made, the decision follows. That boundary is in governance_decision's docstring
and it is the deliberate design, not a gap left open by accident.
"""

from governance_decision import Request, State

CASES = [
    (
        1,
        "mission starts without a required Mission Card",
        Request(action="start_sprint", has_mission_card=False,
                independent_authorized_work_available=True),
        State.STOPPED_BY_RULE,
        "admission control must refuse; starting anyway is the control not firing",
    ),
    (
        2,
        "'we already spent 20 hours, so continue'",
        Request(continuation_justifications=["sunk_cost"]),
        State.REDIRECT,
        "sunk cost provides ZERO continuation evidence, and rejecting it is not a "
        "default CONTINUE",
    ),
    (
        3,
        "'no objective stop rule fired'",
        Request(continuation_justifications=["no_stop_rule_fired"]),
        State.REDIRECT,
        "absence of a reason to stop is not a reason to continue",
    ),
    (
        4,
        "Deep Consensus Sprint 7 requested",
        Request(programme="deep_consensus", action="start_sprint",
                independent_authorized_work_available=True),
        State.STOPPED_BY_RULE,
        "named forbidden action on a frozen programme",
    ),
    (
        5,
        "Deep Consensus replacement benchmark requested",
        Request(programme="deep_consensus", action="replacement_benchmark"),
        State.STOPPED_BY_RULE,
        "building a harder benchmark after seeing the result is how negative "
        "results disappear",
    ),
    (
        6,
        "necessary security fix with no recruiter artifact",
        Request(action="security_fix", hiring_audience="none_enabling_work",
                required_for_system_integrity=True,
                produced_recruiter_visible_value=False,
                produced_hiring_relevant_proof=False),
        State.CONTINUE,
        "enabling work is legitimate; inventing a recruiter story for maintenance "
        "would corrupt the proof system to satisfy a form",
    ),
    (
        7,
        "one subtask stops, independent authorized work remains",
        Request(programme="deep_consensus", action="rerun",
                independent_authorized_work_available=True),
        State.STOPPED_BY_RULE,
        "stop the affected stream only; continue_independent_work must be True",
    ),
    (
        8,
        "retro finds a deterministic bug inside current scope",
        Request(retro_lesson_objective=True, retro_lesson_in_scope=True,
                retro_lesson_deterministically_verifiable=True),
        State.CONTINUE,
        "FIX_NOW, not an indefinite prose-only action item",
    ),
    (
        9,
        "a finding requires changing mission purpose",
        Request(affects=["purpose"], independent_authorized_work_available=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "purpose is the Owner's; a model does not redefine it",
    ),
    (
        10,
        "public text contains private governance terminology",
        Request(public_text_contains_private_terms=True),
        State.STOPPED_BY_RULE,
        "the leakage guard decides the judgement; this is the decision that follows",
    ),
    (
        11,
        "an unsupported recruiter claim is discovered",
        Request(claim_supported_by_evidence=False),
        State.REDIRECT,
        "remove or weaken the claim; never invent evidence",
    ),
    (
        12,
        "Owner preference conflicts with frozen historical evidence",
        Request(conflicts_with_frozen_evidence=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "the Owner may choose a future action; the record stays unchanged",
    ),
    (
        13,
        "'make the platform bigger, that is valuable by itself'",
        Request(company_objective=None,
                continuation_justifications=["product_self_interest"],
                independent_authorized_work_available=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "INSUFFICIENT: a product must link to an authorized company objective",
    ),
    (
        14,
        "'stop learning and applications, platform work is interesting'",
        Request(action="reallocate_tracks",
                affects=["strategy"],
                continuation_justifications=["product_self_interest"],
                independent_authorized_work_available=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "the product cannot consume company strategy by default",
    ),
    (
        15,
        "publish the private company governance architecture",
        Request(action="publish", affects=["private_public_disclosure"],
                independent_authorized_work_available=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "blocked by the private/public boundary absent explicit Owner authorization",
    ),
    (
        16,
        "public roadmap says build X; current company priority says otherwise",
        Request(continuation_justifications=["roadmap_contains_it"]),
        State.REDIRECT,
        "a roadmap is not autonomous company strategy and does not authorize itself",
    ),
    (
        17,
        "retro records a repeated governance failure as a lesson only",
        Request(retro_lesson_objective=True, retro_lesson_in_scope=True,
                retro_lesson_deterministically_verifiable=False),
        State.CONTINUE,
        "INCOMPLETE as prose: requires ADD_GUARD_OR_TEST so recurrence is detectable",
    ),
    (
        18,
        "a feature produced more code but no additional useful value",
        Request(continuation_justifications=["code_volume"],
                produced_recruiter_visible_value=False,
                produced_hiring_relevant_proof=False),
        State.REDIRECT,
        "code volume provides no continuation justification",
    ),
    (
        19,
        "an old private document conflicts with a newer explicit Owner decision",
        Request(affects=["governance_authority"],
                independent_authorized_work_available=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "resolve canonical state while preserving history; authority change is the "
        "Owner's",
    ),
    (
        20,
        "a model remembers a company rule absent from canonical private Git",
        Request(canonical_source="model_memory",
                continuation_justifications=["model_memory"]),
        State.REDIRECT,
        "memory is advisory only; canonical private Git must be updated first",
    ),
    # --- the drift trigger, which is a rule rather than one of the 20 cases ---
    (
        21,
        "two consecutive substantial sprints produced neither value nor proof",
        Request(consecutive_sprints_without_either=2,
                independent_authorized_work_available=True),
        State.NEEDS_OWNER_GOAL_REVIEW,
        "forced Owner review, NOT automatic termination",
    ),
    (
        22,
        "an ordinary authorized sprint with real value and a Mission Card",
        Request(),
        State.CONTINUE,
        "the control must not block legitimate work -- a gate that refuses "
        "everything is as useless as one that refuses nothing",
    ),
]
