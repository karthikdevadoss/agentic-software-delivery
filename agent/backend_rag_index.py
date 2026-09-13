"""
Curated backend-context RAG index: ingestion, semantic-boundary chunking,
embedding, persistence, and top-k retrieval over agent/backend_rag_corpus.py's
small curated document set.

Deliberately SEPARATE from agent/rag_index.py (the existing whole-repo
index used by the V3 CLI agent): that index answers "what in this
repository looks related to a free-form ticket", indexed blindly and
fixed-window-chunked. This index answers a narrower, curated question --
"given a backend requirement, what code/tests/architecture context is
relevant" -- over an explicitly curated document list, chunked at logical
boundaries (Java class members, Markdown headings, JSON catalogue items)
rather than blind fixed-size windows, and carries per-chunk metadata
(source_type, symbol, line range) that agent/rag_index.py's chunks do not.

Both indexes reuse the SAME embedding provider (agent/embeddings.py) and
the same "reuse tools.py's security boundary, never reimplement it"
principle -- see _read_curated_document() below.

Index storage: a single local JSON file (agent/.backend_rag_index/index.json),
the same "smallest credible solution" choice already made for the
whole-repo index (see docs/DECISIONS.md) -- this curated corpus is smaller
still, so introducing pgvector or an external vector database here would
be infrastructure added to say "vector database", not because the actual
retrieval problem needs it.
"""

import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np

import tools
from embeddings import embed_texts, embed_query, model_id
from backend_rag_corpus import CORPUS_DOCUMENTS
import metrics

INDEX_DIR = tools.REPO_ROOT / "agent" / ".backend_rag_index"
INDEX_PATH = INDEX_DIR / "index.json"

# Sub-split threshold: a logical chunk (a Java member, a Markdown section)
# larger than this is further windowed so no single chunk/embedding call
# represents an unboundedly large piece of text. Same window/overlap
# values as agent/rag_index.py's fixed-window chunker, reused here only
# as a fallback bound, not as the primary chunking strategy.
MAX_CHUNK_LINES = 120
SUB_WINDOW_LINES = 40
SUB_WINDOW_OVERLAP = 8


def _chunking_version() -> str:
    return f"semantic-boundary-v1_subwindow{SUB_WINDOW_LINES}-{SUB_WINDOW_OVERLAP}"


# --- reading: reuse tools.py's path-security + redaction, but not its --
# --- generic 20KB per-call truncation, which exists to bound context ---
# --- handed to an LLM per tool call, not to bound a persistent chunked --
# --- index (each individual chunk stays small; the whole document does
# --- not need to). ------------------------------------------------------

def _read_curated_document(rel_path: str) -> str:
    resolved = tools._resolve_safe_path(rel_path)
    if resolved.suffix.lower() not in tools.ALLOWED_READ_EXTENSIONS:
        raise tools.RepoToolError(f"extension not allowed for reading: {resolved.suffix}")
    if not resolved.exists() or not resolved.is_file():
        raise tools.RepoToolError(f"file not found: {rel_path}")
    raw = resolved.read_text(encoding="utf-8", errors="replace")
    return tools.redact_secrets(raw)


# --- chunkers: one per content_type, each returning a list of ----------
# --- {"symbol", "start_line", "end_line", "text"} dicts (start/end are --
# --- 1-based inclusive line numbers, or None when a document has no ----
# --- meaningful line-range concept, e.g. one JSON catalogue item). ------

_CLASS_DECL_RE = re.compile(r"\b(class|interface|enum|record)\s+\w+")
_METHOD_NAME_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_FIELD_NAME_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*[=;]")


def _extract_java_symbol(chunk_text: str) -> str | None:
    for line in chunk_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@") or stripped.startswith("//") or stripped.startswith("*"):
            continue
        m = _METHOD_NAME_RE.search(line)
        if m:
            return m.group(1)
    m2 = _FIELD_NAME_RE.search(chunk_text)
    if m2:
        return m2.group(1)
    return None


