"""
Loads and resolves agent/web/learn-tree.json — the single canonical Learn
knowledge model. Both the recursive Learn routes (web_server.py) and the
PDF book generator (learn_pdf.py) import from here so there is exactly
ONE knowledge source, never two that can drift apart.

Cached in-process, invalidated automatically when the file's mtime
changes (so `python agent/build_learn_tree.py` followed by a normal
request picks up new content without a server restart).
"""

import json
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
TREE_PATH = WEB_DIR / "learn-tree.json"

_cache = {"mtime": None, "tree": None}


def load_tree() -> dict:
    mtime = TREE_PATH.stat().st_mtime
    if _cache["tree"] is None or _cache["mtime"] != mtime:
        _cache["tree"] = json.loads(TREE_PATH.read_text(encoding="utf-8"))
        _cache["mtime"] = mtime
    return _cache["tree"]


def resolve_path(path_segments: list[str]):
    """Walk the tree by slug path. Returns (node, breadcrumb) on success,
    (None, None) if any segment doesn't match — the caller decides how to
    respond (e.g. a real HTTP 404), this function never guesses/fuzzy-matches."""
    tree = load_tree()
    nodes = tree["domains"]
    breadcrumb = []
    node = None
    for seg in path_segments:
        match = next((n for n in nodes if n["slug"] == seg), None)
        if match is None:
            return None, None
        node = match
        breadcrumb.append({"slug": node["slug"], "title": node["title"]})
        nodes = node.get("children") or []
    return node, breadcrumb


def find_node_by_slug(slug: str, nodes=None):
    """Depth-first search for a node anywhere in the tree by its slug —
    used to resolve related-topic links without needing their full path."""
    if nodes is None:
        nodes = load_tree()["domains"]
    for n in nodes:
        if n["slug"] == slug:
            return n
        found = find_node_by_slug(slug, n.get("children") or [])
        if found:
            return found
    return None
