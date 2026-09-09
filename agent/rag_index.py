"""
RAG index (Phase B): incremental chunking, persistence, and semantic search.

Reuses tools.py's existing safe traversal (list_repository_files) and safe
read (read_file, which already redacts secrets) for ingestion — there is no
second, separate filesystem-walking implementation here. Anything tools.py
excludes (.env, .git, target/, secret-named files) or redacts is
automatically excluded/redacted from the index too.

Incremental by design: each file's post-redaction text is hashed; unchanged
files reuse their existing chunk vectors verbatim (zero re-embedding calls),
changed/new files are re-chunked and re-embedded, and files no longer
present are dropped from the index. A full rebuild only happens when there
is no existing index, or the embedding model/chunking strategy changed
(incompatible with what's stored) — never "just because".

Index storage: a single local JSON file, no external vector database. For
this repository's size (dozens of files), an in-memory numpy cosine-similarity
scan over the stored vectors is genuinely fast and simple — not a compromise,
just appropriately sized. Swappable for Qdrant/pgvector later without
changing the semantic_search() call signature.

This is retrieval only — it finds candidate files/chunks. It is never treated
as authoritative on its own; callers must still use read_file/search_code to
verify actual current source before relying on anything it returns.
"""

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from tools import REPO_ROOT, ALLOWED_READ_EXTENSIONS, list_repository_files, read_file
from embeddings import embed_texts, embed_query, model_id
import metrics

INDEX_DIR = REPO_ROOT / "agent" / ".rag_index"
INDEX_PATH = INDEX_DIR / "index.json"

CHUNK_LINES = 40
CHUNK_OVERLAP = 8

# Not a security exclusion (tools.py already owns that) — just things that
# aren't project knowledge worth retrieving, including the index's own
# output (or it would index itself and grow unboundedly on every rebuild).
RAG_IGNORED_PREFIXES = (".claude/", "agent/.rag_index/")


def _chunking_version() -> str:
    return f"lines{CHUNK_LINES}_overlap{CHUNK_OVERLAP}"


def _indexable_files() -> list[str]:
    listing = list_repository_files(".")
    paths = []
    for line in listing.splitlines():
        line = line.strip()
        if not line or line.startswith("...") or line.startswith("("):
            continue
        if line.startswith(RAG_IGNORED_PREFIXES):
            continue
        if Path(line).suffix.lower() in ALLOWED_READ_EXTENSIONS:
            paths.append(line)
    return paths


def _strip_read_file_header(content: str, rel_path: str) -> str:
    header = f"--- {rel_path} ---\n"
    if content.startswith(header):
        return content[len(header):]
    return content


def _read_indexable_text(rel_path: str) -> str:
    """The exact text used for both hashing and chunking, so 'unchanged'
    and 'what would be re-chunked' can never silently disagree."""
    raw = read_file(rel_path)  # reuses redaction + size truncation
    return _strip_read_file_header(raw, rel_path)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_text(rel_path: str, text: str) -> list[dict]:
    lines = text.splitlines()
    if not lines:
        return []

    chunks = []
    step = max(CHUNK_LINES - CHUNK_OVERLAP, 1)
    i = 0
    while i < len(lines):
        window = lines[i:i + CHUNK_LINES]
        chunk_text = "\n".join(window).strip()
        if chunk_text:
            chunks.append({
                "path": rel_path,
                "start_line": i + 1,
                "end_line": i + len(window),
                "text": chunk_text,
            })
        if i + CHUNK_LINES >= len(lines):
            break
        i += step
    return chunks


def _chunk_id(rel_path: str, start_line: int, end_line: int) -> str:
    return f"{rel_path}#{start_line}-{end_line}"


