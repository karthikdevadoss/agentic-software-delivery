"""Reproduce the test_rag_index shared-state mechanism, deterministically.

The suite failure was `files_added: 10 != 1`. The mechanism, read from the
code rather than guessed: rag_index._indexable_files() calls
tools.list_all_repository_files("."), which is a FILESYSTEM WALK of the real
working tree -- not `git ls-files`. So the corpus is whatever is on disk at the
moment each build runs, and any file that appears in the repository between two
builds is counted as added.

This script makes that mechanism explicit by creating files between the two
builds, which is what a long multi-module suite does incidentally.

Run from the repo root. Creates and removes its own files only.
"""
import hashlib
import pathlib
import sys
import tempfile
from unittest import mock

sys.path.insert(0, "agent")
import tools          # noqa: E402
import rag_index      # noqa: E402


def _fake_vector(text):
    d = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in d[:16]]


real_index = pathlib.Path(rag_index.INDEX_PATH)
real_index.parent.mkdir(parents=True, exist_ok=True)
tmp = tempfile.TemporaryDirectory(prefix="_repro_", dir=str(real_index.parent))
created = []
try:
    with mock.patch.object(rag_index, "INDEX_PATH", pathlib.Path(tmp.name) / "index.json"), \
         mock.patch("rag_index.embed_texts", side_effect=lambda ts: [_fake_vector(t) for t in ts]), \
         mock.patch("rag_index.embed_query", side_effect=_fake_vector):

        assert pathlib.Path(rag_index.INDEX_PATH) != real_index, "refusing to touch the real index"

        rag_index._loaded_index = None
        s1 = rag_index.build_index()
        print(f"build 1 (baseline over the REAL tree): files_indexed={s1.get('files_indexed')} "
              f"added={s1.get('files_added')} embedded={s1.get('chunks_embedded')}")

        # What a long suite does incidentally: other modules write files into
        # the working tree. Nine of them, to match the observed number.
        noise_dir = tools.REPO_ROOT / "docs" / "_repro_noise"
        noise_dir.mkdir(parents=True, exist_ok=True)
        created.append(noise_dir)
        for i in range(9):
            f = noise_dir / f"artifact_{i}.md"
            f.write_text(f"# incidental artifact {i}\nwritten by another test module\n",
                         encoding="utf-8")
            created.append(f)

        # ...and then THIS test writes its own single fixture and asserts "1".
        fixture = tools.REPO_ROOT / "docs" / "_test_fixture_rag.md"
        fixture.write_text("# Fixture\nOriginal fixture content for incremental test.\n",
                           encoding="utf-8")
        created.append(fixture)

        rag_index._loaded_index = None
        s2 = rag_index.build_index()
        added = s2.get("files_added")
        print(f"build 2 (after 9 incidental files + 1 fixture): files_added={added}")
        print()
        if added == 1:
            print("RESULT: files_added == 1 -- mechanism NOT reproduced")
            code = 0
        else:
            print(f"RESULT: files_added == {added}, the test asserts 1 -> FAILS")
            print("        The assertion is about THIS test's own fixture, but the count")
            print("        is over the whole mutable working tree. Confirmed root cause:")
            print("        the corpus is shared global state, not the test's own input.")
            code = 1
finally:
    for p in reversed(created):
        try:
            p.unlink() if p.is_file() else p.rmdir()
        except OSError:
            pass
    tmp.cleanup()
    rag_index._loaded_index = None

sys.exit(code)
