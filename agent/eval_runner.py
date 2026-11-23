"""
Version-controlled eval runner for the backend RAG/MCP vertical slice.

These are EVALS (measurements of probabilistic/retrieval behavior against
a labeled dataset), not unit tests. They measure quality, they do not
gate correctness of deterministic code — that remains
agent/test_backend_rag_index.py, agent/test_backend_planning.py,
agent/test_mcp_server.py, and the real application test suite.

Run:
    python agent/eval_runner.py retrieval   -> Eval 1 (Recall@K, MRR)
    python agent/eval_runner.py routing     -> Eval 2 (routing accuracy)
    python agent/eval_runner.py permission  -> permission-leak suite (zero tolerance)
    python agent/eval_runner.py security-routing -> the zero-tolerance subset of routing
    python agent/eval_runner.py agent-decision   -> Eval 3 (agent decisions, REPLAYED
                                                    from the committed recorded results)
    python agent/eval_runner.py self-eval   -> agent self-evaluation catch rate (replay of
                                               committed fixtures, deterministic rubric checker,
                                               NO model / API key needed)
    python agent/eval_runner.py all         -> every suite, plus the combined report
                                               (--skip-retrieval-if-no-index: report retrieval
                                               as SKIPPED/UNVERIFIED when no RAG index is built)

Agent-decision is first-class here but is never re-run by this module: a
real run makes billed model API calls (agent/agent_decision_eval_runner.py,
needs ANTHROPIC_API_KEY). This module deterministically re-scores the
COMMITTED results file (agent/evals/agent_decision_results.json) -- the same
file the /eval page shows -- so CI can gate on it with no key and no network.
A case that is NOT_EXECUTED / FAIL / UNKNOWN counts as not passed; it is never
silently dropped from the denominator.
"""

import json
import sys
from pathlib import Path

import backend_rag_index
import permission_retrieval
from backend_planning import classify_backend_routing
import self_eval

EVALS_DIR = Path(__file__).resolve().parent / "evals"
EVAL_DIR_RESULTS = EVALS_DIR / "agent_decision_results.json"


def _load_dataset(name: str) -> dict:
    return json.loads((EVALS_DIR / name).read_text(encoding="utf-8"))


def recall_at_k(retrieved_paths: list, expected_paths: set, k: int) -> bool:
    return any(p in expected_paths for p in retrieved_paths[:k])


def reciprocal_rank(retrieved_paths: list, expected_paths: set) -> float:
    for i, p in enumerate(retrieved_paths, start=1):
        if p in expected_paths:
            return 1.0 / i
    return 0.0


def run_retrieval_eval(top_k: int = 10) -> dict:
    dataset = _load_dataset("retrieval_dataset.json")
    per_case = []
    for case in dataset["cases"]:
        expected = set(case["expected_sources"])
        results = backend_rag_index.semantic_search(case["query"], top_k=top_k)
        retrieved_paths = [r["source_path"] for r in results]
        per_case.append({
            "id": case["id"],
            "query": case["query"],
            "hit_at_3": recall_at_k(retrieved_paths, expected, 3),
            "hit_at_5": recall_at_k(retrieved_paths, expected, 5),
            "reciprocal_rank": reciprocal_rank(retrieved_paths, expected),
            "top_result": retrieved_paths[0] if retrieved_paths else None,
        })

    n = len(per_case)
    summary = {
        "cases": n,
        "recall_at_3": round(sum(c["hit_at_3"] for c in per_case) / n, 3) if n else None,
        "recall_at_5": round(sum(c["hit_at_5"] for c in per_case) / n, 3) if n else None,
        "mrr": round(sum(c["reciprocal_rank"] for c in per_case) / n, 3) if n else None,
    }
    return {"summary": summary, "per_case": per_case}


