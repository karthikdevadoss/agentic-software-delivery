"""
Snapshot of the "Ask the Codebase" example questions, answered by the REAL
feature (agent/ask_codebase.ask) against the locally built curated index,
written to agent/web/ask-codebase-examples.json for the static
/ask-codebase/examples page.

The example questions are read from the live page's own "Try:" buttons
(agent/web/ask-codebase.html), so the snapshot and the page cannot list
different questions. ask_codebase makes zero LLM calls; nothing here is
written by hand -- statuses, scores, sources and excerpts are the feature's
own output.

Run (from agent/, after building the curated index):
    python backend_rag_index.py
    python publish_ask_codebase_examples.py
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from publish_eval_results import _sha256_text

AGENT_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENT_DIR.parent
PAGE = AGENT_DIR / "web" / "ask-codebase.html"
OUTPUT_PATH = AGENT_DIR / "web" / "ask-codebase-examples.json"
REPO_URL = "https://github.com/karthikdevadoss/agentic-software-delivery"

TOP_EVIDENCE = 3
EXCERPT_CHARS = 360

HASHED_FILES = ["agent/ask_codebase.py", "agent/backend_rag_corpus.py"]
INPUTS_NOT_COVERED = [
    "contents of the curated corpus documents (living docs change for unrelated reasons)",
    "the retrieval implementation (agent/backend_rag_index.py) and embedding model weights",
]

_EXAMPLE_RE = re.compile(r'<button[^>]*class="ac-example-btn"[^>]*>(.*?)</button>', re.S)


def extract_examples(html: str) -> list:
    return [unescape(re.sub(r"\s+", " ", m).strip()) for m in _EXAMPLE_RE.findall(html)]


def trim_answer(answer: dict) -> dict:
    """Keep the feature's own status/message and its top evidence items,
    with excerpts shortened for display. No field is invented."""
    evidence = []
    for e in answer.get("evidence", [])[:TOP_EVIDENCE]:
        excerpt = (e.get("excerpt") or "").strip()
        evidence.append({
            "rank": e["rank"],
            "score": e["score"],
            "source_path": e["source_path"],
            "symbol": e.get("symbol"),
            "start_line": e.get("start_line"),
            "end_line": e.get("end_line"),
            "source_url": e["source_url"],
            "excerpt": excerpt[:EXCERPT_CHARS] + ("…" if len(excerpt) > EXCERPT_CHARS else ""),
        })
    return {"query": answer.get("query"), "status": answer.get("status"),
            "message": answer.get("message"), "evidence": evidence,
            "evidence_returned": len(answer.get("evidence", []))}


def compute_input_hashes(examples: list, repo_root: Path = REPO_ROOT) -> dict:
    files = {rel: _sha256_text((repo_root / rel).read_text(encoding="utf-8").replace("\r\n", "\n"))
             for rel in HASHED_FILES}
    return {"files": files, "examples": _sha256_text(json.dumps(examples))}


def build_snapshot(examples: list, answers: list, *, commit_sha: str, generated_at: str,
                   embedding_model: str, working_tree_dirty: bool, inputs: dict,
                   min_strong_score: float) -> dict:
    statuses = [a["status"] for a in answers]
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "commit_sha": commit_sha,
        "working_tree_dirty": working_tree_dirty,
        "embedding_model": embedding_model,
        "llm_calls": 0,
        "min_strong_score": min_strong_score,
        "summary": {s: statuses.count(s) for s in sorted(set(statuses))},
        "examples": [trim_answer(a) for a in answers],
        "inputs": dict(inputs, not_covered=INPUTS_NOT_COVERED),
        "sources": {
            "feature": f"{REPO_URL}/blob/master/agent/ask_codebase.py",
            "corpus": f"{REPO_URL}/blob/master/agent/backend_rag_corpus.py",
            "publisher": f"{REPO_URL}/blob/master/agent/publish_ask_codebase_examples.py",
        },
    }


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main(argv: list) -> int:
    import ask_codebase
    from embeddings import model_id

    examples = extract_examples(PAGE.read_text(encoding="utf-8"))
    answers = [ask_codebase.ask(q) for q in examples]
    out_rel = OUTPUT_PATH.relative_to(REPO_ROOT).as_posix()
    dirty = any(l.strip() and not l.endswith(out_rel) for l in _git("status", "--porcelain").splitlines())
    snap = build_snapshot(
        examples, answers, commit_sha=_git("rev-parse", "HEAD"),
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        embedding_model=model_id(), working_tree_dirty=dirty,
        inputs=compute_input_hashes(examples), min_strong_score=ask_codebase.MIN_STRONG_SCORE)
    text = json.dumps(snap, indent=2, ensure_ascii=False) + "\n"
    if "--stdout" in argv:
        print(text, end="")
    else:
        OUTPUT_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {out_rel} (commit={snap['commit_sha'][:7]}, {snap['summary']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
