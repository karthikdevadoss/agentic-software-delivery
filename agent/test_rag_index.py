"""
Focused automated tests for RAG indexing (agent/rag_index.py) — resolves
ACTION_QUEUE.json ACT-003 (RAG portion).

Embeddings are mocked (deterministic hash-based fake vectors, no real model
calls) so these tests are fast and need no network/model download. Real
retrieval quality against the actual fastembed model was verified manually
in-session (see docs/PROJECT_STATE.json verification_state); these tests
protect the indexing/incremental/ranking *logic* from regressing.

Automation Sprint 6: build/search tests index a TEMPORARY sandbox copy under
docs/, never the live repository tree, and write the index into a temporary
directory under agent/.rag_index/. Exclusion tests still call the real
scanner against the live tree (that is their job). The real
agent/.rag_index/index.json is never opened for writing.

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


def _fingerprint(path: pathlib.Path):
    if not path.exists():
        return None
    return (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())


class RagIndexExclusionTestCase(unittest.TestCase):
    """These must see the real repository tree — they assert production
    exclusion rules against live paths, not a sandbox."""

    def test_env_and_git_and_target_never_indexable(self):
        files = rag_index._indexable_files()
        self.assertFalse(any(f.endswith(".env") for f in files))
        self.assertFalse(any(f == ".git" or f.startswith(".git/") for f in files))
        self.assertFalse(any(f.startswith("target/") for f in files))

    def test_own_index_output_excluded_from_ingestion(self):
        files = rag_index._indexable_files()
        self.assertFalse(any("agent/.rag_index" in f for f in files))

    def test_claude_settings_excluded_from_ingestion(self):
        files = rag_index._indexable_files()
        self.assertFalse(any(f.startswith(".claude/") for f in files))


class RagIndexTestCase(unittest.TestCase):
    # ISOLATION BY CONSTRUCTION (2026-09-25, extended Automation Sprint 6).
    # INDEX_PATH + INDEX_DIR redirect into a temporary directory so the real
    # index is never opened for writing. Build/search tests further restrict
    # _indexable_files to a temporary sandbox under docs/, so build_index()
    # never walks or embeds the live repository.
    @classmethod
    def setUpClass(cls):
        cls._REAL_INDEX_PATH = pathlib.Path(rag_index.INDEX_PATH)
        cls._REAL_INDEX_DIR = pathlib.Path(rag_index.INDEX_DIR)
        cls._real_index_fingerprint = _fingerprint(cls._REAL_INDEX_PATH)
        real_index_dir = cls._REAL_INDEX_PATH.parent
        real_index_dir.mkdir(parents=True, exist_ok=True)
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="_test_", dir=str(real_index_dir))
        tmp_dir = pathlib.Path(cls._tmpdir.name)
        tmp_index = tmp_dir / "index.json"
        cls._index_path_patch = mock.patch.object(rag_index, "INDEX_PATH", tmp_index)
        cls._index_dir_patch = mock.patch.object(rag_index, "INDEX_DIR", tmp_dir)
        cls._index_path_patch.start()
        cls._index_dir_patch.start()
        assert rag_index.INDEX_PATH == tmp_index, "index path redirect failed"
        assert rag_index.INDEX_DIR == tmp_dir, "index dir redirect failed"
        assert "_test_" in pathlib.Path(rag_index.INDEX_PATH).parent.name, (
            f"not an isolated path: {rag_index.INDEX_PATH}"
        )
        assert pathlib.Path(rag_index.INDEX_PATH) != cls._REAL_INDEX_PATH, (
            "tests are pointed at the REAL index -- refusing to run"
        )

        # Temporary corpus copy under docs/ (inside REPO_ROOT so
        # Path.relative_to(REPO_ROOT) works; cleaned up in tearDownClass).
        docs_dir = tools.REPO_ROOT / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        cls._sandbox_tmpdir = tempfile.TemporaryDirectory(
            prefix="_test_rag_sandbox_", dir=str(docs_dir)
        )
        cls._sandbox_path = pathlib.Path(cls._sandbox_tmpdir.name)
        cls._sandbox_rel = str(cls._sandbox_path.relative_to(tools.REPO_ROOT)).replace("\\", "/")
        seed = cls._sandbox_path / "seed.md"
        seed.write_text("# Sandbox seed\nStable seed content for incremental reuse tests.\n", encoding="utf-8")
        cls.SEED_REL = f"{cls._sandbox_rel}/seed.md"
        cls.FIXTURE_PATH = cls._sandbox_path / "fixture.md"
        cls.FIXTURE_REL = f"{cls._sandbox_rel}/fixture.md"

    @classmethod
    def tearDownClass(cls):
        if cls.FIXTURE_PATH.exists():
            cls.FIXTURE_PATH.unlink()
        cls._index_path_patch.stop()
        cls._index_dir_patch.stop()
        cls._tmpdir.cleanup()
        cls._sandbox_tmpdir.cleanup()
        after = _fingerprint(cls._REAL_INDEX_PATH)
        assert after == cls._real_index_fingerprint, (
            f"real RAG index was modified by tests: before={cls._real_index_fingerprint} after={after}"
        )

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
        # Restrict the corpus to the temporary sandbox only.
        files_patch = mock.patch.object(
            rag_index, "_indexable_files", side_effect=self._sandbox_indexable_files
        )
        files_patch.start()
        self.addCleanup(files_patch.stop)
        self.addCleanup(self._cleanup_fixture)

    def _sandbox_indexable_files(self):
        allowed = tools.ALLOWED_READ_EXTENSIONS
        out = []
        for p in sorted(self._sandbox_path.rglob("*")):
            if p.is_file() and p.suffix.lower() in allowed:
                out.append(str(p.relative_to(tools.REPO_ROOT)).replace("\\", "/"))
        return out

    def _cleanup_fixture(self):
        if self.FIXTURE_PATH.exists():
            self.FIXTURE_PATH.unlink()
        rag_index._loaded_index = None

    def _write_fixture(self, content: str):
        self.FIXTURE_PATH.write_text(content, encoding="utf-8")

    # --- no secret indexing ---------------------------------------------

    def test_indexed_text_is_redacted(self):
        self._write_fixture("ANTHROPIC_API_KEY=sk-ant-api03-thisisatestsecretvalue1234567890\n")
        text = rag_index._read_indexable_text(self.FIXTURE_REL)
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
        self.assertNotIn(self.FIXTURE_REL, index["files"])

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
        distinctive_text = "zzzz_unique_fixture_marker_for_ranking_test_zzzz"
        self._write_fixture(distinctive_text + "\n")
        rag_index.build_index()
        results = rag_index.semantic_search(distinctive_text, top_k=3)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["path"], self.FIXTURE_REL)
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
        stats = rag_index.build_index()
        self.assertTrue(stats["full_rebuild"])


if __name__ == "__main__":
    unittest.main()
