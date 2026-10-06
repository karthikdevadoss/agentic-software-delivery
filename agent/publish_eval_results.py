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
    python publish_eval_results.py --no-ci    # skip the GitHub Actions lookup

It also records what CI actually did with the eval step on master (via the
gh CLI, read-only): the latest run's eval-step conclusion and when the step
last passed. If gh is unavailable that field is null, never guessed.
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
                       thresholds: dict = None,
                       ci_observation: dict = None,
                       eval_inputs: dict = None) -> dict:
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
        # Content hashes of what produced these numbers; see
        # test_eval_results_fresh.py. None only in synthetic unit tests.
        "eval_inputs": (
            dict(eval_inputs, not_covered=EVAL_INPUTS_NOT_COVERED) if eval_inputs else None),
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
            # What CI actually did, captured from the GitHub Actions API at
            # publish time; None = not captured (gh unavailable).
            "observed": ci_observation,
        },
        "sources": {
            "eval_runner": f"{REPO_URL}/blob/master/agent/eval_runner.py",
            "retrieval_dataset": f"{REPO_URL}/blob/master/agent/evals/retrieval_dataset.json",
            "routing_dataset": f"{REPO_URL}/blob/master/agent/evals/routing_dataset.json",
            "ci_workflow": f"{REPO_URL}/blob/master/.github/workflows/ci.yml",
            "publisher": f"{REPO_URL}/blob/master/agent/publish_eval_results.py",
        },
    }


# Staleness check inputs (retro action 2026-10-06, item 3). The published
# numbers are only valid for these exact inputs; agent/test_eval_results_fresh.py
# fails CI when any of them changes without the JSON being regenerated.
EVAL_INPUT_FILES = [
    "agent/eval_runner.py",
    "agent/evals/retrieval_dataset.json",
    "agent/evals/routing_dataset.json",
]
# Stated honestly in the JSON: things that also affect the scores but are NOT
# hashed, because they change for unrelated reasons (the curated corpus pulls
# in living docs such as docs/ACTION_QUEUE.json) or are not in the repo.
EVAL_INPUTS_NOT_COVERED = [
    "curated corpus document contents (agent/backend_rag_corpus.py and the files it lists)",
    "retrieval/routing implementation (agent/backend_rag_index.py, agent/backend_planning.py)",
    "embedding model weights (recorded by name in embedding_model)",
]


def _sha256_text(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_eval_input_hashes(repo_root: Path = None, thresholds: dict = None) -> dict:
    """sha256 of each eval input file and of the THRESHOLDS dict as canonical
    JSON. Files are read in text mode and CRLF is normalised to LF, so a
    Windows checkout with core.autocrlf hashes the same as Linux CI."""
    repo_root = REPO_ROOT if repo_root is None else repo_root
    thresholds = eval_runner.THRESHOLDS if thresholds is None else thresholds
    files = {}
    for rel in EVAL_INPUT_FILES:
        raw = (repo_root / rel).read_text(encoding="utf-8")
        files[rel] = _sha256_text(raw.replace("\r\n", "\n"))
    return {
        "files": files,
        "thresholds": _sha256_text(json.dumps(thresholds, sort_keys=True)),
    }


EVAL_STEP_NAME = "RAG/MCP retrieval + routing evals (must meet recorded thresholds)"
GH_REPO = "karthikdevadoss/agentic-software-delivery"


def summarise_ci_runs(runs: list, observed_at: str) -> dict:
    """Pure: what CI actually did with the eval step on master.

    `runs` is newest-first; each item is {"created_at", "head_sha",
    "eval_step": conclusion or None, "failed_steps": [names in the same
    job that failed]}. A "skipped" eval step means GitHub did not run it
    because an earlier step in the same job failed (default if: success()),
    so the gate did not execute on that run -- reported, not hidden."""
    if not runs:
        return None
    latest = runs[0]
    skipped_streak = 0
    for r in runs:
        if r["eval_step"] == "success":
            break
        skipped_streak += 1
    last_success = next((r for r in runs if r["eval_step"] == "success"), None)
    return {
        "observed_at": observed_at,
        "branch": "master",
        "latest_run": {
            "created_at": latest["created_at"],
            "head_sha": latest["head_sha"],
            "eval_step": latest["eval_step"],
            "failed_steps_in_same_job": latest.get("failed_steps", []),
        },
        "runs_since_eval_step_last_passed": skipped_streak if last_success else None,
        "last_eval_step_success": (
            {"created_at": last_success["created_at"], "head_sha": last_success["head_sha"]}
            if last_success else None),
        "runs_examined": len(runs),
    }


def fetch_ci_runs(limit: int = 40) -> list:
    """Newest-first master CI runs with the eval step's conclusion, via the
    gh CLI. Stops at the first run where the eval step succeeded. Returns
    None (never raises) when gh is unavailable or unauthenticated -- the page
    then says the CI status was not captured, rather than guessing."""
    try:
        listing = json.loads(subprocess.run(
            ["gh", "run", "list", "-R", GH_REPO, "-b", "master", "-w", "CI",
             "-L", str(limit), "--json", "databaseId,createdAt,headSha"],
            capture_output=True, text=True, check=True, timeout=60).stdout)
        runs = []
        for item in listing:
            jobs = json.loads(subprocess.run(
                ["gh", "run", "view", str(item["databaseId"]), "-R", GH_REPO, "--json", "jobs"],
                capture_output=True, text=True, check=True, timeout=60).stdout)["jobs"]
            conclusion, failed = None, []
            for job in jobs:
                steps = job.get("steps") or []
                if any(st["name"] == EVAL_STEP_NAME for st in steps):
                    conclusion = next(st["conclusion"] for st in steps if st["name"] == EVAL_STEP_NAME)
                    failed = [st["name"] for st in steps if st["conclusion"] == "failure"]
            runs.append({"created_at": item["createdAt"], "head_sha": item["headSha"],
                         "eval_step": conclusion, "failed_steps": failed})
            if conclusion == "success":
                break
        return runs
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None


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
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ci_runs = None if "--no-ci" in argv else fetch_ci_runs()
    results = build_eval_results(
        retrieval, routing,
        commit_sha=_git("rev-parse", "HEAD"),
        generated_at=now,
        embedding_model=model_id(),
        working_tree_dirty=_working_tree_dirty(),
        ci_observation=summarise_ci_runs(ci_runs, now) if ci_runs else None,
        eval_inputs=compute_eval_input_hashes(),
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
