"""
"Ask the Codebase" -- a public, READ-ONLY, deterministic query surface over
the existing curated backend RAG index (agent/backend_rag_index.py,
agent/backend_rag_corpus.py). Lets a visitor (interviewer or Karthik
himself) ask a real question and see grounded, cited, ranked excerpts from
the real repository -- not a chat answer.

DELIBERATE DESIGN DECISION, not an oversight: this module makes ZERO LLM
calls. agent/backend_rag_index.semantic_search() already returns ranked
chunks with real cosine-similarity scores, source files, line ranges, and
excerpts -- which already satisfies "grounded, cited retrieval" on its
own. Adding an LLM synthesis layer on top would introduce exactly the
things a PUBLIC, unauthenticated endpoint should not have: unbounded API
cost from public traffic, a prompt-injection surface, and a place for an
answer to sound confident without being grounded. See
docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml and this project's own
"deterministic vs LLM" principle, applied here at the smallest possible
LLM footprint: none.

SECURITY BOUNDARY (structural, not a policy the model might ignore):
this module never calls read_file/list_repository_files/search_code or
any write/execute/deploy tool. It can ONLY ever return content that was
pre-embedded from agent/backend_rag_corpus.CORPUS_DOCUMENTS -- a fixed,
curated, code-defined allowlist -- via
agent/backend_rag_index._read_curated_document(), which itself reuses
tools._resolve_safe_path() (traversal/absolute/symlink/secret-filename
rejection) and tools.redact_secrets() (secret-shaped content scrubbed
BEFORE embedding, so it cannot exist in the index to be retrieved even in
principle). A query cannot expand, redirect, or escape this corpus --
there is no code path from a query string to any file outside
CORPUS_DOCUMENTS, let alone outside the repository (e.g. the private
karthik-ai-context repo, or .env). This holds regardless of what the
query text says, because no LLM ever reads or acts on the query text --
it is only ever embedded into a vector and compared by cosine similarity.
"""

import dataclasses

import backend_rag_index
import permission_retrieval

GITHUB_REPO_URL = "https://github.com/karthikdevadoss/agentic-software-delivery"

# Real, already-established threshold from agent/backend_planning.py
# (MIN_USABLE_TOP_SCORE), empirically chosen against
# agent/evals/retrieval_dataset.json -- reused here rather than inventing
# a second, undocumented number for the same underlying question ("is
# this evidence strong enough to show as an answer").
MIN_STRONG_SCORE = 0.45

MAX_QUERY_LEN = 300
MIN_QUERY_LEN = 2
RESULT_COUNT = 5  # fixed, not client-controllable -- one less abuse knob


class InvalidQuery(Exception):
    """The query itself failed input validation, before any retrieval was attempted."""


@dataclasses.dataclass(frozen=True)
class EvidenceItem:
    rank: int
    score: float
    source_path: str
    source_type: str
    symbol: str
    start_line: int | None
    end_line: int | None
    excerpt: str
    source_url: str | None
    source: str = "github-public"
    access_level: str = "public"


def _source_url(source_path: str, start_line: int | None, end_line: int | None) -> str | None:
    if source_path.startswith("agent/fixtures/"):
        return None  # fake fixture doc: no public GitHub link to claim
    url = f"{GITHUB_REPO_URL}/blob/master/{source_path}"
    if start_line:
        url += f"#L{start_line}" + (f"-L{end_line}" if end_line and end_line != start_line else "")
    return url


def validate_query(raw_query: str) -> str:
    """Raises InvalidQuery with a specific, honest reason -- mirrors this
    project's own established validate_value() pattern (see
    agent/demo_catalogue.py) rather than a generic 400."""
    query = (raw_query or "").strip()
    if len(query) < MIN_QUERY_LEN:
        raise InvalidQuery("Question is too short -- ask a real question about the codebase.")
    if len(query) > MAX_QUERY_LEN:
        raise InvalidQuery(f"Question is too long ({len(query)} characters, over the {MAX_QUERY_LEN}-character limit).")
    return query


def ask(raw_query: str, role: str | None = permission_retrieval.DEFAULT_PUBLIC_ROLE) -> dict:
    """Traced wrapper (2026-11-26): one `ask_codebase.request` span around
    the whole request, with the outcome status. Query recorded as length +
    short hash only, never raw text."""
    import tracing
    with tracing.span("ask_codebase.request", **tracing.query_fingerprint(raw_query or "")) as sp:
        result = _ask(raw_query, role)
        sp.set_attribute("ask.status", result.get("status"))
        sp.set_attribute("ask.evidence_count", len(result.get("evidence") or []))
        return result


def _ask(raw_query: str, role: str | None = permission_retrieval.DEFAULT_PUBLIC_ROLE) -> dict:
    """Top-level entry point. Returns a JSON-ready dict; never raises for
    a genuinely bad/adversarial query -- validation failures and
    insufficient-evidence cases are both real, honest OUTCOMES, not
    exceptions the caller must handle specially.

    `role` is the caller's role (explicit, testable). It defaults to `public`;
    a missing (None) or unknown role is DENIED, not downgraded. Filtering
    happens in code in agent/permission_retrieval.py, before ranking."""
    if not permission_retrieval.allowed_levels(role):
        return {
            "query": raw_query, "status": "ROLE_DENIED",
            "message": "Caller role is missing or unknown; access is denied by default.",
            "evidence": [],
        }
    try:
        query = validate_query(raw_query)
    except InvalidQuery as exc:
        return {
            "query": raw_query,
            "status": "INVALID_QUERY",
            "message": str(exc),
            "evidence": [],
        }

    try:
        raw_results = permission_retrieval.search(query, role, top_k=RESULT_COUNT)
    except RuntimeError as exc:
        # The index genuinely doesn't exist / needs rebuilding -- a real,
        # honest operational state, never silently swallowed into "no
        # results found" (which would look like the corpus was searched
        # and came up empty, when actually nothing was searched at all).
        return {
            "query": query,
            "status": "INDEX_UNAVAILABLE",
            "message": f"The codebase index is not currently available: {exc}",
            "evidence": [],
        }

    evidence = [
        EvidenceItem(
            rank=r["rank"], score=r["score"], source_path=r["source_path"],
            source_type=r["source_type"], symbol=r["symbol"],
            start_line=r["start_line"], end_line=r["end_line"],
            excerpt=r["content"],
            source_url=_source_url(r["source_path"], r["start_line"], r["end_line"]),
            source=r["source"], access_level=r["access_level"],
        )
        for r in raw_results
    ]

    if not evidence:
        return {
            "query": query, "status": "NO_EVIDENCE",
            "message": "No indexed content matched this question at all.",
            "evidence": [],
        }

    top_score = evidence[0].score
    if top_score < MIN_STRONG_SCORE:
        return {
            "query": query, "status": "WEAK_EVIDENCE",
            "message": (
                f"The closest matches (top score {top_score}) are below this system's own "
                f"confidence threshold ({MIN_STRONG_SCORE}) for a real answer. Shown anyway, "
                "labeled honestly, rather than hidden or guessed at."
            ),
            "evidence": [dataclasses.asdict(e) for e in evidence],
        }

    return {
        "query": query, "status": "STRONG_EVIDENCE",
        "message": f"{len(evidence)} relevant excerpt(s) found in the indexed codebase.",
        "evidence": [dataclasses.asdict(e) for e in evidence],
    }
