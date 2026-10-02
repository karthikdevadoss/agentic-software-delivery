"""The governance decision boundary, as code.

WHY THIS EXISTS
This project's most expensive lesson is that a principle which is written down
but never evaluated at a decision point is not a control. `agent/
governance_clauses.py` checks that the RULES still exist in the canonical files.
It cannot check that they FIRE. This module is where they fire.

WHAT IT IS, AND THE LINE IT REFUSES TO CROSS
It is a deterministic policy engine over TYPED FACTS about a request. It is
emphatically **not** a reader of prose.

That distinction is the whole design, and it is not caution for its own sake.
Deep Consensus Sprints 5 and 6 produced two opposite false headlines from the
same mistake -- a substring match asked to decide something semantic -- and the
honest conclusion was recorded as unapproved lesson A17: treat any assertion
over prose in a guard, scorer, identity mechanism, routing rule or test as
suspect by default. Building a lexical pseudo-reasoner for governance would
repeat that error in the one place where a false PASS is most expensive.

So the division of labour is explicit and the engine's inputs say so:

    A JUDGEMENT ("does this public page contain private terminology?",
    "is this claim supported by evidence?", "is this work genuinely required
    for system integrity?") is made elsewhere -- by a dedicated checker such as
    agent/test_public_leakage.py, by the claim-boundary authority, or by the
    Owner -- and is handed to this engine as an already-decided typed field.

    A DECISION ("given those facts, may this start / continue / must it stop /
    must a human look at it?") is what this engine makes, mechanically, from
    the typed fields alone.

Feed it prose and it will refuse, because `Request` accepts no prose. That is
the guard-rail, enforced by construction rather than by a comment.

THE FOUR TERMINAL STATES, from CLAUDE.md's "Mission value gate":
    CONTINUE / REDIRECT / STOPPED_BY_RULE / NEEDS_OWNER_GOAL_REVIEW

Run:  python agent/governance_decision.py     # prints the case table
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class State(str, Enum):
    CONTINUE = "CONTINUE"
    REDIRECT = "REDIRECT"
    STOPPED_BY_RULE = "STOPPED_BY_RULE"
    NEEDS_OWNER_GOAL_REVIEW = "NEEDS_OWNER_GOAL_REVIEW"


class Disposition(str, Enum):
    FIX_NOW = "FIX_NOW"
    ADD_GUARD_OR_TEST = "ADD_GUARD_OR_TEST"
    UPDATE_CANONICAL_KNOWLEDGE = "UPDATE_CANONICAL_KNOWLEDGE"
    NEEDS_OWNER = "NEEDS_OWNER"
    NO_ACTION_WITH_REASON = "NO_ACTION_WITH_REASON"


# ---------------------------------------------------------------------------
# Programmes frozen by an existing, already-authorized Owner decision, and the
# actions that decision forbids. Objective: membership in a set, not a reading
# of intent. docs/DEEP_CONSENSUS_FINAL_CLOSURE_2026-10-02.md is the record.
# ---------------------------------------------------------------------------
FROZEN_PROGRAMMES = {
    "deep_consensus": {
        "start_sprint",
        "rerun",
        "ablation",
        "replacement_benchmark",
        "local_mvp",
        "rescue_experiment",
        "new_architecture",
    }
}

# Continuation arguments that carry ZERO evidential weight. Each is a typed
# flag, so no sentence is being parsed -- the caller has already classified the
# argument being made.
WORTHLESS_JUSTIFICATIONS = {
    "sunk_cost": "effort already spent is not evidence about the next increment",
    "no_stop_rule_fired": "absence of a reason to stop is not a reason to continue",
    "code_volume": "more code is not more useful value",
    "activity": "activity is not value",
    "technology_count": "a longer technology list is not value",
    "product_self_interest": "a product may not justify itself by its own growth",
    "model_recommendation": "a model's preference is not the Owner's purpose",
    "model_memory": "a rule remembered by a model is not canonical governance",
    "roadmap_contains_it": "a roadmap is not strategy and does not authorize itself",
}

# Decisions reserved to the Owner. Objective: a named category, not a judgement.
OWNER_RESERVED = {
    "strategy",
    "purpose",
    "governance_authority",
    "mission_scope_expansion",
    "publication",
    "spend",
    "frozen_evidence",
    "subjective_preference",
    "private_public_disclosure",
}


@dataclass
class Request:
    """Typed facts about a request. Deliberately no free-text field anywhere:
    a judgement must be resolved to a boolean or an enum BEFORE it gets here."""

    action: str = "proceed"
    programme: str | None = None

    # admission
    has_mission_card: bool = True
    hiring_audience: str | None = "recruiter_hr"      # or "none_enabling_work"
    required_for_system_integrity: bool = False
    company_objective: str | None = "employment"      # None = unlinked to any objective

    # continuation
    continuation_justifications: list[str] = field(default_factory=list)
    produced_recruiter_visible_value: bool = True
    produced_hiring_relevant_proof: bool = True
    consecutive_sprints_without_either: int = 0

    # what the request would touch
    affects: list[str] = field(default_factory=list)

    # already-decided judgements, made by a checker or a human elsewhere
    claim_supported_by_evidence: bool = True
    public_text_contains_private_terms: bool = False
    conflicts_with_frozen_evidence: bool = False
    canonical_source: str = "private_git"             # or "model_memory"

    # a retro finding, if this request is one
    retro_lesson_objective: bool | None = None
    retro_lesson_in_scope: bool | None = None
    retro_lesson_deterministically_verifiable: bool | None = None

    # context
    independent_authorized_work_available: bool = False


@dataclass
class Decision:
    state: State
    rule: str
    reasons: list[str] = field(default_factory=list)
    disposition: Disposition | None = None
    continue_independent_work: bool = False
    frozen_evidence_may_change: bool = False

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.state.value} [{self.rule}]"


def evaluate(request: Request) -> Decision:
    """Apply the governance rules, highest-authority first.

    Order matters and is itself a rule: an objective frozen-programme stop
    outranks every argument for proceeding, and the private/public boundary
    outranks a request to publish. Nothing below can rescue something stopped
    above."""
    reasons: list[str] = []

    # --- 1. frozen programme. Objective, pre-authorized, outranks everything.
    forbidden = FROZEN_PROGRAMMES.get(request.programme or "", set())
    if request.action in forbidden:
        return Decision(
            State.STOPPED_BY_RULE,
            rule="frozen-programme-guard",
            reasons=[
                f"{request.programme!r} is paused by an existing Owner decision and "
                f"{request.action!r} is one of the actions that decision forbids",
                "reopening it needs a NEW explicit Owner decision; it cannot be "
                "inferred from the lessons the programme produced",
            ],
            continue_independent_work=request.independent_authorized_work_available,
        )

    # --- 2. protected evidence is immutable. Authority does not rewrite history.
    if "frozen_evidence" in request.affects:
        return Decision(
            State.STOPPED_BY_RULE,
            rule="frozen-evidence-immutable",
            reasons=[
                "frozen evidence, pre-registered results and historical records are "
                "not rewritten; governance may interpret evidence and may never alter it",
                "the Owner may decide what happens next; he does not decide what "
                "already happened",
            ],
            continue_independent_work=request.independent_authorized_work_available,
            frozen_evidence_may_change=False,
        )

    if request.conflicts_with_frozen_evidence:
        return Decision(
            State.NEEDS_OWNER_GOAL_REVIEW,
            rule="owner-preference-vs-frozen-evidence",
            reasons=[
                "an Owner preference conflicts with frozen historical evidence",
                "the Owner may choose a different FUTURE action; the historical record "
                "stays unchanged, and both readings are preserved and labelled",
            ],
            continue_independent_work=request.independent_authorized_work_available,
            frozen_evidence_may_change=False,
        )

    # --- 3. private/public boundary, before anything is published.
    if request.public_text_contains_private_terms:
        return Decision(
            State.STOPPED_BY_RULE,
            rule="private-public-boundary",
            reasons=[
                "public material carries private governance terminology; public "
                "surfaces use ordinary professional engineering language",
                "judged by the leakage checker, not by this engine",
            ],
            continue_independent_work=request.independent_authorized_work_available,
        )

    if "private_public_disclosure" in request.affects or (
        "publication" in request.affects
    ):
        return Decision(
            State.NEEDS_OWNER_GOAL_REVIEW,
            rule="owner-reserved-decision",
            reasons=[
                "publication and private/public disclosure are reserved to the Owner",
            ],
            continue_independent_work=request.independent_authorized_work_available,
        )

    # --- 4. an unsupported public claim is removed, not dressed up.
    if not request.claim_supported_by_evidence:
        return Decision(
            State.REDIRECT,
            rule="unsupported-claim",
            reasons=[
                "the claim is not supported by the claim-boundary authority",
                "remove or weaken the claim; never invent evidence, and never "
                "convert missing evidence into positive evidence",
            ],
            disposition=Disposition.FIX_NOW,
            continue_independent_work=True,
        )

    # --- 5. a retro finding is dispositioned, never merely recorded.
    if request.retro_lesson_objective is not None:
        objective = bool(request.retro_lesson_objective)
        in_scope = bool(request.retro_lesson_in_scope)
        verifiable = bool(request.retro_lesson_deterministically_verifiable)
        owner_reserved = sorted(set(request.affects) & OWNER_RESERVED)
        if owner_reserved:
            return Decision(
                State.NEEDS_OWNER_GOAL_REVIEW,
                rule="retro-disposition",
                reasons=[f"the correction would touch {owner_reserved}, reserved to the Owner"],
                disposition=Disposition.NEEDS_OWNER,
                continue_independent_work=True,
            )
        if objective and in_scope and verifiable:
            return Decision(
                State.CONTINUE,
                rule="retro-disposition",
                reasons=[
                    "objective, in scope and deterministically verifiable, so it is "
                    "corrected now rather than queued",
                    "a lesson recorded as prose with no disposition is an incomplete retro",
                ],
                disposition=Disposition.FIX_NOW,
            )
        if objective and verifiable and not in_scope:
            return Decision(
                State.NEEDS_OWNER_GOAL_REVIEW,
                rule="retro-disposition",
                reasons=["the correction is outside the approved scope"],
                disposition=Disposition.NEEDS_OWNER,
                continue_independent_work=True,
            )
        return Decision(
            State.CONTINUE,
            rule="retro-disposition",
            reasons=["not deterministically correctable now; make recurrence detectable"],
            disposition=Disposition.ADD_GUARD_OR_TEST,
        )

    # --- 6. other Owner-reserved categories.
    reserved = sorted(set(request.affects) & OWNER_RESERVED)
    if reserved:
        return Decision(
            State.NEEDS_OWNER_GOAL_REVIEW,
            rule="owner-reserved-decision",
            reasons=[f"{reserved} is reserved to the Owner; a model does not decide it"],
            continue_independent_work=request.independent_authorized_work_available,
        )

    # --- 7. admission. A substantial mission needs a Mission Card.
    if not request.has_mission_card:
        return Decision(
            State.STOPPED_BY_RULE,
            rule="mission-card-required",
            reasons=[
                "substantial work may not start without a Mission Card; the gate is "
                "admission control, and starting without one is the control not firing",
            ],
            continue_independent_work=request.independent_authorized_work_available,
        )

    # --- 8. a product must serve an authorized company objective.
    if request.company_objective is None:
        return Decision(
            State.NEEDS_OWNER_GOAL_REVIEW,
            rule="product-subordinate-to-company",
            reasons=[
                "the work is not linked to an authorized company objective or a "
                "legitimate durable company capability",
                "a product is subordinate to the company purpose and may not justify "
                "itself by its own growth",
            ],
            continue_independent_work=request.independent_authorized_work_available,
        )

    # --- 9. enabling work is legitimate without a recruiter artifact.
    enabling = (
        request.hiring_audience in (None, "none_enabling_work")
        and request.required_for_system_integrity
    )

    # --- 10. worthless continuation arguments carry no weight.
    worthless = [j for j in request.continuation_justifications if j in WORTHLESS_JUSTIFICATIONS]
    real = [j for j in request.continuation_justifications if j not in WORTHLESS_JUSTIFICATIONS]
    for j in worthless:
        reasons.append(f"{j!r} carries no weight: {WORTHLESS_JUSTIFICATIONS[j]}")

    if worthless and not real and not enabling:
        return Decision(
            State.REDIRECT,
            rule="no-valid-continuation-evidence",
            reasons=reasons + [
                "every argument offered for continuing carries zero evidential weight, "
                "so question 4 is answered on current evidence alone -- and nothing "
                "else argued for continuing",
                "rejecting the argument is not the same as answering the question; the "
                "answer is not a default CONTINUE",
            ],
            continue_independent_work=True,
        )

    # --- 11. the drift trigger. Two in a row forces a review, not a stop.
    if request.consecutive_sprints_without_either >= 2 or (
        not request.produced_recruiter_visible_value
        and not request.produced_hiring_relevant_proof
        and not enabling
    ):
        return Decision(
            State.NEEDS_OWNER_GOAL_REVIEW,
            rule="drift-visibility-trigger",
            reasons=reasons + [
                "two consecutive substantial sprints produced neither recruiter-visible "
                "value nor proof that strengthens the hiring argument",
                "a forced Owner review, not an automatic termination: two excellent "
                "sprints pointed slightly away from the objective can fire this",
            ],
            continue_independent_work=request.independent_authorized_work_available,
        )

    if enabling:
        reasons.append(
            "enabling work: no recruiter artifact required, because it is genuinely "
            "required for system integrity"
        )

    return Decision(
        State.CONTINUE,
        rule="continuation-test-passed",
        reasons=reasons or ["the continuation test passed on its own merits"],
    )


def main() -> int:  # pragma: no cover - reporting convenience
    from governance_cases import CASES

    print(f"{'#':<4} {'EXPECTED':<24} {'ACTUAL':<24} {'OK':<4} CASE")
    print("-" * 110)
    bad = 0
    for number, name, request, expected, _ in CASES:
        got = evaluate(request)
        ok = got.state == expected
        bad += 0 if ok else 1
        print(f"{number:<4} {expected.value:<24} {got.state.value:<24} "
              f"{'yes' if ok else 'NO':<4} {name}")
    print("-" * 110)
    print(f"{len(CASES) - bad} of {len(CASES)} cases resolve as specified")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
