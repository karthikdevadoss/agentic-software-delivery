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

Schema 2 adds, on top of the unchanged v1 fields:
  suites[]          one first-class card per suite (retrieval, routing,
                    security-routing, agent-decision): score, threshold,
                    pass/fail, dataset hash, commit hash, run time
  reproducibility   the exact command + a hash of the inputs that produced
                    the numbers (runner + datasets + thresholds)
and every publish also appends one record to agent/web/eval-history/
(<UTC timestamp>-<commit7>.json) and rebuilds eval-history/index.json, which
the page loads for the history table and trend lines. History can be seeded,
once, from the REAL git history of the committed results files:
    python publish_eval_results.py --seed-history
Nothing in history is ever computed or estimated: a field that cannot be read
from a real committed artifact is null and the page says "n/a".
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import eval_runner

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
OUTPUT_PATH = AGENT_DIR / "web" / "eval-results.json"
HISTORY_DIR = AGENT_DIR / "web" / "eval-history"
HISTORY_INDEX = HISTORY_DIR / "index.json"

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


AGENT_DECISION_KEY = "agent_decision_pass_rate"

# suite key -> (label, primary metric key, other metrics shown on the card,
# dataset file that defines it). security-routing is the REJECT_UNAUTHORIZED
# subset of the routing dataset, so it shares that dataset's hash.
SUITE_SPECS = [
    ("retrieval", "Retrieval", "recall_at_3", ["mrr"], "agent/evals/retrieval_dataset.json"),
    ("routing", "Tool routing", "routing_accuracy", [], "agent/evals/routing_dataset.json"),
    ("security-routing", "Security routing (zero tolerance)", "security_case_accuracy", [],
     "agent/evals/routing_dataset.json"),
    ("agent-decision", "Agent decisions", AGENT_DECISION_KEY, [], "agent/evals/agent_decision_dataset.json"),
]


def metric_passes(score, threshold, comparator: str) -> bool:
    if score is None:
        return False
    if comparator == ">=":
        return score >= threshold
    if comparator == "==":
        return score == threshold
    raise ValueError(f"unknown comparator: {comparator}")


def _dataset_hash(eval_inputs, rel):
    return ((eval_inputs or {}).get("files") or {}).get(rel)


def build_suites(metrics, labelled, eval_inputs, commit_sha, generated_at, agent_decision):
    """Pure: one record per suite, derived ONLY from the already-computed
    metrics list + recorded facts. Used for live publishes and, with the
    metrics of an older snapshot, for history seeding. A suite whose metric is
    absent (e.g. agent-decision in a snapshot that predates its threshold) has
    threshold/passed = None, never a guess."""
    by_key = {m["key"]: m for m in metrics}
    cases = {"retrieval": labelled.get("retrieval_cases"), "routing": labelled.get("routing_cases"),
             "security-routing": labelled.get("security_routing_cases"),
             "agent-decision": agent_decision["cases_total"] if agent_decision else None}
    suites = []
    for key, label, primary, others, dataset in SUITE_SPECS:
        if key == "agent-decision":
            if agent_decision is None:
                continue
            total = agent_decision["cases_total"]
            m = by_key.get(primary) or {
                "score": round(agent_decision["summary"]["PASS"] / total, 3) if total else None,
                "threshold": None, "comparator": ">=", "passed": None}
            run_at, run_commit, kind = (agent_decision.get("run_at_utc") or None,
                                        agent_decision.get("recorded_commit"), "recorded")
        else:
            m = by_key.get(primary)
            if m is None:
                continue
            run_at, run_commit, kind = generated_at, commit_sha, "measured"
        suite_metrics = [{"key": k, "score": by_key[k]["score"], "threshold": by_key[k]["threshold"],
                          "comparator": by_key[k]["comparator"], "passed": by_key[k]["passed"]}
                         for k in [primary] + others if k in by_key]
        if not suite_metrics:
            suite_metrics = [{"key": primary, "score": m["score"], "threshold": m["threshold"],
                              "comparator": m["comparator"], "passed": m["passed"]}]
        passes = [x["passed"] for x in suite_metrics]
        suites.append({
            "key": key,
            "label": label,
            "kind": kind,  # measured = this publish ran it; recorded = replayed from committed results
            "cases": cases[key],
            "primary_metric": primary,
            "score": m["score"],
            "threshold": m["threshold"],
            "comparator": m["comparator"],
            "passed": None if any(p is None for p in passes) else all(passes),
            "metrics": suite_metrics,
            "dataset_file": dataset,
            "dataset_hash": _dataset_hash(eval_inputs, dataset),
            "commit_sha": run_commit,
            "run_at": run_at,
        })
    return suites


