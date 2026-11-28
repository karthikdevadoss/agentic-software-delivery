"""AI-assisted learning efficiency: knowledge gained per hour and per dollar,
without counting an explanation as learning.

A concept is VERIFIED only by evidence: a correctly answered assessment or a
reviewed practical exercise. Generating an explanation, studying, or a
self-report never verifies anything. Retention tests are measured separately
(a concept can be verified once and still be forgotten later).

Records come from three places, each labelled by `source`:
  platform   learning done through this platform's own AI calls
  manual     typed in by the learner (owner-only form)
  imported   from a JSON/CSV export (e.g. sessions held in a personal chat app,
             whose token usage is NOT available and is never invented)
  demo       fictional demonstration data
"""
from __future__ import annotations

import csv
import dataclasses
import io
import json

EVENTS = ("introduced", "studied", "verification", "retention_test")
VERIFYING = {"assessment", "reviewed_exercise"}
SOURCES = {"platform", "manual", "imported", "demo"}


@dataclasses.dataclass
class LearningRecord:
    session_id: str
    section: str
    concept: str
    event: str                       # introduced | studied | verification | retention_test
    timestamp: str | None = None
    user_id: str | None = None
    correct: bool | None = None      # for verification / retention_test
    attempt: int | None = None       # 1 = first attempt
    evidence: str | None = None      # assessment | reviewed_exercise | self_report | ai_explanation
    minutes: float | None = None
    source: str = "manual"

    def __post_init__(self):
        if self.event not in EVENTS:
            raise ValueError(f"event must be one of {EVENTS}")
        if self.source not in SOURCES:
            raise ValueError(f"source must be one of {sorted(SOURCES)}")

    @property
    def verifies(self) -> bool:
        return self.event == "verification" and self.correct is True and self.evidence in VERIFYING


def metrics(records: list[LearningRecord], cost_by_session: dict[str, float] | None = None,
            objectives: dict[str, int] | None = None) -> dict:
    """objectives: section -> target number of verified concepts (optional)."""
    cost_by_session = cost_by_session or {}
    introduced = {(r.section, r.concept) for r in records if r.event == "introduced"}
    studied = {(r.section, r.concept) for r in records if r.event in ("introduced", "studied")}
    verified = {(r.section, r.concept) for r in records if r.verifies}
    ver_attempts = [r for r in records if r.event == "verification"]
    first = [r for r in ver_attempts if r.attempt == 1]
    retention = [r for r in records if r.event == "retention_test" and r.correct is not None]
    minutes = [r.minutes for r in records if r.minutes is not None]
    sessions = {r.session_id for r in records}
    cost_known = [cost_by_session[s] for s in sessions if cost_by_session.get(s) is not None]
    cost = round(sum(cost_known), 6) if cost_known else None
    hours = sum(minutes) / 60 if minutes else None

    attempts_per_verified = None
    if verified:
        per = {}
        for r in ver_attempts:
            per.setdefault((r.section, r.concept), 0)
            per[(r.section, r.concept)] += 1
        attempts_per_verified = round(sum(per[c] for c in verified if c in per) / len(verified), 2)

    sections = {}
    for r in records:
        s = sections.setdefault(r.section, {"introduced": set(), "verified": set()})
        if r.event == "introduced":
            s["introduced"].add(r.concept)
        if r.verifies:
            s["verified"].add(r.concept)
    by_section = []
    for name, s in sections.items():
        target = (objectives or {}).get(name)
        by_section.append({"section": name, "introduced": len(s["introduced"]), "verified": len(s["verified"]),
                           "objective": target,
                           "progress": round(len(s["verified"]) / target, 4) if target else None})

    return {
        "sessions": len(sessions),
        "concepts_introduced": len(introduced),
        "concepts_studied": len(studied),
        "concepts_verified": len(verified),
        "verification_attempts": len(ver_attempts),
        "attempts_per_verified_concept": attempts_per_verified,
        "first_attempt_accuracy": round(sum(1 for r in first if r.correct) / len(first), 4) if first else None,
        "retention_accuracy": round(sum(1 for r in retention if r.correct) / len(retention), 4) if retention else None,
        "retention_tests": len(retention),
        "learning_minutes": round(sum(minutes), 1) if minutes else None,
        "verified_per_hour": round(len(verified) / hours, 2) if hours else None,
        "ai_cost": cost,
        "ai_cost_coverage": f"{len(cost_known)} of {len(sessions)} sessions have measured AI cost",
        "cost_per_verified_concept": round(cost / len(verified), 6) if (cost is not None and verified) else None,
        "unverified_explanations": len(studied - verified),
        "by_section": sorted(by_section, key=lambda r: r["section"]),
        "sources": sorted({r.source for r in records}),
    }


def parse_import(text: str, fmt: str, user_id: str) -> list[LearningRecord]:
    """JSON (list of objects) or CSV with the LearningRecord field names.
    Every record is stamped source="imported" and the given user; unknown
    fields are rejected rather than silently dropped."""
    allowed = {f.name for f in dataclasses.fields(LearningRecord)} - {"source", "user_id"}
    if fmt == "json":
        rows = json.loads(text)
        if not isinstance(rows, list):
            raise ValueError("JSON import must be a list of records")
    elif fmt == "csv":
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        raise ValueError("format must be json or csv")
    out = []
    for i, row in enumerate(rows):
        extra = set(row) - allowed
        if extra:
            raise ValueError(f"row {i}: unknown fields {sorted(extra)}")
        clean = {k: (None if v in ("", None) else v) for k, v in row.items()}
        if isinstance(clean.get("correct"), str):
            clean["correct"] = clean["correct"].strip().lower() in ("true", "1", "yes")
        for k in ("attempt",):
            if clean.get(k) is not None:
                clean[k] = int(clean[k])
        if clean.get("minutes") is not None:
            clean["minutes"] = float(clean["minutes"])
        out.append(LearningRecord(**clean, user_id=user_id, source="imported"))
    return out
