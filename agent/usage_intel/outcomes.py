"""Outcome records: what an AI activity actually achieved.

Cost alone says nothing about value. An outcome ties a task to a result and
says HOW that result is known. Only two kinds of evidence make a success
"verified":

  objective      a machine check passed (tests, a production assertion, a
                 correctly answered assessment)
  human          a person approved or confirmed it

Two more kinds are recorded but never counted as verified:

  estimated      someone's estimate (e.g. "this probably saved 20 minutes")
  ai_unverified  an AI's own judgement of its work

Time saved is likewise split: `measured` (a real before/after timing) versus
`estimated`. They are reported separately and never summed together.
"""
from __future__ import annotations

import dataclasses
from enum import Enum


class Evidence(str, Enum):
    OBJECTIVE = "objective"
    HUMAN = "human"
    ESTIMATED = "estimated"
    AI_UNVERIFIED = "ai_unverified"
    NONE = "none"


VERIFYING_EVIDENCE = {Evidence.OBJECTIVE.value, Evidence.HUMAN.value}

# Configurable outcome types (the owner can record any string; these are the defaults).
OUTCOME_TYPES = {
    "code_fix_verified": "Verified code fix",
    "dev_task_completed": "Completed software development task",
    "support_resolution": "Successful customer support resolution",
    "research_completed": "Completed research task",
    "document_approved": "Approved document",
    "workflow_completed": "Successfully completed workflow",
    "learning_objective_verified": "Verified learning objective",
    "ai_action_approved": "Human-approved AI action",
}


@dataclasses.dataclass
class Outcome:
    outcome_id: str
    task_id: str
    outcome_type: str
    status: str                      # completed | failed | abandoned | in_progress
    evidence: str = Evidence.NONE.value
    timestamp: str | None = None
    org_id: str | None = None
    team_id: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    workflow_id: str | None = None
    activity_category: str | None = None
    difficulty: str | None = None    # simple | standard | complex -- comparisons stay within a difficulty
    attempts: int | None = None      # 1 = first-attempt success
    corrections: int | None = None   # human corrections / rework cycles
    human_review_minutes: float | None = None
    time_saved_minutes: float | None = None
    time_saved_source: str | None = None   # measured | estimated
    feedback: str | None = None            # short, never raw content
    dataset: str = "live"

    @property
    def verified_success(self) -> bool:
        return self.status == "completed" and self.evidence in VERIFYING_EVIDENCE

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["verified_success"] = self.verified_success
        return d


def value_metrics(outcomes: list[Outcome], cost_by_task: dict[str, float],
                  active_hours: float | None = None, hourly_rate: float | None = None) -> dict:
    """Value of AI spend, computed only from what the records actually support.

    cost_by_task: estimated API cost of every model call attributed to a task,
    INCLUDING failed attempts and retries (that is the real cost of getting there).
    active_hours / hourly_rate: optional, supplied by the user; ROI is only
    computed when both are given and is always labelled an estimate.
    """
    tasks = {o.task_id: o for o in outcomes}  # latest record per task wins (caller orders by time)
    total = len(tasks)
    completed = [o for o in tasks.values() if o.status == "completed"]
    verified = [o for o in tasks.values() if o.verified_success]
    unsuccessful = [o for o in tasks.values() if o.status in ("failed", "abandoned")]
    with_attempts = [o for o in tasks.values() if o.attempts is not None and o.status == "completed"]
    first_attempt = [o for o in with_attempts if o.attempts == 1]
    with_corr = [o for o in tasks.values() if o.corrections is not None]

    def cost_of(rows):
        known = [cost_by_task[o.task_id] for o in rows if cost_by_task.get(o.task_id) is not None]
        return (round(sum(known), 6) if known else None), len(known)

    total_cost, priced = cost_of(list(tasks.values()))
    unsuccessful_cost, _ = cost_of(unsuccessful)
    measured_saved = [o.time_saved_minutes for o in tasks.values() if o.time_saved_minutes is not None and o.time_saved_source == "measured"]
    estimated_saved = [o.time_saved_minutes for o in tasks.values() if o.time_saved_minutes is not None and o.time_saved_source == "estimated"]
    review = [o.human_review_minutes for o in tasks.values() if o.human_review_minutes is not None]

    def ratio(n, d):
        return round(n / d, 4) if d else None

    out = {
        "tasks": total,
        "completed": len(completed),
        "verified_successes": len(verified),
        "evidence_mix": {e.value: sum(1 for o in tasks.values() if o.evidence == e.value) for e in Evidence},
        "task_success_rate": ratio(len(completed), total),
        "verified_success_rate": ratio(len(verified), total),
        "first_attempt_success_rate": ratio(len(first_attempt), len(with_attempts)),
        "first_attempt_basis": f"{len(with_attempts)} completed tasks with attempt counts",
        "rework_rate": ratio(sum(1 for o in with_corr if o.corrections > 0), len(with_corr)),
        "total_cost": total_cost,
        "cost_coverage": f"{priced} of {total} tasks have a known cost",
        "cost_per_task": ratio(total_cost, priced) if total_cost is not None else None,
        "cost_per_verified_success": round(total_cost / len(verified), 6) if (total_cost is not None and verified) else None,
        "cost_of_unsuccessful_attempts": unsuccessful_cost,
        "human_review_minutes": round(sum(review), 1) if review else None,
        "time_saved_minutes_measured": round(sum(measured_saved), 1) if measured_saved else None,
        "time_saved_minutes_estimated": round(sum(estimated_saved), 1) if estimated_saved else None,
        "verified_per_hour": ratio(len(verified), active_hours) if active_hours else None,
        "roi_estimate": None,
        "roi_basis": None,
    }
    saved = sum(measured_saved) + sum(estimated_saved)
    if hourly_rate and total_cost and saved:
        value = saved / 60 * hourly_rate
        out["roi_estimate"] = round((value - total_cost) / total_cost, 2)
        out["roi_basis"] = (f"ESTIMATE: ({saved:.0f} min saved "
                            f"[{sum(measured_saved):.0f} measured, {sum(estimated_saved):.0f} estimated] "
                            f"x {hourly_rate}/h - cost) / cost. Not a measured financial return.")
    return out
