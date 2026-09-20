"""
Aggregate agent/verify_change.py's per-run evidence JSON
(agent/.verify_change_evidence/*.json) across every run into real,
honestly-labeled cross-run metrics -- BL-029 (docs/BACKLOG.json).

docs/TESTING_ARCHITECTURE_V1.md's own "Open items" section (gap 5)
flagged this real gap explicitly: verify_change.py's per-run evidence is
real but was never aggregated across runs. docs/RETRO_LOG.md's "Standing
Scrum-process research" section (BL-023, 2026-09-20) independently found
the same industry-wide conclusion from outside sources: story points/
velocity are a broken metric for AI-agent work, and "first-pass yield" /
"rework ratio" / real cost-and-time rollups are the meaningful
replacements (Scrum.org, "From Velocity to Agent Efficiency"). This module
is exactly that aggregation, built directly against verify_change.py's
REAL, ALREADY-WRITTEN evidence schema -- no new capture mechanism.

CLAUDE.md's AI-characteristic defect discipline rule applies directly:
"Do NOT fabricate a metric the real data doesn't support -- if a field
genuinely isn't present in existing evidence files, report it as
'insufficient data' rather than inventing a number." This module was
written only after reading agent/verify_change.py's real evidence-dict
construction (execute(), _save_evidence()) end to end. Real, verified
schema facts it depends on:

- verdict: one of "PASSED" / "FAILED" / "UNVERIFIED" / "DRY_RUN".
- escaped_defects: int or None (BL-020; None means "never revisited",
  NOT "zero defects" -- never treated as 0 here).
- independent_evaluation: {invoked: bool, verdict: str|None,
  findings_count: int|None}.
- commands: list of {name, argv, cwd, exit_code, duration_seconds,
  skipped?} -- duration_seconds is a real per-subprocess wall-clock
  measurement (agent/verify_change.py's _run()).
- changed_paths: list of real file paths the run's git diff touched.
- timestamp_utc: ISO-8601 string, real wall-clock start time.
- NO run_id / parent_run_id / backlog_item_id / "supersedes" field of any
  kind exists anywhere in the schema. That means: there is no way to
  state with certainty "run B is the fix for the issue run A flagged" --
  only a same-changed-paths heuristic is derivable, and it is reported
  as a clearly labeled heuristic, never as an authoritative rework ratio.
- NO cost/token field of any kind exists in this schema -- AI usage/cost
  is captured by a completely separate system (agent/event_ledger.py's
  run_usage_summary event, agent/pricing_config.py), not by
  verify_change.py. Cost rollups are reported as insufficient_data with
  this exact reason, never fabricated as 0.

Usage (from the repository root):
    python agent/aggregate_evidence.py            # human-readable report
    python agent/aggregate_evidence.py --json      # machine-readable
"""

import json
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(AGENT_DIR))
import verify_change as vc  # noqa: E402 -- reuses the real EVIDENCE_DIR, no duplicated path constant