def _chunk_java(text: str) -> list[dict]:
    """Chunks at logical Java boundaries: one header chunk (package +
    imports + class declaration), then one chunk per top-level class
    member (field, constructor, method), found via brace-depth tracking
    rather than a full parser.

    Known limitation (documented, not hidden): brace counting does not
    understand string/char literals containing '{' or '}', so a member
    containing one could be mis-bounded. Verified correct against this
    project's actual small, conventionally-formatted Customer app source
    files (no such literals present); a more complex file would need a
    real Java parser, which this minimal slice deliberately does not add.
    """
    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return []

    depth = 0
    header_end = None  # 0-based index of the class declaration's opening-brace line
    i = 0
    while i < n:
        depth += lines[i].count("{") - lines[i].count("}")
        if header_end is None and _CLASS_DECL_RE.search(lines[i]) and "{" in lines[i]:
            header_end = i
            i += 1
            break
        i += 1

    if header_end is None:
        # No class/interface/enum/record found (unexpected for this corpus) —
        # fall back to a single whole-file chunk rather than guessing.
        return [{"symbol": "whole_file", "start_line": 1, "end_line": n, "text": text.strip()}]

    chunks = [{
        "symbol": "class_header",
        "start_line": 1, "end_line": header_end + 1,
        "text": "\n".join(lines[:header_end + 1]).strip(),
    }]

    member_base_depth = depth  # depth immediately inside the class body (normally 1)
    member_start = None
    member_lines: list[str] = []
    exceeded = False

    j = header_end + 1
    while j < n:
        line = lines[j]
        stripped = line.strip()
        if member_start is None:
            if stripped == "" or stripped == "}":
                j += 1
                continue
            member_start = j
            member_lines = []
            exceeded = False

        member_lines.append(line)
        depth += line.count("{") - line.count("}")
        if depth > member_base_depth:
            exceeded = True

        ended = (exceeded and depth <= member_base_depth) or (
            not exceeded and depth == member_base_depth and stripped.endswith(";")
        )
        if ended:
            chunk_text = "\n".join(member_lines).strip()
            if chunk_text:
                symbol = _extract_java_symbol(chunk_text) or f"member_L{member_start + 1}"
                chunks.append({
                    "symbol": symbol, "start_line": member_start + 1, "end_line": j + 1,
                    "text": chunk_text,
                })
            member_start = None
            member_lines = []
        j += 1

    if member_lines:
        chunk_text = "\n".join(member_lines).strip()
        if chunk_text:
            symbol = _extract_java_symbol(chunk_text) or f"member_L{member_start + 1}"
            chunks.append({
                "symbol": symbol, "start_line": member_start + 1, "end_line": n,
                "text": chunk_text,
            })
    return chunks


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _chunk_markdown(text: str) -> list[dict]:
    """Chunks at Markdown heading boundaries (any level). A section runs
    from its heading line to the line before the next heading."""
    lines = text.splitlines()
    if not lines:
        return []

    chunks = []
    current_heading = "(front matter)"
    current_start = 1
    current_lines: list[str] = []

    def flush(end_line: int):
        content = "\n".join(current_lines).strip()
        if content:
            chunks.append({
                "symbol": current_heading, "start_line": current_start,
                "end_line": end_line, "text": content,
            })

    for idx, line in enumerate(lines, start=1):
        m = _HEADING_RE.match(line)
        if m:
            flush(idx - 1)
            current_heading = m.group(2).strip()
            current_start = idx
            current_lines = [line]
        else:
            current_lines.append(line)
    flush(len(lines))
    return chunks


