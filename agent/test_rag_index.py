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

    @classmethod
    def setUpClass(cls):
        cls._index_backup = (
            rag_index.INDEX_PATH.read_text(encoding="utf-8")
            if rag_index.INDEX_PATH.exists() else None
        )

    @classmethod
    def tearDownClass(cls):
        if cls.FIXTURE_PATH.exists():
            cls.FIXTURE_PATH.unlink()
        if cls._index_backup is not None:
            rag_index.INDEX_PATH.write_text(cls._index_backup, encoding="utf-8")
        elif rag_index.INDEX_PATH.exists():
            rag_index.INDEX_PATH.unlink()

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
        self.assertFalse(any(".git" in f for f in files))
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
