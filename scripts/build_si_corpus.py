"""
Build the Standing Interview corpus from the PRIVATE knowledge base.

WHY THIS EXISTS, AND WHY IT IS A SCRIPT AND NOT A COMMITTED FILE
Standing Interview must answer from the private books, and the books must
never enter this public repository. Those two constraints look contradictory
until you notice how this platform actually deploys: `railway up` uploads the
local WORKING DIRECTORY, not a fresh git clone (see
scripts/deploy_customer_app.sh's header, which documents that it does not even
include .git). So a directory that is gitignored here is still delivered to the
container.

That is the whole mechanism, and it is the smallest thing that works:

    private repo (books)  --this script-->  agent/.si_corpus/corpus.json
                                            (gitignored: never in git)
                                            --railway up--> container

Consequences, stated so nobody has to rediscover them:
  * The public repository contains ZERO book text. `git check-ignore` proves
    the output path is ignored, and a test asserts it.
  * `.dockerignore` must NOT exclude agent/.si_corpus/ or the image would
    build without a corpus. A test asserts that too.
  * The corpus is build-time data. If it is stale, Standing Interview answers
    from stale books -- so the corpus records the source book hashes, and the
    server reports them.
  * If the corpus is ABSENT, Standing Interview must say so honestly rather
    than answer from the model's own knowledge. That is enforced server-side,
    not here.

Vectors are computed HERE, on the machine that has the private books, and
shipped inside corpus.json. The container therefore never needs the books --
only the query embedding at runtime, which uses the same model and the same
agent/embeddings.py this repo already depends on.

Run:  python scripts/build_si_corpus.py
      python scripts/build_si_corpus.py --private-repo /path/to/context-repo
"""

import argparse
import hashlib
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "agent" / ".si_corpus"
OUT_PATH = OUT_DIR / "corpus.json"
# 2 (Sprint 13, BL-090): adds `career_map` and `attribution`. The server
# treats a corpus without them as no corpus at all, so a stale v1 file on a
# container cannot silently answer without the map.
CORPUS_FORMAT_VERSION = 2
CAREER_MAP_REL = pathlib.Path("books") / "SI_CAREER_MAP.md"

# The hands-on books each end in a technology attribution matrix:
#     <Technology>
#     Personal classification: HANDS-ON | USED/EXPOSED | NOT USED | ...
#     Safe interpretation: <one line>
# That table is the books' own answer to "where did he actually use X", so it
# is parsed into structured data here rather than left for the model to
# infer from prose. The vocabulary is normalised into four buckets; anything
# unrecognised is kept verbatim under bucket "OTHER" rather than guessed.
_CLASSIFICATION_RE = re.compile(r"^Personal classification:\s*(.+?)\s*$")
_INTERPRETATION_RE = re.compile(r"^Safe interpretation:\s*(.+?)\s*$")


def _bucket(classification: str) -> str:
    c = classification.upper()
    if c.startswith("HANDS-ON"):
        return "HANDS_ON"
    if c.startswith(("USED/EXPOSED", "MINOR EXPOSURE", "WEAK", "DOMAIN KNOWLEDGE", "POSSIBLE")):
        return "USED"
    if c.startswith(("NOT USED", "NOT SUPPORTED", "UNKNOWN")):
        return "NOT_USED"
    if "SYSTEM" in c:
        return "SYSTEM"
    return "OTHER"


def _parse_attribution(body: str) -> list[dict]:
    """Walk the derived text; a classification line binds to the nearest
    preceding non-empty line that is not a meta comment. When the matrix is
    split by a section heading, that heading IS the technology name."""
    out, prev, section = [], None, None
    for line in body.splitlines():
        t = line.strip()
        if not t:
            continue
        if t.startswith("## "):
            section = t[3:].strip()
            prev = None
            continue
        if t.startswith("<!--"):
            continue
        m = _CLASSIFICATION_RE.match(t)
        if m:
            tech = prev if prev is not None else section
            if tech:
                out.append({"tech": tech, "classification": m.group(1),
                            "bucket": _bucket(m.group(1)), "interpretation": ""})
            prev = None
            continue
        m = _INTERPRETATION_RE.match(t)
        if m and out and not out[-1]["interpretation"]:
            out[-1]["interpretation"] = m.group(1)
            prev = None
            continue
        prev = t
    return out


def _load_career_map(private_repo: pathlib.Path) -> str:
    path = private_repo / CAREER_MAP_REL
    if not path.is_file():
        raise SystemExit(
            f"FAIL: no career map at {path}.\n"
            "Sprint 13 (BL-090): every Standing Interview answer is generated with the "
            "standing career map in front of the model, so a corpus without one is "
            "refused here rather than shipped as a working corpus.")
    text = _FRONT_RE.sub("", path.read_text(encoding="utf-8")).strip()
    if len(text) < 500:
        raise SystemExit(f"FAIL: career map at {path} is implausibly short ({len(text)} chars).")
    return text

# Chunk sizing: derived book sections vary wildly, so cap by characters with a
# small overlap rather than trusting section length. 1800/200 keeps a chunk
# comfortably inside what a grounded answer can quote from without the model
# having to summarise across unrelated material.
MAX_CHARS = 1800
OVERLAP = 200

_META_RE = re.compile(r'<!--\s*(.*?)\s*-->')
_FRONT_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)


def _front_matter(text: str) -> dict:
    m = _FRONT_RE.match(text)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def _inline_meta(comment: str) -> dict:
    return dict(
        part.split("=", 1) for part in comment.split() if "=" in part
    )


