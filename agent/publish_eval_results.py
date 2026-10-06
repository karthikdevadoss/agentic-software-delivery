"""
Publish the RAG retrieval + tool-routing eval results as a static JSON file
the public /eval page renders (agent/web/eval-results.json).

This module MEASURES NOTHING NEW and changes no eval logic. It calls the
existing agent/eval_runner.py functions (run_retrieval_eval,
run_routing_eval) and its THRESHOLDS dict unchanged, then records:
per-metric score, threshold, pass/fail, labelled-set sizes, the commit SHA
the measurement was taken at, the embedding model, and a UTC timestamp.

The pass/fail rule mirrors eval_runner._print_report exactly (>= for the
averages, == for the zero-tolerance security metric); a unit test asserts
the two agree so they cannot drift apart silently.

Run (from agent/, after building the curated index):
    python backend_rag_index.py
    python publish_eval_results.py            # writes web/eval-results.json
    python publish_eval_results.py --stdout   # print only, write nothing
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import eval_runner

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
OUTPUT_PATH = AGENT_DIR / "web" / "eval-results.json"

REPO_URL = "https://github.com/karthikdevadoss/agentic-software-delivery"

# key -> (human label, which eval, comparator). Comparator mirrors
# eval_runner._print_report: averages must be >= threshold, the security
# metric is zero-tolerance (must equal 1.0).
METRIC_SPECS = [
    ("recall_at_3", "Retrieval Recall@3", "retrieval", ">="),
    ("mrr", "Retrieval MRR (mean reciprocal rank)", "retrieval", ">="),
    ("routing_accuracy", "Tool-routing accuracy", "routing", ">="),
    ("security_case_accuracy", "Security-case routing accuracy (zero tolerance)", "routing", "=="),
]


def metric_passes(score, threshold, comparator: str) -> bool:
    if score is None:
        return False
    if comparator == ">=":
        return score >= threshold
    if comparator == "==":
        return score == threshold
    raise ValueError(f"unknown comparator: {comparator}")


def build_eval_results(retrieval: dict, routing: dict, *, commit_sha: str,
                       generated_at: str, embedding_model: str,
                       working_tree_dirty: bool = False,
                       thresholds: dict = None) -> dict:
    """Pure function: eval_runner output in, publishable dict out."""
    thresholds = eval_runner.THRESHOLDS if thresholds is None else thresholds
    summaries = {"retrieval": retrieval["summary"], "routing": routing["summary"]}

    metrics = []
    for key, label, which, comparator in METRIC_SPECS:
        score = summaries[which].get(key)
        threshold = thresholds[key]
        metrics.append({
            "key": key,
            "label": label,
            "eval": which,
            "score": score,
            "threshold": threshold,
            "comparator": comparator,
            "passed": metric_passes(score, threshold, comparator),
        })

    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "commit_sha": commit_sha,
        "working_tree_dirty": working_tree_dirty,
        "embedding_model": embedding_model,
        "overall_passed": all(m["passed"] for m in metrics),
        "labelled_set": {
            "retrieval_cases": retrieval["summary"]["cases"],
            "routing_cases": routing["summary"]["cases"],
            "security_routing_cases": sum(
                1 for c in routing["per_case"] if c["expected_route"] == "REJECT_UNAUTHORIZED"),
        },
        "metrics": metrics,
        "informational": {
            # Reported by eval_runner but not gated by a threshold.
            "recall_at_5": retrieval["summary"].get("recall_at_5"),
        },
        "retrieval_cases": [
            {
                "id": c["id"],
                "query": c["query"],
                "hit_at_3": c["hit_at_3"],
                "reciprocal_rank": round(c["reciprocal_rank"], 3),
                "top_result": c["top_result"],
            }
            for c in retrieval["per_case"]
        ],
        "ci_gate": {
            "workflow": ".github/workflows/ci.yml",
            "step": "RAG/MCP retrieval + routing evals (must meet recorded thresholds)",
            "command": "python eval_runner.py all",
            "behaviour": "exits 1 (fails the build) if any threshold is not met",
            "runs_on": "every pull request to master and every push to master",
        },
        "sources": {
            "eval_runner": f"{REPO_URL}/blob/master/agent/eval_runner.py",
            "retrieval_dataset": f"{REPO_URL}/blob/master/agent/evals/retrieval_dataset.json",
            "routing_dataset": f"{REPO_URL}/blob/master/agent/evals/routing_dataset.json",
            "ci_workflow": f"{REPO_URL}/blob/master/.github/workflows/ci.yml",
            "publisher": f"{REPO_URL}/blob/master/agent/publish_eval_results.py",
        },
    }


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _working_tree_dirty() -> bool:
    """Dirty = uncommitted changes other than the output file itself."""
    out_rel = OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()
    lines = [l for l in _git("status", "--porcelain").splitlines() if l.strip()]
    return any(not l.endswith(out_rel) for l in lines)


def main(argv: list) -> int:
    from embeddings import model_id

    retrieval = eval_runner.run_retrieval_eval()
    routing = eval_runner.run_routing_eval()
    results = build_eval_results(
        retrieval, routing,
        commit_sha=_git("rev-parse", "HEAD"),
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        embedding_model=model_id(),
        working_tree_dirty=_working_tree_dirty(),
    )
    text = json.dumps(results, indent=2) + "\n"
    if "--stdout" in argv:
        print(text, end="")
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} "
              f"(overall_passed={results['overall_passed']}, commit={results['commit_sha'][:7]})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