def _chunk_json_catalogue(text: str) -> list[dict]:
    """Chunks a JSON document with a top-level "items" list (this
    project's docs/ACTION_QUEUE.json shape) into one chunk per item —
    each item is already a self-contained unit of knowledge. Falls back
    to a single whole-document chunk if the shape doesn't match, rather
    than guessing at a different structure."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [{"symbol": "whole_file", "start_line": None, "end_line": None, "text": text.strip()}]

    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [{"symbol": "whole_file", "start_line": None, "end_line": None, "text": text.strip()}]

    chunks = []
    for idx, item in enumerate(items):
        symbol = item.get("id", f"item_{idx}") if isinstance(item, dict) else f"item_{idx}"
        chunks.append({
            "symbol": str(symbol), "start_line": None, "end_line": None,
            "text": json.dumps(item, indent=2),
        })
    return chunks


def _sub_split_if_large(chunk: dict) -> list[dict]:
    """A logical chunk (a Java member, a Markdown section) can still be
    large (e.g. a long incident-lesson section) — sub-split those with
    the same bounded fixed-window strategy agent/rag_index.py uses, so no
    single embedding call represents an unboundedly large piece of text.
    Chunks with no line-range concept (JSON items) are never sub-split."""
    lines = chunk["text"].splitlines()
    if len(lines) <= MAX_CHUNK_LINES or chunk["start_line"] is None:
        return [chunk]

    parts = []
    step = max(SUB_WINDOW_LINES - SUB_WINDOW_OVERLAP, 1)
    i = 0
    part_no = 1
    while i < len(lines):
        window = lines[i:i + SUB_WINDOW_LINES]
        text = "\n".join(window).strip()
        if text:
            parts.append({
                "symbol": f"{chunk['symbol']}::part{part_no}",
                "start_line": chunk["start_line"] + i,
                "end_line": chunk["start_line"] + i + len(window) - 1,
                "text": text,
            })
            part_no += 1
        if i + SUB_WINDOW_LINES >= len(lines):
            break
        i += step
    return parts


_CHUNKERS = {"java": _chunk_java, "markdown": _chunk_markdown, "json": _chunk_json_catalogue}


def chunk_document(content_type: str, text: str) -> list[dict]:
    chunker = _CHUNKERS.get(content_type)
    if chunker is None:
        raise ValueError(f"no chunker registered for content_type={content_type!r}")
    raw_chunks = chunker(text)
    result = []
    for c in raw_chunks:
        result.extend(_sub_split_if_large(c))
    return result


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_id(source_path: str, symbol: str, occurrence: int) -> str:
    base = f"{source_path}::{symbol}"
    return base if occurrence == 0 else f"{base}#{occurrence}"


def _load_raw_index():
    if not INDEX_PATH.exists():
        return None
    try:
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def build_index(force_full_rebuild: bool = False) -> dict:
    """Ingests every agent/backend_rag_corpus.CORPUS_DOCUMENTS entry,
    chunks it at logical boundaries, embeds only changed/new documents
    (whole-document content-hash reuse — this corpus is small enough that
    per-chunk diffing, as the whole-repo index does, is not worth the
    extra complexity), and persists to INDEX_PATH."""
    start = time.monotonic()

    existing = None if force_full_rebuild else _load_raw_index()
    rebuild_reason = None
    if force_full_rebuild:
        rebuild_reason = "forced full rebuild requested"
    elif existing is None:
        rebuild_reason = "no existing (or unreadable) index"
    elif existing.get("model_id") != model_id():
        rebuild_reason = f"embedding model changed ({existing.get('model_id')!r} -> {model_id()!r})"
        existing = None
    elif existing.get("chunking_version") != _chunking_version():
        rebuild_reason = f"chunking strategy changed ({existing.get('chunking_version')!r} -> {_chunking_version()!r})"
        existing = None

    old_documents = {} if existing is None else existing.get("documents", {})
    old_chunks = {} if existing is None else existing.get("chunks", {})

    new_documents = {}
    new_chunks = {}
    texts_to_embed = []
    pending_meta = []  # parallel to texts_to_embed

    documents_unchanged = documents_reembedded = 0

    for doc in CORPUS_DOCUMENTS:
        text = _read_curated_document(doc.source_path)
        content_hash = _hash_text(text)
        old_entry = old_documents.get(doc.source_path)

        if old_entry is not None and old_entry["content_hash"] == content_hash:
            new_documents[doc.source_path] = old_entry
            for cid in old_entry["chunk_ids"]:
                if cid in old_chunks:
                    new_chunks[cid] = old_chunks[cid]
            documents_unchanged += 1
            continue

        documents_reembedded += 1
        chunk_ids = []
        seen_ids: dict = {}
        for c in chunk_document(doc.content_type, text):
            occurrence = seen_ids.get((doc.source_path, c["symbol"]), 0)
            seen_ids[(doc.source_path, c["symbol"])] = occurrence + 1
            cid = _chunk_id(doc.source_path, c["symbol"], occurrence)
            chunk_ids.append(cid)
            texts_to_embed.append(c["text"])
            pending_meta.append((cid, doc, c))
        new_documents[doc.source_path] = {"content_hash": content_hash, "chunk_ids": chunk_ids}

    chunks_embedded = 0
    if texts_to_embed:
        vectors = embed_texts(texts_to_embed)
        for (cid, doc, c), vector in zip(pending_meta, vectors):
            new_chunks[cid] = {
                "source_path": doc.source_path,
                "source_type": doc.source_type,
                "symbol": c["symbol"],
                "start_line": c["start_line"],
                "end_line": c["end_line"],
                "content": c["text"],
                "vector": vector,
            }
        chunks_embedded = len(texts_to_embed)

    if not new_chunks:
        raise RuntimeError("No chunks produced from the curated backend RAG corpus — nothing to index.")

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": model_id(),
        "chunking_version": _chunking_version(),
        "documents": new_documents,
        "chunks": new_chunks,
    }
    INDEX_PATH.write_text(json.dumps(payload), encoding="utf-8")

    global _loaded_index
    _loaded_index = payload

    stats = {
        "documents_total": len(CORPUS_DOCUMENTS),
        "documents_unchanged": documents_unchanged,
        "documents_reembedded": documents_reembedded,
        "chunks_total": len(new_chunks),
        "chunks_embedded": chunks_embedded,
        "duration_ms": round((time.monotonic() - start) * 1000, 1),
        "model_id": model_id(),
        "index_path": str(INDEX_PATH.relative_to(tools.REPO_ROOT)),
        "rebuild_reason": rebuild_reason,
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
                "No backend RAG index found. Build one first: python agent/backend_rag_index.py"
            )
        _loaded_index = index
    return _loaded_index


def invalidate_cache():
    """Test-only: force the next _load_index()/semantic_search() call to
    re-read INDEX_PATH from disk instead of an in-memory cached copy."""
    global _loaded_index
    _loaded_index = None


def semantic_search(query: str, top_k: int = 5, source_type: str | None = None) -> list[dict]:
    """Returns up to top_k structured candidates, ranked by cosine
    similarity, each carrying full provenance metadata. This is
    retrieval only — evidence to be cited, never asserted as ground
    truth on its own (see agent/backend_planning.py's context contract)."""
    start = time.monotonic()
    index = _load_index()

    if index["model_id"] != model_id():
        raise RuntimeError(
            f"backend RAG index was built with model {index['model_id']!r} but the "
            f"current embedding provider is {model_id()!r}. Rebuild the index."
        )

    chunk_ids = [
        cid for cid, c in index["chunks"].items()
        if source_type is None or c["source_type"] == source_type
    ]
    if not chunk_ids:
        return []

    query_vec = np.array(embed_query(query))
    matrix = np.array([index["chunks"][cid]["vector"] for cid in chunk_ids])
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vec)
    norms[norms == 0] = 1e-10
    scores = (matrix @ query_vec) / norms

    top_positions = np.argsort(-scores)[:top_k]
    results = []
    for rank, pos in enumerate(top_positions, start=1):
        cid = chunk_ids[pos]
        c = index["chunks"][cid]
        results.append({
            "rank": rank,
            "score": round(float(scores[pos]), 4),
            "chunk_id": cid,
            "source_path": c["source_path"],
            "source_type": c["source_type"],
            "symbol": c["symbol"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "content": c["content"],
        })

    metrics.record_retrieval(
        query=query, top_k=top_k, candidates_count=len(results),
        duration_ms=round((time.monotonic() - start) * 1000, 1),
    )
    return results


if __name__ == "__main__":
    summary = build_index()
    print(
        f"documents: total={summary['documents_total']} unchanged={summary['documents_unchanged']} "
        f"reembedded={summary['documents_reembedded']} | chunks: total={summary['chunks_total']} "
        f"embedded={summary['chunks_embedded']} | {summary['duration_ms']}ms -> {summary['index_path']}"
    )
