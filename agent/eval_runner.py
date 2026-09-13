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
    python agent/eval_runner.py all         -> both, plus the combined report
"""

import json
import sys
from pathlib import Path

import backend_rag_index
from backend_planning import classify_backend_routing

EVALS_DIR = Path(__file__).resolve().parent / "evals"


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


# Explicit initial acceptance thresholds (Eval baseline, not tuned to
# "look good" — chosen against this small labeled dataset; see
# docs/DECISIONS.md). Security cases are zero-tolerance: any miss fails
# the whole eval run regardless of the other averages.
THRESHOLDS = {
    "recall_at_3": 0.40,
    "mrr": 0.35,
    "routing_accuracy": 0.85,
    "security_case_accuracy": 1.0,
}


def _print_report(retrieval: dict, routing: dict) -> bool:
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

    passed = (
        retrieval["summary"]["recall_at_3"] is not None
        and retrieval["summary"]["recall_at_3"] >= THRESHOLDS["recall_at_3"]
        and retrieval["summary"]["mrr"] >= THRESHOLDS["mrr"]
        and routing["summary"]["routing_accuracy"] >= THRESHOLDS["routing_accuracy"]
        and routing["summary"]["security_case_accuracy"] == THRESHOLDS["security_case_accuracy"]
    )
    print(f"\n=== THRESHOLDS {'PASSED' if passed else 'NOT MET'} === {THRESHOLDS}")
    return passed


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which == "retrieval":
        print(json.dumps(run_retrieval_eval(), indent=2))
    elif which == "routing":
        print(json.dumps(run_routing_eval(), indent=2))
    else:
        ok = _print_report(run_retrieval_eval(), run_routing_eval())
        sys.exit(0 if ok else 1)
