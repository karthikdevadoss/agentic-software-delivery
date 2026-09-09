"""
Pluggable embedding provider for the RAG index (Phase B).

Default provider: fastembed (ONNX runtime, no PyTorch, no API key) — chosen
for a working local demo today with zero credential blockers, verified on
this Windows machine. Swappable later for a code-specialized hosted model
without changing agent/rag_index.py — it only calls embed_texts()/embed_query().

Production code-embedding option (verified current as of this session, not
assumed from memory): Voyage AI's voyage-code-4 (released 2026-08, supersedes
voyage-code-3 — see docs/DECISIONS.md for the verification date/source and
re-check trigger). Matryoshka embeddings support 2048/1024/512/256
dimensions; 1024 is used here as a reasonable default.

See docs/DECISIONS.md for why this choice was made and what would change
if/when a Voyage API key becomes available.
"""

import os

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-en-v1.5"
VOYAGE_MODEL = "voyage-code-4"
VOYAGE_DIMENSIONS = 1024
PROVIDER = os.environ.get("RAG_EMBEDDING_PROVIDER", "local")

_local_model = None


def _get_local_model():
    global _local_model
    if _local_model is None:
        from fastembed import TextEmbedding
        _local_model = TextEmbedding(model_name=DEFAULT_LOCAL_MODEL)
    return _local_model


def _embed_local(texts: list[str]) -> list[list[float]]:
    model = _get_local_model()
    return [vec.tolist() for vec in model.embed(texts)]


def _embed_voyage(texts: list[str]) -> list[list[float]]:
    """Voyage AI voyage-code-4 (Anthropic's recommended code-embedding
    provider, current as of 2026-09; supersedes voyage-code-3). Not usable
    yet: requires VOYAGE_API_KEY, which is not configured in this
    environment. Implemented so switching providers later is a one-line
    config change, not a rewrite."""
    api_key = os.environ.get("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RAG_EMBEDDING_PROVIDER=voyage requires VOYAGE_API_KEY to be set "
            "(in agent/.env or the environment). Get one at https://voyageai.com. "
            "Falling back is not automatic — set RAG_EMBEDDING_PROVIDER=local "
            "to use the offline embedding model instead."
        )
    import requests
    response = requests.post(
        "https://api.voyageai.com/v1/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"input": texts, "model": VOYAGE_MODEL, "output_dimension": VOYAGE_DIMENSIONS},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return [item["embedding"] for item in data["data"]]


def model_id() -> str:
    """A stable identifier for whichever provider/model produced the vectors,
    stored in the index so a mismatched query embedding is never silently
    compared against vectors from a different model."""
    return f"voyage:{VOYAGE_MODEL}:{VOYAGE_DIMENSIONS}d" if PROVIDER == "voyage" else f"local:{DEFAULT_LOCAL_MODEL}"


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if PROVIDER == "voyage":
        return _embed_voyage(texts)
    return _embed_local(texts)


def embed_query(query: str) -> list[float]:
    return embed_texts([query])[0]