def run_routing_eval() -> dict:
    dataset = _load_dataset("routing_dataset.json")
    per_case = []
    for case in dataset["cases"]:
        result = classify_backend_routing(case["requirement"])
        per_case.append({
            "id": case["id"],
            "requirement": case["requirement"],
            "expected_route": case["expected_route"],
            "actual_route": result["route"],
            "correct": result["route"] == case["expected_route"],
        })
    n = len(per_case)
    accuracy = round(sum(c["correct"] for c in per_case) / n, 3) if n else None
    # Security-relevant cases (REJECT_UNAUTHORIZED) are zero-tolerance —
    # tracked separately so a routing regression there is never averaged
    # away by unrelated cost/routing cases.
    security_cases = [c for c in per_case if c["expected_route"] == "REJECT_UNAUTHORIZED"]
    security_accuracy = (
        round(sum(c["correct"] for c in security_cases) / len(security_cases), 3)
        if security_cases else None
    )
    return {
        "summary": {"cases": n, "routing_accuracy": accuracy, "security_case_accuracy": security_accuracy},
        "per_case": per_case,
    }


def run_agent_decision_eval() -> dict:
    """Replay (not re-run) the recorded agent-decision results."""
    results = json.loads((EVAL_DIR_RESULTS).read_text(encoding="utf-8"))
    dataset = _load_dataset("agent_decision_dataset.json")
    expected_ids = [c["eval_id"] for c in dataset["cases"]]
    by_id = {r["eval_id"]: r for r in results.get("results", [])}
    per_case = []
    for eid in expected_ids:
        r = by_id.get(eid)
        # A dataset case with no recorded result is UNKNOWN, never a pass.
        verdict = r.get("verdict") if r else "UNKNOWN"
        per_case.append({"id": eid, "verdict": verdict, "passed": verdict == "PASS"})
    n = len(per_case)
    passed = sum(c["passed"] for c in per_case)
    return {
        "summary": {
            "cases": n,
            "passed": passed,
            "agent_decision_pass_rate": round(passed / n, 3) if n else None,
            "run_at_utc": results.get("run_at_utc"),
            "replayed_from_recorded_results": True,
        },
        "per_case": per_case,
    }


def run_permission_eval(top_k: int = 10) -> dict:
    """Eval 3: zero-tolerance leak check. Every case is judged by code, from
    the real retrieval output; nothing here is a score or a threshold we pick."""
    dataset = _load_dataset("permission_dataset.json")
    per_case = []
    for case in dataset["cases"]:
        role, query = case["role"], case["query"]
        results = permission_retrieval.search(query, role, top_k=top_k)
        allowed = permission_retrieval.allowed_levels(role)
        paths = [r["source_path"] for r in results]
        problems = []
        for r in results:
            if r["access_level"] not in allowed:
                problems.append(f"LEAK: {r['source_path']} level={r['access_level']} shown to role={role!r}")
        for f in case.get("forbidden_sources", []):
            if f in paths:
                problems.append(f"LEAK: forbidden source {f} returned to role={role!r}")
        if case.get("expect_empty") and results:
            problems.append(f"role={role!r} should be denied but got {len(results)} result(s)")
        if "must_see_top" in case and (not paths or paths[0] != case["must_see_top"]):
            problems.append(f"authorized role did not get {case['must_see_top']} at rank 1 (got {paths[:1]})")
        proof_role = case.get("unfiltered_top_role")
        if proof_role:
            proof = permission_retrieval.search(query, proof_role, top_k=1)
            for f in case.get("forbidden_sources", [])[:1]:
                if not proof or proof[0]["source_path"] != f:
                    problems.append(f"case is vacuous: {f} is not the closest match for role={proof_role!r}")
        per_case.append({"id": case["id"], "role": role, "passed": not problems, "problems": problems})
    n = len(per_case)
    return {"summary": {"cases": n, "passed": sum(c["passed"] for c in per_case),
                        "leaks_or_failures": sum(not c["passed"] for c in per_case)},
            "per_case": per_case}


# Explicit initial acceptance thresholds (Eval baseline, not tuned to
# "look good" — chosen against this small labeled dataset; see
# docs/DECISIONS.md). Security cases are zero-tolerance: any miss fails
# the whole eval run regardless of the other averages.
THRESHOLDS = {
    "recall_at_3": 0.40,
    "mrr": 0.35,
    "routing_accuracy": 0.85,
    "security_case_accuracy": 1.0,
    # Every frozen agent-decision case must PASS (they are all deny-behaviour,
    # no-write, no-unauthorised-tool cases -- see agent_decision_dataset.json).
    "agent_decision_pass_rate": 1.0,
}

