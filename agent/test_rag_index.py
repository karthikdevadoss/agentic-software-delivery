"""
Focused automated tests for RAG indexing (agent/rag_index.py) — resolves
ACTION_QUEUE.json ACT-003 (RAG portion).

Embeddings are mocked (deterministic hash-based fake vectors, no real model
calls) so these tests are fast and need no network/model download. Real
retrieval quality against the actual fastembed model was verified manually
in-session (see docs/PROJECT_STATE.json verification_state); these tests
protect the indexing/incremental/ranking *logic* from regressing.

These tests operate on the real project repository (tools.py's REPO_ROOT is
fixed at import time, not sandboxed) using a small, clearly-named,
self-cleaning fixture file, and back up/restore the real RAG index around
the run so the actual project index is left exactly as found.

Run: python agent/test_rag_index.py
"""

import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest import mock

import tools
import rag_index


def _fake_vector(text: str) -> list:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in digest[:16]]


def _fake_embed_texts(texts):
    return [_fake_vector(t) for t in texts]


def _fake_embed_query(text):
    return _fake_vector(text)


class RagIndexTestCase(unittest.TestCase):
    FIXTURE_PATH = tools.REPO_ROOT / "docs" / "_test_fixture_rag.md"

    # ISOLATION BY CONSTRUCTION (2026-09-25). This class used to back up the
    # REAL agent/.rag_index/index.json in setUpClass and restore it in
    # tearDownClass, while patching in a 16-dimensional fake embedder. That is
    # safe only if teardown always runs -- and it does not. A timeout, Ctrl-C,
    # CI step cancellation or crash skips tearDownClass and leaves the real
    # index holding 16-dim fake vectors written under the REAL model's id.
    #
    # That is not hypothetical: it happened on 2026-09-25 when this module was
    # killed by a 25s survey timeout. The damage was invisible to both existing
    # guards -- the model_id check passed (the fake vectors were stored under
    # `local:BAAI/bge-small-en-v1.5`), and incremental rebuild reused them
    # because the content hashes were unchanged (`embedded=0`). Semantic search
    # then failed with a 384-vs-16 matmul error until a full delete+rebuild.
    #
    # The fix is isolation, not better cleanup: INDEX_PATH is redirected into a
    # temporary directory for the whole class, so the real index is never
    # opened for writing at all. Teardown failing can no longer corrupt
    # anything, because there is nothing real in scope to corrupt.
    @classmethod
    def setUpClass(cls):
        # The temp dir is nested INSIDE the real .rag_index/ directory, which
        # is deliberate and took two attempts to get right:
        #   - OS temp dir (outside the repo) breaks 8 tests: production code
        #     calls Path.relative_to(REPO_ROOT) and raises "not in the subpath of".
        #   - A sibling dir inside the repo breaks 4 tests: the indexer's own
        #     ingestion-exclusion rule matches the literal prefix "agent/.rag_index",
        #     so a sibling like agent/.rag_index_test_x is NOT excluded and the
        #     indexer starts ingesting its own test fixtures.
        # Nesting under .rag_index/ satisfies all three constraints at once:
        # inside the repo, already covered by the exclusion rule, and separate
        # from the real index.json that must never be written by a test.
        cls._REAL_INDEX_PATH = pathlib.Path(rag_index.INDEX_PATH)
        real_index_dir = cls._REAL_INDEX_PATH.parent
        real_index_dir.mkdir(parents=True, exist_ok=True)
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="_test_", dir=str(real_index_dir))
        tmp_index = pathlib.Path(cls._tmpdir.name) / "index.json"
        cls._index_patch = mock.patch.object(rag_index, "INDEX_PATH", tmp_index)
        cls._index_patch.start()
        # Fail loudly rather than silently testing the wrong thing if the
        # redirect ever stops working (e.g. the module starts capturing the
        # path at import time instead of reading the attribute).
        assert rag_index.INDEX_PATH == tmp_index, "index path redirect failed"
        assert "_test_" in pathlib.Path(rag_index.INDEX_PATH).parent.name, (
            f"not an isolated path: {rag_index.INDEX_PATH}"
        )
        assert pathlib.Path(rag_index.INDEX_PATH) != cls._REAL_INDEX_PATH, (
            "tests are pointed at the REAL index -- refusing to run"
        )

    @classmethod
    def tearDownClass(cls):
        if cls.FIXTURE_PATH.exists():
            cls.FIXTURE_PATH.unlink()
        cls._index_patch.stop()
        cls._tmpdir.cleanup()

    def setUp(self):
        rag_index._loaded_index = None
        if self.FIXTURE_PATH.exists():
            self.FIXTURE_PATH.unlink()
        patch_texts = mock.patch("rag_index.embed_texts", side_effect=_fake_embed_texts)
        patch_query = mock.patch("rag_index.embed_query", side_effect=_fake_embed_query)
        patch_texts.start()
        patch_query.start()
        self.addCleanup(patch_texts.stop)
        self.addCleanup(patch_query.stop)
        self.addCleanup(self._cleanup_fixture)

    def _cleanup_fixture(self):
        if self.FIXTURE_PATH.exists():
            self.FIXTURE_PATH.unlink()
        rag_index._loaded_index = None

    def _write_fixture(self, content: str):
        self.FIXTURE_PATH.write_text(content, encoding="utf-8")

    # --- exclusion behavior -------------------------------------------

    def test_env_and_git_and_target_never_indexable(self):
        files = rag_index._indexable_files()
        self.assertFalse(any(f.endswith(".env") for f in files))
        # Precise check for the .git internal directory as a real path
        # segment — a bare ".git" substring also matches legitimate,
        # correctly-indexable files like .github/workflows/ci.yml or
        # .gitattributes.
        self.assertFalse(any(f == ".git" or f.startswith(".git/") for f in files))
        self.assertFalse(any(f.startswith("target/") for f in files))

    def test_own_index_output_excluded_from_ingestion(self):
        files = rag_index._indexable_files()
        self.assertFalse(any("agent/.rag_index" in f for f in files))

    def test_claude_settings_excluded_from_ingestion(self):
        files = rag_index._indexable_files()
        self.assertFalse(any(f.startswith(".claude/") for f in files))

    # --- no secret indexing ---------------------------------------------

    def test_indexed_text_is_redacted(self):
        self._write_fixture("ANTHROPIC_API_KEY=sk-ant-api03-thisisatestsecretvalue1234567890\n")
        text = rag_index._read_indexable_text("docs/_test_fixture_rag.md")
        self.assertNotIn("sk-ant-api03-thisisatestsecretvalue1234567890", text)
        self.assertIn("REDACTED", text)

    # --- incremental reuse / change / deletion ---------------------------

    def test_second_build_with_no_changes_embeds_nothing(self):
        rag_index.build_index()
        stats = rag_index.build_index()
        self.assertEqual(stats["chunks_embedded"], 0)
        self.assertFalse(stats["full_rebuild"])
        self.assertGreater(stats["chunks_reused"], 0)

    def test_new_file_triggers_only_that_files_embedding(self):
        rag_index.build_index()
        self._write_fixture("# Fixture\nOriginal fixture content for incremental test.\n")
        stats = rag_index.build_index()
        self.assertEqual(stats["files_added"], 1)
        self.assertEqual(stats["files_changed"], 0)
        self.assertGreater(stats["chunks_embedded"], 0)
        self.assertFalse(stats["full_rebuild"])

    def test_changed_file_reembeds_only_that_file(self):
        self._write_fixture("# Fixture\nOriginal fixture content.\n")
        rag_index.build_index()
        self._write_fixture("# Fixture\nCHANGED fixture content, different text entirely.\n")
        stats = rag_index.build_index()
        self.assertEqual(stats["files_changed"], 1)
        self.assertEqual(stats["files_added"], 0)
        self.assertGreater(stats["chunks_embedded"], 0)

    def test_deleted_file_removed_from_index(self):
        self._write_fixture("# Fixture\nWill be deleted.\n")
        rag_index.build_index()
        self.FIXTURE_PATH.unlink()
        stats = rag_index.build_index()
        self.assertEqual(stats["files_deleted"], 1)
        self.assertGreater(stats["chunks_removed"], 0)
        index = json.loads(rag_index.INDEX_PATH.read_text(encoding="utf-8"))
        self.assertNotIn("docs/_test_fixture_rag.md", index["files"])

    # --- provider/model + chunking incompatibility -----------------------

    def test_model_change_forces_full_rebuild(self):
        rag_index.build_index()
        with mock.patch("rag_index.model_id", return_value="different-model-id"):
            stats = rag_index.build_index()
            self.assertTrue(stats["full_rebuild"])
            self.assertIn("model", stats["rebuild_reason"])

    def test_chunking_version_change_forces_full_rebuild(self):
        rag_index.build_index()
        with mock.patch("rag_index._chunking_version", return_value="different-chunking"):
            stats = rag_index.build_index()
            self.assertTrue(stats["full_rebuild"])
            self.assertIn("chunking", stats["rebuild_reason"])

    # --- ranking -----------------------------------------------------

    def test_semantic_search_ranks_identical_text_highest(self):
        # Our fake embedding is a content hash with no partial-similarity
        # structure (unlike a real embedding model), so the fixture's chunk
        # text must exactly match the query for a guaranteed top score —
        # this tests the ranking/argsort mechanism, not semantic quality
        # (semantic quality was verified manually against the real model).
        distinctive_text = "zzzz_unique_fixture_marker_for_ranking_test_zzzz"
        self._write_fixture(distinctive_text + "\n")
        rag_index.build_index()
        results = rag_index.semantic_search(distinctive_text, top_k=3)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["path"], "docs/_test_fixture_rag.md")
        for a, b in zip(results, results[1:]):
            self.assertGreaterEqual(a["score"], b["score"])

    # --- corrupt/missing index safety --------------------------------

    def test_missing_index_raises_clear_error_not_crash(self):
        if rag_index.INDEX_PATH.exists():
            rag_index.INDEX_PATH.unlink()
        rag_index._loaded_index = None
        with self.assertRaises(RuntimeError) as ctx:
            rag_index.semantic_search("anything")
        self.assertIn("No RAG index found", str(ctx.exception))

    def test_corrupt_index_treated_as_missing_not_a_crash(self):
        rag_index.INDEX_DIR.mkdir(parents=True, exist_ok=True)
        rag_index.INDEX_PATH.write_text("{not valid json!!!", encoding="utf-8")
        rag_index._loaded_index = None
        with self.assertRaises(RuntimeError):
            rag_index.semantic_search("anything")
        # build_index() must recover with a full rebuild, not crash
        stats = rag_index.build_index()
        self.assertTrue(stats["full_rebuild"])


if __name__ == "__main__":
    unittest.main()
