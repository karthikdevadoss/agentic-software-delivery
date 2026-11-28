"""
Document-level permissions for retrieval -- enforced in CODE, never in a prompt.

Scope, stated honestly: this is a small FIXTURE pipeline. It indexes (1) the
existing curated public slice of this GitHub repo (every document in
backend_rag_corpus.CORPUS_DOCUMENTS is tagged `public`) and (2) a handful of
clearly fake markdown pages under agent/fixtures/permission_docs/ that stand in
for Notion/Slack-style docs, each tagged with a source and an access level.
There is no OAuth, no live Notion/Slack/GitHub crawl and no source ACL sync.

Mechanism: the caller's role is mapped to a set of allowed access levels by a
fixed table (ROLE_ALLOWED_LEVELS). Chunks whose level is not allowed are removed
from the candidate set BEFORE any similarity is computed, so a forbidden chunk
that happens to be the closest match is withheld, not merely out-ranked. A
missing/unknown/malformed role maps to the empty set (deny by default). A final
post-check re-asserts every returned chunk is allowed. No LLM is involved.
"""

import dataclasses
import hashlib
import time
from pathlib import Path

import numpy as np

import backend_rag_index
import metrics
from embeddings import embed_texts, embed_query, model_id

PUBLIC = "public"
ENG_INTERNAL = "eng-internal"
PRIVATE = "private"
ACCESS_LEVELS = (PUBLIC, ENG_INTERNAL, PRIVATE)

# Deny by default: anything not listed here gets no access at all.
ROLE_ALLOWED_LEVELS = {
    PUBLIC: frozenset({PUBLIC}),
    ENG_INTERNAL: frozenset({PUBLIC, ENG_INTERNAL}),
    PRIVATE: frozenset({PUBLIC, ENG_INTERNAL, PRIVATE}),
}

DEFAULT_PUBLIC_ROLE = PUBLIC

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "permission_docs"
FIXTURE_SOURCE_TYPE = "FIXTURE_DOC"


@dataclasses.dataclass(frozen=True)
class FixtureDoc:
    filename: str
    source: str  # which (pretend) system this stands in for
    access_level: str


# Code-defined manifest -- the only files this module ever reads.
FIXTURE_DOCUMENTS = (
    FixtureDoc("onboarding-faq.md", "notion-standin", PUBLIC),
    FixtureDoc("checkout-incident-postmortem.md", "slack-standin", ENG_INTERNAL),
    FixtureDoc("payments-reconciliation-runbook.md", "notion-standin", ENG_INTERNAL),
    FixtureDoc("compensation-bands-fixture.md", "notion-standin", PRIVATE),
)


def allowed_levels(role) -> frozenset:
    """Empty set (no access) for a missing, non-string or unknown role."""
    if not isinstance(role, str):
        return frozenset()
    return ROLE_ALLOWED_LEVELS.get(role.strip(), frozenset())


def fixture_content_hash(doc: FixtureDoc) -> str:
    """Real sha256 of the file on disk (computed, never hand-written)."""
    return hashlib.sha256((FIXTURE_DIR / doc.filename).read_bytes()).hexdigest()


_fixture_cache = None  # (model_id, hashes tuple) -> chunk list


def _fixture_chunks() -> list[dict]:
    global _fixture_cache
    docs = [(d, (FIXTURE_DIR / d.filename).read_text(encoding="utf-8")) for d in FIXTURE_DOCUMENTS]
    key = (model_id(), tuple(hashlib.sha256(t.encode("utf-8")).hexdigest() for _, t in docs))
    if _fixture_cache is not None and _fixture_cache[0] == key:
        return _fixture_cache[1]
    chunks = []
    for doc, text in docs:
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        for c in backend_rag_index.chunk_document("markdown", text):
            chunks.append({
                "chunk_id": f"fixture:{doc.filename}::{c['symbol']}#{len(chunks)}",
                "source_path": f"agent/fixtures/permission_docs/{doc.filename}",
                "source_type": FIXTURE_SOURCE_TYPE,
                "source": doc.source,
                "access_level": doc.access_level,
                "content_hash": h,
                "symbol": c["symbol"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["text"],
            })
    vectors = embed_texts([c["content"] for c in chunks])
    for c, v in zip(chunks, vectors):
        c["vector"] = v
    _fixture_cache = (key, chunks)
    return chunks


def invalidate_cache():
    """Test-only."""
    global _fixture_cache
    _fixture_cache = None


def _candidates(levels: frozenset) -> list[dict]:
    """Permission PRE-filter: only chunks whose level is allowed are ever
    candidates. Curated-corpus chunks are all `public`."""
    out = []
    if PUBLIC in levels:
        index = backend_rag_index._load_index()
        if index["model_id"] != model_id():
            raise RuntimeError(
                f"backend RAG index was built with model {index['model_id']!r} but the "
                f"current embedding provider is {model_id()!r}. Rebuild the index."
            )
        for cid, c in index["chunks"].items():
            out.append({**c, "chunk_id": cid, "source": "github-public", "access_level": PUBLIC})
    # Fixture chunks: only those whose own level is allowed become candidates.
    out.extend(c for c in _fixture_chunks() if c["access_level"] in levels)
    return out


def search(query: str, role, top_k: int = 5) -> list[dict]:
    """Ranked, permission-filtered chunks for `role`. Same result shape as
    backend_rag_index.semantic_search plus `source` and `access_level`."""
    import tracing
    start = time.monotonic()
    levels = allowed_levels(role)
    if not levels:
        return []
    # Spans (2026-11-26): the filter, the embedding and the ranking are timed
    # separately so /ask-codebase can show where the time goes. Counts and
    # levels only -- never query text or document content.
    with tracing.span("permission.filter", **{"permission.allowed_levels": ",".join(sorted(levels))}) as sp:
        cands = _candidates(levels)
        sp.set_attribute("permission.candidates", len(cands))
    if not cands:
        return []

    with tracing.span("embedding.query", **{"embedding.model": model_id()}):
        query_vec = np.array(embed_query(query))
    with tracing.span("retrieval.rank", top_k=top_k, **{"retrieval.candidates": len(cands)}) as sp:
        matrix = np.array([c["vector"] for c in cands])
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec)
        norms[norms == 0] = 1e-10
        scores = (matrix @ query_vec) / norms

        results = []
        for rank, pos in enumerate(np.argsort(-scores)[:top_k], start=1):
            c = cands[pos]
            if c["access_level"] not in levels:  # defense in depth; unreachable by construction
                raise AssertionError("permission filter violated")
            results.append({
                "rank": rank, "score": round(float(scores[pos]), 4), "chunk_id": c["chunk_id"],
                "source_path": c["source_path"], "source_type": c["source_type"],
                "symbol": c["symbol"], "start_line": c["start_line"], "end_line": c["end_line"],
                "content": c["content"], "source": c["source"], "access_level": c["access_level"],
            })
        sp.set_attribute("retrieval.hit_count", len(results))
        if results:
            sp.set_attribute("retrieval.top_score", results[0]["score"])
    metrics.record_retrieval(
        query=query, top_k=top_k, candidates_count=len(results),
        duration_ms=round((time.monotonic() - start) * 1000, 1),
    )
    return results