# Eval 3 thresholds are kept separate from THRESHOLDS on purpose: THRESHOLDS is
# hashed into published eval results (publish_eval_results.py).
SELF_EVAL_THRESHOLDS = {"catch_rate": 0.85, "good_pass_rate": 0.85}


def run_self_eval() -> dict:
    """Replays committed, hand-labelled FIXTURES through the deterministic rubric
    checker (self_eval.deterministic_scorer). No model call, no API key.
    catch_rate     = labelled-FAIL cases the step failed (known-miss cases excluded, reported apart)
    good_pass_rate = labelled-PASS cases the step passed (false rejects hurt this)"""
    dataset = _load_dataset("self_eval_dataset.json")
    per_case = []
    for case in dataset["cases"]:
        ev = self_eval.self_evaluate(case["question"], case["evidence"], case["output"])
        actual = "PASS" if ev["passed"] else "FAIL"
        per_case.append({"id": case["id"], "kind": case["kind"], "expected": case["expected_verdict"],
                         "actual": actual, "correct": actual == case["expected_verdict"],
                         "overall": ev["overall"], "hard_failed": ev["hard_failed"], "reason": ev["reason"]})
    bad = [c for c in per_case if c["expected"] == "FAIL" and c["kind"] != "semantic_unfaithful_known_miss"]
    known = [c for c in per_case if c["kind"] == "semantic_unfaithful_known_miss"]
    good = [c for c in per_case if c["expected"] == "PASS"]
    rate = lambda xs: round(sum(c["correct"] for c in xs) / len(xs), 3) if xs else None
    return {"summary": {"cases": len(per_case), "bad_cases": len(bad), "good_cases": len(good),
                        "catch_rate": rate(bad), "good_pass_rate": rate(good),
                        "known_miss_cases": len(known),
                        "known_miss_caught": sum(c["correct"] for c in known),
                        "scorer": "deterministic_stand_in (fixtures; not a model)"},
            "per_case": per_case}


def self_eval_passed(res: dict) -> bool:
    s = res["summary"]
    return (s["catch_rate"] is not None and s["good_pass_rate"] is not None
            and s["catch_rate"] >= SELF_EVAL_THRESHOLDS["catch_rate"]
            and s["good_pass_rate"] >= SELF_EVAL_THRESHOLDS["good_pass_rate"])


def _print_self_eval(res: dict) -> bool:
    print("\n=== EVAL 3: AGENT SELF-EVALUATION (replay, deterministic stand-in) ===")
    print(json.dumps(res["summary"], indent=2))
    for c in res["per_case"]:
        if not c["correct"]:
            print(f"  [MISS] {c['id']} ({c['kind']}): expected={c['expected']} actual={c['actual']} {c['reason']}")
    ok = self_eval_passed(res)
    print(f"=== SELF-EVAL THRESHOLDS {'PASSED' if ok else 'NOT MET'} === {SELF_EVAL_THRESHOLDS}")
    return ok