def build_reproducibility(eval_inputs):
    """The command, and a single hash over exactly the inputs hashed in
    eval_inputs (runner + datasets + recorded agent-decision results +
    thresholds). Same bytes in, same hash out; None when inputs are unknown."""
    base = {
        "command": "python eval_runner.py all",
        "working_directory": "agent",
        "setup": ["pip install -r requirements.txt", "python backend_rag_index.py"],
        "single_suite_commands": [
            "python eval_runner.py retrieval", "python eval_runner.py routing",
            "python eval_runner.py security-routing", "python eval_runner.py agent-decision"],
        "agent_decision_note": "agent-decision is replayed from the committed recorded results "
                               "(no API key, no network); re-recording it needs agent_decision_eval_runner.py "
                               "and a billed ANTHROPIC_API_KEY.",
    }
    if not eval_inputs:
        return dict(base, inputs_hash=None, hash_covers=[])
    return dict(base, inputs_hash=inputs_hash(eval_inputs),
                hash_covers=sorted(eval_inputs["files"]) + ["eval_runner.THRESHOLDS"])


def inputs_hash(eval_inputs):
    """sha256 over the canonical JSON of {files, thresholds} hashes."""
    canon = json.dumps({"files": eval_inputs["files"], "thresholds": eval_inputs["thresholds"]},
                       sort_keys=True)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def build_eval_results(retrieval: dict, routing: dict, *, commit_sha: str,
                       generated_at: str, embedding_model: str,
                       working_tree_dirty: bool = False,
                       thresholds: dict = None,
                       ci_observation: dict = None,
                       eval_inputs: dict = None,
                       agent_decision: dict = None) -> dict:
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

    if agent_decision is not None:
        total = agent_decision["cases_total"]
        ad_score = round(agent_decision["summary"]["PASS"] / total, 3) if total else None
        metrics.append({
            "key": AGENT_DECISION_KEY,
            "label": "Agent-decision pass rate (recorded results, zero tolerance)",
            "eval": "agent_decision",
            "score": ad_score,
            "threshold": thresholds[AGENT_DECISION_KEY],
            "comparator": ">=",
            "passed": metric_passes(ad_score, thresholds[AGENT_DECISION_KEY], ">="),
        })

    labelled = {
        "retrieval_cases": retrieval["summary"]["cases"],
        "routing_cases": routing["summary"]["cases"],
        "security_routing_cases": sum(
            1 for c in routing["per_case"] if c["expected_route"] == "REJECT_UNAUTHORIZED"),
    }
    suites = build_suites(metrics, labelled, eval_inputs, commit_sha, generated_at, agent_decision)

    return {
        "schema_version": 2,
        "generated_at": generated_at,
        "commit_sha": commit_sha,
        "working_tree_dirty": working_tree_dirty,
        "embedding_model": embedding_model,
        "overall_passed": all(m["passed"] for m in metrics),
        # Content hashes of what produced these numbers; see
        # test_eval_results_fresh.py. None only in synthetic unit tests.
        "eval_inputs": (
            dict(eval_inputs, not_covered=EVAL_INPUTS_NOT_COVERED) if eval_inputs else None),
        "labelled_set": labelled,
        "suites": suites,
        "reproducibility": build_reproducibility(eval_inputs),
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
        "agent_decision": agent_decision,
        "ci_gate": {
            "workflow": ".github/workflows/ci.yml",
            "step": EVAL_STEP_NAME,
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
    # Agent-decision eval: shown from the COMMITTED results (re-running needs a
    # paid model API key), so the recorded results file is itself the input.
    "agent/evals/agent_decision_dataset.json",
    "agent/evals/agent_decision_results.json",
]
AGENT_DECISION_RESULTS = "agent/evals/agent_decision_results.json"
AGENT_DECISION_DATASET = "agent/evals/agent_decision_dataset.json"
# Stated honestly in the JSON: things that also affect the scores but are NOT
# hashed, because they change for unrelated reasons (the curated corpus pulls
# in living docs such as docs/ACTION_QUEUE.json) or are not in the repo.
EVAL_INPUTS_NOT_COVERED = [
    "curated corpus document contents (agent/backend_rag_corpus.py and the files it lists)",
    "retrieval/routing implementation (agent/backend_rag_index.py, agent/backend_planning.py)",
    "embedding model weights (recorded by name in embedding_model)",
]


def _sha256_text(text: str) -> str:
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


EVAL_STEP_NAME = "RAG/MCP retrieval + routing + agent-decision evals (must meet recorded thresholds)"
# Runs recorded before the agent-decision suite joined the gate used the old
# step name; keep matching it so the CI observation still finds them.
EVAL_STEP_NAMES = (EVAL_STEP_NAME, "RAG/MCP retrieval + routing evals (must meet recorded thresholds)")
GH_REPO = "karthikdevadoss/agentic-software-delivery"


def build_agent_decision_section(results: dict, dataset: dict, recorded_commit: str) -> dict:
    """Pure: the committed agent-decision eval results, as recorded. Nothing
    is re-run or re-scored. Deliberately omits evidence_reference (a local
    machine path) and the free-text expected/actual decision lists."""
    names = {c["eval_id"]: c.get("name") for c in dataset.get("cases", [])}
    cases = []
    for r in results.get("results", []):
        cases.append({
            "id": r["eval_id"],
            "name": names.get(r["eval_id"]),
            "ticket": r.get("ticket"),
            "verdict": r.get("verdict"),
            "reason": r.get("reason"),
            # The recorded file stores the full call list (inputs + result
            # excerpts); publish only the count and the tool names.
            "tool_calls": len(r["tool_calls"]) if isinstance(r.get("tool_calls"), list) else r.get("tool_calls"),
            "tools_used": sorted({c.get("name") for c in r["tool_calls"] if isinstance(c, dict)})
                          if isinstance(r.get("tool_calls"), list) else [],
            "write_occurred": r.get("write_occurred"),
            "approval_present": r.get("approval_present"),
            "unsafe_action_attempted": r.get("unsafe_action_attempted"),
        })
    verdicts = [c["verdict"] for c in cases]
    run_at = results.get("run_at_utc") or ""
    return {
        "label": f"recorded {run_at[:10]}" if run_at else "recorded (date unknown)",
        "run_at_utc": run_at,
        "recorded_commit": recorded_commit,
        "model": results["results"][0].get("model") if results.get("results") else None,
        "scoring_authority": "deterministic: real dispatch trace + before/after file hashes; never an LLM judge",
        "summary": {v: verdicts.count(v) for v in ("PASS", "FAIL", "NOT_EXECUTED", "UNKNOWN")},
        "cases_total": len(cases),
        "approval_gate_exercised_cases": sum(1 for c in cases if c["approval_present"]),
        "writes_occurred": sum(1 for c in cases if c["write_occurred"]),
        "why_not_rerun": "re-running makes real, billed model API calls; no API key in the publishing environment",
        "cases": cases,
        "source": f"{REPO_URL}/blob/master/{AGENT_DECISION_RESULTS}",
        "runner": f"{REPO_URL}/blob/master/agent/agent_decision_eval_runner.py",
    }


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
                if any(st["name"] in EVAL_STEP_NAMES for st in steps):
                    conclusion = next(st["conclusion"] for st in steps if st["name"] in EVAL_STEP_NAMES)
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


def history_entry(d: dict, source: str = None) -> dict:
    """Pure: the slim history record for one published snapshot (v1 or v2).
    Everything is read from the snapshot itself; v1 snapshots simply have
    fewer hashes and null for what they never recorded."""
    suites = d.get("suites")
    if suites is None:  # schema 1: derive from the recorded metrics only
        suites = build_suites(d["metrics"], d["labelled_set"], d.get("eval_inputs"),
                              d["commit_sha"], d["generated_at"], d.get("agent_decision"))
    return {
        "schema_version": 1,
        "generated_at": d["generated_at"],
        "commit_sha": d["commit_sha"],
        "working_tree_dirty": d.get("working_tree_dirty"),
        "embedding_model": d.get("embedding_model"),
        "overall_passed": d.get("overall_passed"),
        "reproducibility_hash": (inputs_hash(d["eval_inputs"]) if d.get("eval_inputs") else None),
        "source": source or "publish_eval_results.py",
        "suites": [
            {k: s[k] for k in ("key", "kind", "score", "threshold", "comparator", "passed",
                                "dataset_hash", "commit_sha", "run_at", "cases")}
            | {"metrics": {m["key"]: m["score"] for m in s["metrics"]}}
            for s in suites],
    }


def history_filename(entry: dict) -> str:
    ts = entry["generated_at"].replace("-", "").replace(":", "")
    ts = ts.split(".")[0].rstrip("Z").split("+")[0] + "Z"
    return f"{ts}-{entry['commit_sha'][:7]}.json"


def agent_decision_history_entry(results: dict, dataset_text, commit: str) -> dict:
    """Pure: history record for one committed agent-decision results file
    (an agent-decision-only run -- no retrieval/routing was measured then).
    Threshold/pass are null: no threshold existed when it was recorded."""
    verdicts = [r.get("verdict") for r in results.get("results", [])]
    n = len(verdicts)
    return {
        "schema_version": 1,
        "generated_at": results["run_at_utc"],
        "commit_sha": commit,
        "working_tree_dirty": None,
        "embedding_model": None,
        "overall_passed": None,
        "reproducibility_hash": None,
        "source": f"git:{commit[:7]}:{AGENT_DECISION_RESULTS}",
        "suites": [{
            "key": "agent-decision", "kind": "recorded", "cases": n,
            "score": round(verdicts.count("PASS") / n, 3) if n else None,
            "threshold": None, "comparator": ">=", "passed": None,
            "dataset_hash": _sha256_text(dataset_text.replace("\r\n", "\n")) if dataset_text else None,
            "commit_sha": commit, "run_at": results["run_at_utc"],
            "metrics": {AGENT_DECISION_KEY: round(verdicts.count("PASS") / n, 3) if n else None},
            "verdict_counts": {v: verdicts.count(v) for v in sorted(set(verdicts))},
        }],
    }


def write_history_entry(entry: dict, history_dir: Path = None) -> Path:
    history_dir = HISTORY_DIR if history_dir is None else history_dir
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / history_filename(entry)
    path.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    return path


def rebuild_history_index(history_dir: Path = None) -> dict:
    """index.json = every history file, oldest first, so the static page needs
    one fetch. The per-run files stay the canonical records."""
    history_dir = HISTORY_DIR if history_dir is None else history_dir
    entries = []
    for f in sorted(history_dir.glob("*.json")):
        if f.name == "index.json":
            continue
        entries.append(dict(json.loads(f.read_text(encoding="utf-8")), file=f.name))
    entries.sort(key=lambda e: (e["generated_at"], e["file"]))
    index = {"schema_version": 1, "entries": entries}
    (history_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return index


def _git_show(rev: str, rel: str):
    try:
        return _git("show", f"{rev}:{rel}")
    except subprocess.CalledProcessError:
        return None


def seed_history_from_git(history_dir: Path = None) -> list:
    """Seed history ONLY from real committed artifacts: every committed
    version of web/eval-results.json, plus every committed version of
    evals/agent_decision_results.json (agent-decision-only runs). Idempotent:
    a record whose file already exists is left untouched."""
    history_dir = HISTORY_DIR if history_dir is None else history_dir
    written = []
    snap_rel = OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()
    for commit in _git("log", "--reverse", "--format=%H", "--", snap_rel).splitlines():
        text = _git_show(commit, snap_rel)
        if text is None:
            continue
        entry = history_entry(json.loads(text), source=f"git:{commit[:7]}:{snap_rel}")
        path = history_dir / history_filename(entry)
        if not path.exists():
            written.append(write_history_entry(entry, history_dir))
    for commit in _git("log", "--reverse", "--format=%H", "--", AGENT_DECISION_RESULTS).splitlines():
        text = _git_show(commit, AGENT_DECISION_RESULTS)
        if text is None:
            continue
        results = json.loads(text)
        if not results.get("run_at_utc"):
            continue
        entry = agent_decision_history_entry(
            results, _git_show(commit, AGENT_DECISION_DATASET), commit)
        path = history_dir / history_filename(entry)
        if not path.exists():
            written.append(write_history_entry(entry, history_dir))
    rebuild_history_index(history_dir)
    return written


def main(argv: list) -> int:
    if "--seed-history" in argv:
        written = seed_history_from_git()
        print(f"seeded {len(written)} history record(s) from git into "
              f"{HISTORY_DIR.relative_to(REPO_ROOT)}")
        return 0
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
        agent_decision=build_agent_decision_section(
            json.loads((REPO_ROOT / AGENT_DECISION_RESULTS).read_text(encoding="utf-8")),
            json.loads((REPO_ROOT / AGENT_DECISION_DATASET).read_text(encoding="utf-8")),
            _git("log", "-1", "--format=%H", "--", AGENT_DECISION_RESULTS)),
    )
    text = json.dumps(results, indent=2) + "\n"
    if "--stdout" in argv:
        print(text, end="")
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {OUTPUT_PATH.relative_to(REPO_ROOT)} "
              f"(overall_passed={results['overall_passed']}, commit={results['commit_sha'][:7]})")
        if "--no-history" not in argv:
            path = write_history_entry(history_entry(results))
            rebuild_history_index()
            print(f"history: {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
