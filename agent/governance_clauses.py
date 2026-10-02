"""Structural presence gate for the governing clauses this project depends on.

WHAT THIS CHECKS, AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------
This module asserts that a small set of REQUIRED GOVERNING CLAUSES is still
PRESENT in the canonical governance files. That is a structural/reference
check: it proves a clause has not been silently deleted or renamed out of the
file a session is told to obey.

It makes NO claim about what the surrounding prose MEANS. Reading natural
language for truth with substring matching is exactly the pattern that produced
five false conclusions across Deep Consensus Sprints 5 and 6 (see
docs/DEEP_CONSENSUS_FINAL_CLOSURE_2026-10-02.md, unapproved lesson A17), and
this module must never be grown in that direction. "The clause is in the file"
is a fact a substring can establish; "the governance is correct" is not.

Why it exists: governance that lives only in prose can be refactored away by a
later well-meaning edit, and nothing would notice. The six Owner-authorized
Phase-0 decision cases (docs/GOVERNANCE_TEST_CASES_2026-10-02.md) each resolve
by citing a specific clause. If a clause disappears, the case it answers becomes
ambiguous, and this gate turns that into a test failure instead of a surprise
six months later.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# clause_id -> (relative file path, exact required substring, which case it answers)
REQUIRED_CLAUSES = {
    "mission_card_exists": (
        "CLAUDE.md",
        "### Admission: the Mission Card",
        "admission control exists at all",
    ),
    "four_terminal_states": (
        "CLAUDE.md",
        "### The four terminal states",
        "a decision boundary has a defined output vocabulary",
    ),
    "dc_guard_sprint7": (
        "CLAUDE.md",
        "**Sprint 7, a rerun of Sprint 6, an\nablation, a replacement benchmark, a local MVP, "
        "new consensus architecture, or\nimplementing A15–A23.**",
        "cases A and B",
    ),
    "dc_guard_returns_stopped_by_rule": (
        "CLAUDE.md",
        "returns `STOPPED_BY_RULE` and names this section",
        "cases A and B",
    ),
    "sunk_cost_rejected": (
        "CLAUDE.md",
        "**Past effort is never a justification for more effort.**",
        "case C",
    ),
    "no_default_continue": (
        "CLAUDE.md",
        "Absence of a reason\nto stop is not a reason to continue.",
        "case C",
    ),
    "needs_owner_goal_review_weak_value": (
        "CLAUDE.md",
        "hiring value now looks weak",
        "case D",
    ),
    "enabling_work_legitimate": (
        "CLAUDE.md",
        "**Enabling work is legitimate.**",
        "case E",
    ),
    "one_stop_does_not_stop_others": (
        "CLAUDE.md",
        "A stop condition firing on one workstream is never a reason to stop the others.",
        "case F",
    ),
    "frozen_evidence_read_only": (
        "CLAUDE.md",
        "is **read-only**",
        "protected-evidence rule",
    ),
    "public_language_rule": (
        "CLAUDE.md",
        "### Public language",
        "private terminology stays off public surfaces",
    ),
    "constitution_stop_checks": (
        "docs/CONSTITUTION.md",
        "## 19. Purpose, discernment, non-waste and non-attachment are STOP CHECKS",
        "principles are attached to a boundary",
    ),
    "constitution_sunk_cost": (
        "docs/CONSTITUTION.md",
        "**Sunk cost never satisfies the continuation test.**",
        "case C",
    ),
    "constitution_no_rewriting_evidence": (
        "docs/CONSTITUTION.md",
        "**Governance may interpret evidence; it may never rewrite it.**",
        "frozen-evidence rule",
    ),
    "collaboration_roles_superseded_marker": (
        "docs/AI_COLLABORATION.md",
        "## SUPERSEDED 2026-10-02",
        "stale provider-as-architecture text is marked, not deleted",
    ),
    "collaboration_truth_authority": (
        "docs/AI_COLLABORATION.md",
        "### 5. Technical truth authority",
        "deterministic evidence outranks model opinion",
    ),
    "sprint_process_phase4": (
        ".claude/rules/sprint-process.md",
        "### Phase 4: a substantial item carries a Mission Card",
        "retro ends in a continuation state",
    ),
    "sprint_process_continuation_state": (
        ".claude/rules/sprint-process.md",
        "**Continuation state.** Exactly one of `CONTINUE` / `REDIRECT` /",
        "retro ends in a continuation state",
    ),
}


def check_text(required_substring: str, text: str) -> bool:
    """Return True iff the required clause is present. Newlines are normalised
    so a CRLF checkout does not read as a missing clause."""
    return required_substring.replace("\r\n", "\n") in text.replace("\r\n", "\n")


def missing_clauses(repo_root: Path = REPO_ROOT):
    """Return a list of (clause_id, path, answers) for every absent clause."""
    missing = []
    for clause_id, (rel_path, needle, answers) in sorted(REQUIRED_CLAUSES.items()):
        target = repo_root / rel_path
        if not target.exists():
            missing.append((clause_id, rel_path, f"{answers} (FILE MISSING)"))
            continue
        if not check_text(needle, target.read_text(encoding="utf-8")):
            missing.append((clause_id, rel_path, answers))
    return missing


def main() -> int:
    missing = missing_clauses()
    total = len(REQUIRED_CLAUSES)
    if not missing:
        print(f"GOVERNANCE CLAUSE GATE: PASS -- {total}/{total} required clauses present")
        return 0
    print(f"GOVERNANCE CLAUSE GATE: FAIL -- {len(missing)} of {total} required clauses absent")
    for clause_id, rel_path, answers in missing:
        print(f"  MISSING  {clause_id}  ({rel_path})  -- governs: {answers}")
    print("\nA required governing clause was deleted or reworded. The decision case it")
    print("answers is now ambiguous. Restore the clause, or change the clause list")
    print("deliberately with an Owner decision recorded in docs/DECISIONS.md.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