def _split(text: str) -> list[str]:
    text = text.strip()
    if len(text) <= MAX_CHARS:
        return [text] if text else []
    out, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        if end < len(text):                      # break on a sentence if we can
            dot = text.rfind(". ", start + MAX_CHARS // 2, end)
            if dot != -1:
                end = dot + 1
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - OVERLAP)
    return [c for c in out if c]


def build(private_repo: pathlib.Path) -> dict:
    derived = private_repo / "books" / "derived"
    registry = private_repo / "books" / "REGISTRY.yaml"
    if not derived.is_dir():
        raise SystemExit(
            f"FAIL: no derived book text at {derived}.\n"
            "Standing Interview's corpus is built from the private knowledge base. "
            "Point --private-repo at it, or run its own `books.py derive` first."
        )

    import yaml
    reg = yaml.safe_load(registry.read_text(encoding="utf-8"))
    by_id = {e["book_id"]: e for e in reg["books"]}

    chunks = []
    for path in sorted(derived.glob("BOOK-*.md")):
        raw = path.read_text(encoding="utf-8")
        fm = _front_matter(raw)
        book_id = fm.get("book_id") or path.stem
        entry = by_id.get(book_id, {})
        body = _FRONT_RE.sub("", raw)

        section, meta, buf = "(front matter)", {}, []

        def flush():
            for piece in _split("\n".join(buf)):
                chunks.append({
                    "book_id": book_id,
                    "section": section,
                    "text": piece,
                    "employer": (entry.get("employer") or meta.get("employer") or "none"),
                    "knowledge_type": entry.get("knowledge_type", meta.get("knowledge_type", "")),
                    "work_type": entry.get("work_type", meta.get("work_type", "")),
                    "status": meta.get("status", "unspecified"),
                })

        for line in body.splitlines():
            if line.startswith("## "):
                flush()
                section, meta, buf = line[3:].strip(), {}, []
            elif line.strip().startswith("<!--"):
                m = _META_RE.search(line)
                if m:
                    meta = _inline_meta(m.group(1))
            else:
                buf.append(line)
        flush()

    if not chunks:
        raise SystemExit("FAIL: derived books produced zero chunks -- refusing to "
                         "write an empty corpus that would look like a working one.")

    # Attribution: only the personal hands-on employer books carry the matrix.
    attribution = {}
    for path in sorted(derived.glob("BOOK-*.md")):
        raw = path.read_text(encoding="utf-8")
        fm = _front_matter(raw)
        book_id = fm.get("book_id") or path.stem
        entry = by_id.get(book_id, {})
        if entry.get("knowledge_type") != "personal_hands_on" or not entry.get("employer"):
            continue
        rows = _parse_attribution(_FRONT_RE.sub("", raw))
        if rows:
            attribution[entry["employer"]] = rows
    if not attribution:
        raise SystemExit("FAIL: no attribution matrix parsed from any hands-on book -- "
                         "the only-where-used answer policy cannot run without it.")

    career_map = _load_career_map(private_repo)
    map_hash = hashlib.sha256(career_map.encode("utf-8")).hexdigest()

    sys.path.insert(0, str(REPO_ROOT / "agent"))
    import embeddings

    # Embedded in batches rather than one call. A single 361-chunk call was
    # silently KILLED on 2026-09-27 with the machine at 87% memory load and
    # under 2 GiB free -- no traceback, no output, no corpus, and (because the
    # shell reported the exit code of `tail` rather than python) an apparent
    # success. Batching bounds peak memory and prints progress, so a kill is
    # visible as a gap in the output instead of looking like a clean run.
    BATCH = 32
    vectors = []
    for i in range(0, len(chunks), BATCH):
        batch = [c["text"] for c in chunks[i:i + BATCH]]
        vectors.extend(embeddings.embed_texts(batch))
        print(f"  embedded {min(i + BATCH, len(chunks))}/{len(chunks)}", flush=True)
    if len(vectors) != len(chunks):
        raise SystemExit(f"FAIL: embedded {len(vectors)} vectors for {len(chunks)} chunks -- "
                         "refusing to write a partially-embedded corpus.")
    for c, v in zip(chunks, vectors):
        c["vector"] = v

    return {
        "format_version": CORPUS_FORMAT_VERSION,
        "model_id": embeddings.model_id(),
        "built_from": "private knowledge base, derived text",
        "source_book_hashes": {b: by_id[b]["sha256"] for b in sorted(by_id)},
        "chunk_count": len(chunks),
        "chunks": chunks,
        "career_map": career_map,
        "career_map_sha256": map_hash,
        "attribution": attribution,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--private-repo", default=str(REPO_ROOT.parent / "karthik-ai-context"))
    args = ap.parse_args()

    corpus = build(pathlib.Path(args.private_repo).expanduser().resolve())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(corpus), encoding="utf-8")

    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()[:16]
    per_book = {}
    for c in corpus["chunks"]:
        per_book[c["book_id"]] = per_book.get(c["book_id"], 0) + 1
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)}")
    print(f"  chunks     : {corpus['chunk_count']}  {dict(sorted(per_book.items()))}")
    print(f"  model_id   : {corpus['model_id']}")
    print(f"  career_map : {len(corpus['career_map']):,} chars  sha256: {corpus['career_map_sha256'][:16]}...")
    for emp, rows in sorted(corpus["attribution"].items()):
        buckets = {}
        for r in rows:
            buckets[r["bucket"]] = buckets.get(r["bucket"], 0) + 1
        print(f"  attribution: {emp:<6} {len(rows):>2} rows  {dict(sorted(buckets.items()))}")
    print(f"  bytes      : {OUT_PATH.stat().st_size:,}   sha256: {digest}...")
    print("\nThis file is GITIGNORED and must stay that way. It is delivered to the")
    print("container by `railway up`, which uploads the working directory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
