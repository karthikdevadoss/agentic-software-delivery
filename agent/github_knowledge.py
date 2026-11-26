"""GitHub knowledge pipeline (2026-11-26): pull requests and issues of this
repository, synced into a small retrieval index with freshness on every hit.

Kraken's AI Foundations "Context" squad builds "pipelines that collect
knowledge from tools like Notion, Slack and GitHub". This is that pattern at
demo scale, with the properties that make such a pipeline trustworthy:

  * FULL LISTING, INCREMENTAL EMBEDDING. Each sync lists every PR and issue
    (a handful of API pages), but only items whose content hash changed are
    re-embedded. Embedding is the expensive part; listing everything is what
    makes deletions detectable.
  * DELETIONS ARE REAL. An item that is no longer listed (deleted, transferred,
    made private) is removed from the index in the same sync. Stale knowledge
    is a correctness bug, not a cosmetic one.
  * FRESHNESS ON EVERY ANSWER. Each hit carries the item's own updated_at and
    the time of the sync that indexed it.
  * KEEP LAST GOOD. A failed sync (rate limit, network) keeps the previous
    index and records the error; it never empties the index. On a fresh
    process the committed snapshot (agent/knowledge/github_snapshot.json) is
    the starting point, so the feature works before the first live sync.
  * PUBLIC ONLY. Every document is tagged access_level "public": this reads a
    public repository with no credentials. Private sources would need the
    permission filtering in permission_retrieval.py, which is not wired here.

No model is called. Embeddings are the same local model as Ask the Codebase.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = os.environ.get("GITHUB_KNOWLEDGE_REPO", "karthikdevadoss/agentic-software-delivery")
API = "https://api.github.com"
MAX_PAGES = 10            # 1,000 items: far above this repo, bounds a runaway listing
BODY_CHARS = 4000         # per item; titles and states matter more than long bodies
SNAPSHOT = Path(__file__).resolve().parent / "knowledge" / "github_snapshot.json"
SYNC_INTERVAL_SECONDS = int(os.environ.get("GITHUB_KNOWLEDGE_SYNC_SECONDS", "1800"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# --- fetch ------------------------------------------------------------------

def _http_get_json(url: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "agentic-platform-knowledge-sync"}
    token = os.environ.get("GITHUB_KNOWLEDGE_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_items(get_json=_http_get_json) -> list[dict]:
    """Every issue and pull request (the issues endpoint lists both)."""
    items = []
    for page in range(1, MAX_PAGES + 1):
        batch = get_json(f"{API}/repos/{REPO}/issues?state=all&per_page=100&page={page}")
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
    return items


# --- normalise --------------------------------------------------------------

def normalize(item: dict) -> dict:
    is_pr = "pull_request" in item
    kind = "pull request" if is_pr else "issue"
    state = item.get("state", "open")
    if is_pr and (item.get("pull_request") or {}).get("merged_at"):
        state = "merged"
    title = (item.get("title") or "").strip()
    body = (item.get("body") or "").strip()[:BODY_CHARS]
    text = f"{kind.capitalize()} #{item['number']}: {title}\nState: {state}\n\n{body}"
    return {
        "key": f"{'pr' if is_pr else 'issue'}#{item['number']}",
        "kind": kind,
        "number": item["number"],
        "title": title,
        "state": state,
        "url": item.get("html_url"),
        "updated_at": item.get("updated_at"),
        "access_level": "public",
        "text": text,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


# --- store + sync -----------------------------------------------------------

class KnowledgeStore:
    def __init__(self):
        self.docs: dict[str, dict] = {}       # key -> normalised doc + "vector" + "indexed_at"
        self.synced_at: str | None = None
        self.source: str = "empty"            # empty | snapshot | live
        self.last_error: str | None = None
        self.last_report: dict | None = None
        self._lock = threading.Lock()

    def status(self) -> dict:
        with self._lock:
            return {"repo": REPO, "documents": len(self.docs), "synced_at": self.synced_at,
                    "source": self.source, "last_error": self.last_error,
                    "last_sync": self.last_report,
                    "pull_requests": sum(d["kind"] == "pull request" for d in self.docs.values()),
                    "issues": sum(d["kind"] == "issue" for d in self.docs.values())}


def sync(store: KnowledgeStore, items: list[dict], embed_fn, now: str | None = None,
         source: str = "live") -> dict:
    """Bring the store in line with `items`. Only new or changed docs are
    embedded; docs no longer listed are removed. Atomic: the swap happens only
    after every embedding succeeded, so a failure leaves the old index intact."""
    now = now or _now_iso()
    incoming = {d["key"]: d for d in (normalize(i) for i in items)}
    with store._lock:
        current = dict(store.docs)
    to_embed = [d for k, d in incoming.items()
                if k not in current or current[k]["content_hash"] != d["content_hash"]]
    vectors = embed_fn([d["text"] for d in to_embed]) if to_embed else []
    added = sum(1 for d in to_embed if d["key"] not in current)
    new_docs = {}
    for k, d in incoming.items():
        if k in current and current[k]["content_hash"] == d["content_hash"]:
            new_docs[k] = {**current[k], **{f: d[f] for f in ("updated_at", "url")}}
    for d, v in zip(to_embed, vectors):
        new_docs[d["key"]] = {**d, "vector": list(v), "indexed_at": now}
    report = {"added": added, "updated": len(to_embed) - added,
              "unchanged": len(incoming) - len(to_embed),
              "deleted": len([k for k in current if k not in incoming]),
              "embedded": len(to_embed), "at": now, "source": source}
    with store._lock:
        store.docs = new_docs
        store.synced_at = now
        store.source = source
        store.last_error = None
        store.last_report = report
    return report


def search(store: KnowledgeStore, query: str, embed_query_fn, k: int = 3) -> list[dict]:
    import numpy as np
    with store._lock:
        docs = list(store.docs.values())
        synced_at = store.synced_at
    if not docs:
        return []
    q = np.asarray(embed_query_fn(query), dtype=float)
    m = np.asarray([d["vector"] for d in docs], dtype=float)
    scores = (m @ q) / (np.linalg.norm(m, axis=1) * (np.linalg.norm(q) or 1.0) + 1e-12)
    order = np.argsort(-scores)[:k]
    return [{"key": docs[i]["key"], "kind": docs[i]["kind"], "number": docs[i]["number"],
             "title": docs[i]["title"], "state": docs[i]["state"], "url": docs[i]["url"],
             "updated_at": docs[i]["updated_at"], "indexed_at": docs[i]["indexed_at"],
             "synced_at": synced_at, "access_level": docs[i]["access_level"],
             "score": round(float(scores[i]), 4),
             "excerpt": docs[i]["text"][:600]} for i in order]


# --- process-wide instance ----------------------------------------------------

STORE = KnowledgeStore()


def _embed_fns():
    from embeddings import embed_texts, embed_query
    return embed_texts, embed_query


def _precomputed_embedder(vectors: dict, fallback):
    """embed_fn that serves vectors stored in the snapshot (keyed by content
    hash) and only embeds texts it has no vector for."""
    def embed(texts):
        out, missing = [None] * len(texts), []
        for i, text in enumerate(texts):
            v = vectors.get(hashlib.sha256(text.encode("utf-8")).hexdigest())
            if v is None:
                missing.append(i)
            else:
                out[i] = v
        if missing:
            for i, v in zip(missing, fallback([texts[i] for i in missing])):
                out[i] = v
        return out
    return embed


def load_snapshot(store: KnowledgeStore = STORE, path: Path = SNAPSHOT, embed_fns=None) -> dict | None:
    """Start from the committed snapshot. Its stored vectors are used when they
    were made by the same embedding model, so boot needs no embedding work;
    otherwise (or for any item without a vector) it embeds as usual."""
    if not path.exists():
        return None
    snap = json.loads(path.read_text(encoding="utf-8"))
    embed_texts, _ = (embed_fns or _embed_fns)()
    vectors = {}
    if snap.get("model_id") and snap.get("model_id") == _current_model_id():
        vectors = snap.get("vectors") or {}
    report = sync(store, snap["items"], _precomputed_embedder(vectors, embed_texts),
                  now=snap["captured_at"], source="snapshot")
    report["precomputed"] = bool(vectors)
    return report


def _current_model_id() -> str:
    from embeddings import model_id
    return model_id()


def sync_live(store: KnowledgeStore = STORE, get_json=_http_get_json) -> dict:
    try:
        items = fetch_items(get_json)
        embed_texts, _ = _embed_fns()
        return sync(store, items, embed_texts, source="live")
    except Exception as exc:  # noqa: BLE001 - keep last good index, report the failure
        with store._lock:
            store.last_error = f"{type(exc).__name__}: {exc}"[:300]
        return {"error": store.last_error}


def start_background_sync(store: KnowledgeStore = STORE) -> threading.Thread:
    """Snapshot first (works offline), then live sync now and every interval."""
    def loop():
        try:
            load_snapshot(store)
        except Exception as exc:  # noqa: BLE001
            store.last_error = f"snapshot: {type(exc).__name__}: {exc}"[:300]
        while True:
            sync_live(store)
            time.sleep(SYNC_INTERVAL_SECONDS)
    t = threading.Thread(target=loop, name="github-knowledge-sync", daemon=True)
    t.start()
    return t


def write_snapshot(path: Path = SNAPSHOT, get_json=_http_get_json) -> int:
    """Capture the raw API items so a fresh process has a starting point."""
    items = fetch_items(get_json)
    keep = ("number", "title", "body", "state", "html_url", "updated_at", "pull_request")
    slim = [{k: i.get(k) for k in keep if k in i} for i in items]
    for s in slim:
        if s.get("pull_request"):
            s["pull_request"] = {"merged_at": s["pull_request"].get("merged_at")}
    # Store each item's vector (keyed by content hash, rounded to keep the
    # file small) so a fresh process can serve answers without embedding.
    embed_texts, _ = _embed_fns()
    docs = [normalize(s) for s in slim]
    vecs = embed_texts([d["text"] for d in docs])
    vectors = {d["content_hash"]: [round(float(x), 5) for x in v] for d, v in zip(docs, vecs)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"repo": REPO, "captured_at": _now_iso(), "model_id": _current_model_id(),
                                "items": slim, "vectors": vectors},
                               ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return len(slim)


if __name__ == "__main__":
    print(f"wrote {write_snapshot()} items to {SNAPSHOT}")