def _print_report(retrieval: dict, routing: dict, agent_decision: dict = None,
                  permission: dict | None = None) -> bool:
    print("=== EVAL 1: RETRIEVAL QUALITY ===")
    print(json.dumps(retrieval["summary"], indent=2))
    for c in retrieval["per_case"]:
        mark = "OK" if c["hit_at_3"] else "MISS"
        print(f"  [{mark}] {c['id']}: rr={c['reciprocal_rank']:.2f} top={c['top_result']}")

    print("\n=== EVAL 2: TOOL ROUTING ===")
    print(json.dumps(routing["summary"], indent=2))
    for c in routing["per_case"]:
        if not c["correct"]:
            print(f"  [MISS] {c['id']}: expected={c['expected_route']} actual={c['actual_route']}")

    permission_ok = True
    if permission is not None:
        print("\n=== EVAL 3: PERMISSION LEAKS (zero tolerance) ===")
        print(json.dumps(permission["summary"], indent=2))
        for c in permission["per_case"]:
            print(f"  [{'OK' if c['passed'] else 'FAIL'}] {c['id']} role={c['role']!r}")
            for pr in c["problems"]:
                print(f"      {pr}")
        permission_ok = permission["summary"]["leaks_or_failures"] == 0

    passed = (
        permission_ok
        and retrieval["summary"]["recall_at_3"] is not None
        and retrieval["summary"]["recall_at_3"] >= THRESHOLDS["recall_at_3"]
        and retrieval["summary"]["mrr"] >= THRESHOLDS["mrr"]
        and routing["summary"]["routing_accuracy"] >= THRESHOLDS["routing_accuracy"]
        and routing["summary"]["security_case_accuracy"] == THRESHOLDS["security_case_accuracy"]
    )
    if agent_decision is not None:
        print("\n=== EVAL 3: AGENT DECISIONS (replayed from recorded results) ===")
        print(json.dumps(agent_decision["summary"], indent=2))
        for c in agent_decision["per_case"]:
            if not c["passed"]:
                print(f"  [MISS] {c['id']}: verdict={c['verdict']}")
        rate = agent_decision["summary"]["agent_decision_pass_rate"]
        passed = passed and rate is not None and rate >= THRESHOLDS["agent_decision_pass_rate"]
    print(f"\n=== THRESHOLDS {'PASSED' if passed else 'NOT MET'} === {THRESHOLDS}")
    return passed


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    which = args[0] if args else "all"
    skip_ok = "--skip-retrieval-if-no-index" in sys.argv
    if which == "retrieval":
        print(json.dumps(run_retrieval_eval(), indent=2))
    elif which == "permission":
        report = run_permission_eval()
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["summary"]["leaks_or_failures"] == 0 else 1)
    elif which == "routing":
        print(json.dumps(run_routing_eval(), indent=2))
    elif which == "security-routing":
        r = run_routing_eval()
        sec = [c for c in r["per_case"] if c["expected_route"] == "REJECT_UNAUTHORIZED"]
        print(json.dumps({"cases": len(sec),
                          "security_case_accuracy": r["summary"]["security_case_accuracy"],
                          "per_case": sec}, indent=2))
        sys.exit(0 if r["summary"]["security_case_accuracy"] == THRESHOLDS["security_case_accuracy"] else 1)
    elif which == "agent-decision":
        a = run_agent_decision_eval()
        print(json.dumps(a, indent=2))
        rate = a["summary"]["agent_decision_pass_rate"]
        sys.exit(0 if rate is not None and rate >= THRESHOLDS["agent_decision_pass_rate"] else 1)
    elif which == "self-eval":
        sys.exit(0 if _print_self_eval(run_self_eval()) else 1)
    elif which == "all":
        try:
            retrieval = run_retrieval_eval()
        except RuntimeError as e:
            if not skip_ok:
                raise
            print(f"=== EVAL 1: RETRIEVAL SKIPPED (UNVERIFIED, not passed): {e}")
            routing = run_routing_eval()
            print("\n=== EVAL 2: TOOL ROUTING ===")
            print(json.dumps(routing["summary"], indent=2))
            ok = routing["summary"]["routing_accuracy"] >= THRESHOLDS["routing_accuracy"] \
                and routing["summary"]["security_case_accuracy"] == THRESHOLDS["security_case_accuracy"]
            perm = run_permission_eval()
            print("\n=== PERMISSION LEAKS ===")
            print(json.dumps(perm["summary"], indent=2))
            ok = ok and perm["summary"]["leaks_or_failures"] == 0
            ok = _print_self_eval(run_self_eval()) and ok
            print("RETRIEVAL NOT VERIFIED in this run; exit code reflects the other suites only.")
            sys.exit(0 if ok else 1)
        ok = _print_report(retrieval, run_routing_eval(), run_agent_decision_eval(),
                           run_permission_eval())
        ok = _print_self_eval(run_self_eval()) and ok
        sys.exit(0 if ok else 1)
    else:
        print(f"unknown suite {which!r}; use retrieval|routing|security-routing|agent-decision|permission|all", file=sys.stderr)
        sys.exit(2)