def _load_runs(evidence_dir=None) -> list:
    """Real evidence files only -- a file that fails to parse as JSON is
    skipped (never crashes the whole aggregation over one corrupt file),
    same defensive pattern as verify_change.aggregate_evidence()."""
    d = Path(evidence_dir) if evidence_dir is not None else vc.EVIDENCE_DIR
    if not d.is_dir():
        return []
    runs = []
    for f in sorted(d.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        data["_source_file"] = f.name
        runs.append(data)
    return runs


def _is_clean_first_pass(run: dict) -> bool:
    """PASSED, no known escaped defects, and (if independently evaluated)
    zero findings. escaped_defects=None ("never revisited") counts as
    clean here -- it is not evidence of a defect, just absent follow-up."""
    if run.get("verdict") != "PASSED":
        return False
    if run.get("escaped_defects"):  # None or 0 -> fine; >0 -> not clean
        return False
    ie = run.get("independent_evaluation") or {}
    if ie.get("invoked") and (ie.get("findings_count") or 0) > 0:
        return False
    return True


def _base_counts(runs: list) -> dict:
    """The same field semantics as verify_change.aggregate_evidence(),
    computed from the already-loaded run list here (avoids re-globbing
    EVIDENCE_DIR a second time) plus one extra real breakdown
    (verdict_counts) that function doesn't provide."""
    evaluated = 0
    evaluated_with_findings = 0
    total_escaped_defects = 0
    known_escaped_defect_runs = 0
    verdict_counts = {}
    for r in runs:
        ie = r.get("independent_evaluation") or {}
        if ie.get("invoked"):
            evaluated += 1
            if (ie.get("findings_count") or 0) > 0:
                evaluated_with_findings += 1
        if r.get("escaped_defects") is not None:
            known_escaped_defect_runs += 1
            total_escaped_defects += r["escaped_defects"]
        v = r.get("verdict") or "UNKNOWN"
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
    return {
        "independently_evaluated_runs": evaluated,
        "evaluated_runs_with_findings": evaluated_with_findings,
        "runs_with_known_escaped_defect_count": known_escaped_defect_runs,
        "total_known_escaped_defects": total_escaped_defects,
        "verdict_counts": verdict_counts,
    }


def _time_rollup(runs: list) -> dict:
    all_durations = []
    run_totals = []
    for run in runs:
        run_total = 0.0
        any_real = False
        for cmd in (run.get("commands") or []):
            d = cmd.get("duration_seconds")
            if isinstance(d, (int, float)):
                all_durations.append(d)
                run_total += d
                any_real = True
        if any_real:
            run_totals.append(run_total)
    if not run_totals:
        return {
            "available": False,
            "reason": (
                "no evidence run contained a command with a real duration_seconds "
                "value (no evidence yet, or all recorded runs were --dry-run)"
            ),
        }
    return {
        "available": True,
        "runs_with_timing": len(run_totals),
        "total_command_seconds": round(sum(all_durations), 1),
        "total_wall_seconds_by_run": round(sum(run_totals), 1),
        "avg_run_seconds": round(sum(run_totals) / len(run_totals), 1),
        "min_run_seconds": round(min(run_totals), 1),
        "max_run_seconds": round(max(run_totals), 1),
    }


def _cost_rollup(runs: list) -> dict:
    """agent/verify_change.py's evidence schema has no cost/token field
    anywhere (confirmed by reading execute()'s real evidence-dict
    construction). Never invent a number for a field this schema does
    not carry -- report insufficient_data with the real reason instead."""
    cost_like_keys = {"cost", "cost_usd", "tokens", "token_count", "usage", "model", "input_tokens", "output_tokens"}
    found = set()
    for run in runs:
        found |= (set(run.keys()) & cost_like_keys)
    return {
        "available": False,
        "reason": (
            "agent/verify_change.py's evidence schema has no cost/token field; AI "
            "usage/cost is captured separately by agent/event_ledger.py's "
            "run_usage_summary event and agent/pricing_config.py, not by this tool"
        ),
        "cost_like_keys_actually_found_in_evidence": sorted(found),
    }


def _rework_indicator(runs: list) -> dict:
    """See module docstring: no linking field exists to prove causal
    rework, so the authoritative metric is honestly insufficient_data.
    A secondary, explicitly-labeled heuristic (changed_paths overlap with
    a previously-flagged run) is offered alongside it -- real, derived
    from real fields, but never presented as the authoritative ratio."""
    flagged = []  # (timestamp_utc, frozenset(changed_paths)) for runs with a real flag
    for run in runs:
        escaped = run.get("escaped_defects") or 0
        ie = run.get("independent_evaluation") or {}
        findings = ie.get("findings_count") or 0
        if escaped > 0 or (ie.get("invoked") and findings > 0):
            paths = frozenset(run.get("changed_paths") or [])
            if paths:
                flagged.append((run.get("timestamp_utc") or "", paths))

    heuristic_candidates = 0
    for run in runs:
        ts = run.get("timestamp_utc") or ""
        paths = frozenset(run.get("changed_paths") or [])
        if not paths:
            continue
        for flag_ts, flag_paths in flagged:
            if ts > flag_ts and (paths & flag_paths):
                heuristic_candidates += 1
                break

    return {
        "authoritative_rework_ratio": {
            "available": False,
            "reason": (
                "no run_id/parent_run_id/backlog_item_id/'supersedes' field exists in "
                "agent/verify_change.py's evidence schema, so a later run cannot be "
                "attributed with certainty as 'the fix' for an earlier flagged run"
            ),
        },
        "heuristic_path_overlap_rework_candidates": {
            "count": heuristic_candidates,
            "flagged_runs_used_as_basis": len(flagged),
            "caveat": (
                "HEURISTIC ONLY, not authoritative: counts later runs whose "
                "changed_paths overlap a run flagged via escaped_defects>0 or an "
                "independent-evaluation finding. File-path overlap is not proof of "
                "causal rework -- two unrelated changes can touch the same file."
            ),
        },
    }


def aggregate(evidence_dir=None) -> dict:
    runs = _load_runs(evidence_dir)
    total = len(runs)
    dry_runs = sum(1 for r in runs if r.get("verdict") == "DRY_RUN")
    real_runs = [r for r in runs if r.get("verdict") != "DRY_RUN"]

    if not real_runs:
        first_pass_yield = None
        first_pass_yield_note = (
            f"no non-dry-run evidence to compute from (total_runs={total}, dry_runs={dry_runs}) "
            "-- run `python agent/verify_change.py` (without --dry-run) at least once first"
        )
    else:
        clean = sum(1 for r in real_runs if _is_clean_first_pass(r))
        first_pass_yield = round(clean / len(real_runs), 3)
        first_pass_yield_note = (
            f"{clean}/{len(real_runs)} non-dry-run runs reached PASSED with escaped_defects "
            f"in (None, 0) and no independent-evaluation findings "
            f"({dry_runs} dry-run(s) excluded from this ratio)"
        )

    return {
        "total_runs": total,
        "dry_runs_excluded_from_yield": dry_runs,
        "first_pass_yield": first_pass_yield,
        "first_pass_yield_note": first_pass_yield_note,
        "base_evaluation_counts": _base_counts(runs),
        "time_rollup": _time_rollup(runs),
        "cost_rollup": _cost_rollup(runs),
        "rework": _rework_indicator(runs),
    }


def print_report(result: dict):
    print("=" * 70)
    print("AGGREGATE EVIDENCE -- cross-run metrics (agent/.verify_change_evidence/)")
    print("=" * 70)
    print(f"Total evidence files: {result['total_runs']} "
          f"({result['dry_runs_excluded_from_yield']} dry-run, excluded from yield)")
    print(f"\nFirst-pass yield: {result['first_pass_yield']}")
    print(f"  {result['first_pass_yield_note']}")

    bc = result["base_evaluation_counts"]
    print(f"\nVerdict counts: {bc['verdict_counts']}")
    print(f"Independently evaluated runs: {bc['independently_evaluated_runs']} "
          f"({bc['evaluated_runs_with_findings']} with findings)")
    print(f"Runs with known escaped-defect count: {bc['runs_with_known_escaped_defect_count']} "
          f"(total known escaped defects: {bc['total_known_escaped_defects']})")

    t = result["time_rollup"]
    print("\nTime rollup:")
    if t["available"]:
        print(f"  runs with real timing: {t['runs_with_timing']}")
        print(f"  total wall time across runs: {t['total_wall_seconds_by_run']}s "
              f"(sum of {t['total_command_seconds']}s across all individual commands)")
        print(f"  avg/min/max per run: {t['avg_run_seconds']}s / {t['min_run_seconds']}s / {t['max_run_seconds']}s")
    else:
        print(f"  INSUFFICIENT DATA -- {t['reason']}")

    c = result["cost_rollup"]
    print("\nCost rollup:")
    print(f"  INSUFFICIENT DATA -- {c['reason']}")

    rw = result["rework"]
    print("\nRework indicator:")
    print(f"  authoritative rework ratio: INSUFFICIENT DATA -- {rw['authoritative_rework_ratio']['reason']}")
    h = rw["heuristic_path_overlap_rework_candidates"]
    print(f"  heuristic path-overlap candidates: {h['count']} (basis: {h['flagged_runs_used_as_basis']} flagged run(s))")
    print(f"    {h['caveat']}")
    print("=" * 70)


def main():
    args = sys.argv[1:]
    result = aggregate()
    if "--json" in args:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)


if __name__ == "__main__":
    main()