def _load_raw_index():
    """Returns the parsed index dict, or None if missing/corrupt/unreadable
    (all treated the same way: safe to fall back to a full rebuild)."""
    if not INDEX_PATH.exists():
        return None
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def build_index(force_full_rebuild: bool = False) -> dict:
    """Incrementally ingest -> chunk -> embed -> persist. Returns a
    structured stats dict (also recorded via metrics.record_rag_index)."""
    start = time.monotonic()

    existing = None if force_full_rebuild else _load_raw_index()
    rebuild_reason = None

    if force_full_rebuild:
        rebuild_reason = "forced full rebuild requested"
    elif existing is None:
        rebuild_reason = "no existing (or unreadable) index"
    elif existing.get("model_id") != model_id():
        rebuild_reason = (
            f"embedding model changed ({existing.get('model_id')!r} -> {model_id()!r})"
        )
        existing = None
    elif existing.get("chunking_version") != _chunking_version():
        rebuild_reason = (
            f"chunking strategy changed ({existing.get('chunking_version')!r} -> "
            f"{_chunking_version()!r})"
        )
        existing = None

    full_rebuild = existing is None
    old_files = {} if existing is None else existing.get("files", {})
    old_chunks = {} if existing is None else existing.get("chunks", {})

    current_files = _indexable_files()
    current_file_set = set(current_files)

    new_files = {}
    new_chunks = {}
    texts_to_embed = []
    pending_chunk_meta = []  # parallel to texts_to_embed: (chunk_id, path, start, end)

    files_unchanged = files_changed = files_added = 0

    for rel_path in current_files:
        text = _read_indexable_text(rel_path)
        content_hash = _hash_text(text)
        old_entry = old_files.get(rel_path)

        if old_entry is not None and old_entry["content_hash"] == content_hash:
            new_files[rel_path] = old_entry
            for cid in old_entry["chunk_ids"]:
                if cid in old_chunks:
                    new_chunks[cid] = old_chunks[cid]
            files_unchanged += 1
            continue

        files_added += 1 if old_entry is None else 0
        files_changed += 1 if old_entry is not None else 0

        chunk_ids = []
        for c in _chunk_text(rel_path, text):
            cid = _chunk_id(rel_path, c["start_line"], c["end_line"])
            chunk_ids.append(cid)
            texts_to_embed.append(c["text"])
            pending_chunk_meta.append((cid, rel_path, c["start_line"], c["end_line"]))
        new_files[rel_path] = {"content_hash": content_hash, "chunk_ids": chunk_ids}

    # At this point new_chunks contains exactly the reused (unchanged-file)
    # chunks — changed/added chunks are merged in only after embedding below.
    chunks_reused = len(new_chunks)

    files_deleted = sum(1 for p in old_files if p not in current_file_set)
    chunks_removed = sum(
        len(old_files[p]["chunk_ids"]) for p in old_files if p not in current_file_set
    )

    chunks_embedded = 0
    if texts_to_embed:
        vectors = embed_texts(texts_to_embed)
        for (cid, rel_path, start_line, end_line), vector in zip(pending_chunk_meta, vectors):
            new_chunks[cid] = {
                "path": rel_path, "start_line": start_line, "end_line": end_line,
                "vector": vector,
            }
        chunks_embedded = len(texts_to_embed)

    if not new_chunks:
        raise RuntimeError("No indexable files found — nothing to build the RAG index from.")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": model_id(),
        "chunking_version": _chunking_version(),
        "files": new_files,
        "chunks": new_chunks,
    }
    INDEX_PATH.write_text(json.dumps(payload), encoding="utf-8")

    global _loaded_index
    _loaded_index = payload

    stats = {
        "files_scanned": len(current_files),
        "files_unchanged": files_unchanged,
        "files_changed": files_changed,
        "files_added": files_added,
        "files_deleted": files_deleted,
        "chunks_reused": chunks_reused,
        "chunks_embedded": chunks_embedded,
        "chunks_removed": chunks_removed,
        "full_rebuild": full_rebuild,
        "rebuild_reason": rebuild_reason,
        "duration_ms": round((time.monotonic() - start) * 1000, 1),
        "model_id": model_id(),
        "index_path": str(INDEX_PATH.relative_to(REPO_ROOT)),
    }
    metrics.record_rag_index(stats)
    return stats


_loaded_index = None


def _load_index() -> dict:
    global _loaded_index
    if _loaded_index is None:
        index = _load_raw_index()
        if index is None:
            raise RuntimeError(
                "No RAG index found (or it is unreadable). Build one first: "
                "python agent/rag_index.py"
            )
        _loaded_index = index
    return _loaded_index


def semantic_search(query: str, top_k: int = 5) -> list[dict]:
    """Return up to top_k {path, start_line, end_line, score} candidates.

    This is retrieval, not verification: scores indicate likely relevance
    only. Always confirm with read_file/search_code before trusting content."""
    start = time.monotonic()
    index = _load_index()

    if index["model_id"] != model_id():
        raise RuntimeError(
            f"RAG index was built with model {index['model_id']!r} but the "
            f"current embedding provider is {model_id()!r}. Rebuild the "
            f"index: python agent/rag_index.py"
        )

    chunk_ids = list(index["chunks"].keys())
    if not chunk_ids:
        return []

    query_vec = np.array(embed_query(query))
    matrix = np.array([index["chunks"][cid]["vector"] for cid in chunk_ids])
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec)
    norms[norms == 0] = 1e-10
    scores = (matrix @ query_vec) / norms

    top_positions = np.argsort(-scores)[:top_k]
    results = []
    for pos in top_positions:
        chunk = index["chunks"][chunk_ids[pos]]
        results.append({
            "path": chunk["path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "score": round(float(scores[pos]), 4),
        })

    metrics.record_retrieval(
        query=query, top_k=top_k, candidates_count=len(results),
        duration_ms=round((time.monotonic() - start) * 1000, 1),
    )
    return results


if __name__ == "__main__":
    summary = build_index()
    print(
        f"scanned={summary['files_scanned']} unchanged={summary['files_unchanged']} "
        f"changed={summary['files_changed']} added={summary['files_added']} "
        f"deleted={summary['files_deleted']} | "
        f"chunks reused={summary['chunks_reused']} embedded={summary['chunks_embedded']} "
        f"removed={summary['chunks_removed']} | "
        f"full_rebuild={summary['full_rebuild']} ({summary['rebuild_reason']}) | "
        f"{summary['duration_ms']}ms -> {summary['index_path']}"
    )
