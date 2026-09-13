"""
Focused tests for the curated backend RAG index (agent/backend_rag_index.py):
ingestion, chunking (Java/Markdown/JSON), embedding integration, and
retrieval. Covers the RAG unit-test categories from the P0 RAG/MCP/Evals
task: ingestion, chunking, embeddings, retrieval, context builder.

Run: python agent/test_backend_rag_index.py
"""

import unittest
from unittest import mock

import backend_rag_corpus
import backend_rag_index as bi


class JavaChunkingTestCase(unittest.TestCase):
    SAMPLE = (
        "package com.example.demo;\n"
        "\n"
        "import java.util.List;\n"
        "\n"
        "public class Sample {\n"
        "\n"
        "    private final String name;\n"
        "\n"
        "    public Sample(String name) {\n"
        "        this.name = name;\n"
        "    }\n"
        "\n"
        "    public String getName() {\n"
        "        return name;\n"
        "    }\n"
        "}\n"
    )

    def test_no_empty_chunks(self):
        chunks = bi.chunk_document("java", self.SAMPLE)
        self.assertTrue(all(c["text"].strip() for c in chunks))

    def test_header_chunk_contains_package_and_class_decl(self):
        chunks = bi.chunk_document("java", self.SAMPLE)
        header = chunks[0]
        self.assertEqual(header["symbol"], "class_header")
        self.assertIn("package com.example.demo;", header["text"])
        self.assertIn("public class Sample {", header["text"])

    def test_each_method_becomes_its_own_chunk_with_correct_symbol(self):
        chunks = bi.chunk_document("java", self.SAMPLE)
        symbols = [c["symbol"] for c in chunks]
        self.assertIn("Sample", symbols)  # constructor
        self.assertIn("getName", symbols)

    def test_field_declaration_is_its_own_chunk(self):
        chunks = bi.chunk_document("java", self.SAMPLE)
        field_chunk = next(c for c in chunks if c["symbol"] == "name")
        self.assertIn("private final String name;", field_chunk["text"])

    def test_line_ranges_preserved_and_non_overlapping_boundaries(self):
        chunks = bi.chunk_document("java", self.SAMPLE)
        for c in chunks:
            self.assertIsNotNone(c["start_line"])
            self.assertIsNotNone(c["end_line"])
            self.assertLessEqual(c["start_line"], c["end_line"])

    def test_no_class_found_falls_back_to_whole_file_chunk(self):
        chunks = bi.chunk_document("java", "// just a comment\nint x = 1;\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["symbol"], "whole_file")

    def test_deterministic_chunk_ids_for_same_content(self):
        c1 = bi.chunk_document("java", self.SAMPLE)
        c2 = bi.chunk_document("java", self.SAMPLE)
        self.assertEqual([c["symbol"] for c in c1], [c["symbol"] for c in c2])


class MarkdownChunkingTestCase(unittest.TestCase):
    SAMPLE = (
        "# Title\n"
        "intro text\n"
        "## Section A\n"
        "content A\n"
        "### Subsection A.1\n"
        "deep content\n"
        "## Section B\n"
        "content B\n"
    )

    def test_headings_become_chunk_symbols(self):
        chunks = bi.chunk_document("markdown", self.SAMPLE)
        symbols = [c["symbol"] for c in chunks]
        self.assertIn("Title", symbols)
        self.assertIn("Section A", symbols)
        self.assertIn("Subsection A.1", symbols)
        self.assertIn("Section B", symbols)

    def test_section_content_stays_with_its_heading(self):
        chunks = bi.chunk_document("markdown", self.SAMPLE)
        section_a = next(c for c in chunks if c["symbol"] == "Section A")
        self.assertIn("content A", section_a["text"])
        self.assertNotIn("content B", section_a["text"])

    def test_no_empty_chunks(self):
        chunks = bi.chunk_document("markdown", "# Empty\n## Also Empty\n")
        self.assertTrue(all(c["text"].strip() for c in chunks))

    def test_no_headings_produces_one_front_matter_chunk(self):
        chunks = bi.chunk_document("markdown", "just plain text\nmore text\n")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["symbol"], "(front matter)")


class JsonCatalogueChunkingTestCase(unittest.TestCase):
    def test_each_item_becomes_its_own_chunk(self):
        text = '{"items": [{"id": "A-1", "x": 1}, {"id": "A-2", "x": 2}]}'
        chunks = bi.chunk_document("json", text)
        self.assertEqual({c["symbol"] for c in chunks}, {"A-1", "A-2"})

    def test_malformed_json_falls_back_to_whole_file_chunk(self):
        chunks = bi.chunk_document("json", "{not valid json")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["symbol"], "whole_file")

    def test_missing_items_key_falls_back_to_whole_file_chunk(self):
        chunks = bi.chunk_document("json", '{"other": "shape"}')
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["symbol"], "whole_file")


class SubSplitTestCase(unittest.TestCase):
    def test_large_chunk_is_sub_split_with_bounded_size(self):
        big_text = "\n".join(f"line {i}" for i in range(300))
        chunk = {"symbol": "big", "start_line": 1, "end_line": 300, "text": big_text}
        parts = bi._sub_split_if_large(chunk)
        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLessEqual(len(p["text"].splitlines()), bi.SUB_WINDOW_LINES)
            self.assertTrue(p["symbol"].startswith("big::part"))

    def test_small_chunk_is_not_split(self):
        chunk = {"symbol": "small", "start_line": 1, "end_line": 3, "text": "a\nb\nc"}
        parts = bi._sub_split_if_large(chunk)
        self.assertEqual(parts, [chunk])

    def test_chunk_with_no_line_range_is_never_split(self):
        big_text = "\n".join(f"line {i}" for i in range(300))
        chunk = {"symbol": "json_item", "start_line": None, "end_line": None, "text": big_text}
        parts = bi._sub_split_if_large(chunk)
        self.assertEqual(parts, [chunk])


class CorpusExclusionTestCase(unittest.TestCase):
    def test_curated_corpus_documents_all_have_a_registered_chunker(self):
        for doc in backend_rag_corpus.CORPUS_DOCUMENTS:
            self.assertIn(doc.content_type, bi._CHUNKERS)

    def test_curated_corpus_paths_are_repo_relative_and_exist(self):
        for doc in backend_rag_corpus.CORPUS_DOCUMENTS:
            resolved = bi.tools.REPO_ROOT / doc.source_path
            self.assertTrue(resolved.exists(), f"{doc.source_path} does not exist")


class ReadCuratedDocumentTestCase(unittest.TestCase):
    def test_secret_like_assignment_is_redacted(self):
        fake_path = mock.MagicMock()
        fake_path.suffix = ".properties"
        fake_path.exists.return_value = True
        fake_path.is_file.return_value = True
        fake_path.read_text.return_value = 'api_key = "abcdef1234567890"\n'
        widened_extensions = bi.tools.ALLOWED_READ_EXTENSIONS | {".properties"}
        with mock.patch.object(bi.tools, "_resolve_safe_path", return_value=fake_path), \
             mock.patch.object(bi.tools, "ALLOWED_READ_EXTENSIONS", widened_extensions):
            text = bi._read_curated_document("fake.properties")
        self.assertNotIn("abcdef1234567890", text)

    def test_disallowed_extension_rejected(self):
        with self.assertRaises(bi.tools.RepoToolError):
            bi._read_curated_document("agent/.env")

    def test_traversal_path_rejected_reuses_shared_security_boundary(self):
        with self.assertRaises(bi.tools.RepoToolError):
            bi._read_curated_document("../../etc/passwd")


class RetrievalTestCase(unittest.TestCase):
    """Uses a small synthetic in-memory index (never touches the real
    persisted .backend_rag_index/index.json) so these tests are fast,
    deterministic, and independent of the real curated corpus content."""

    def setUp(self):
        bi.invalidate_cache()
        self._orig_loaded = bi._loaded_index
        bi._loaded_index = {
            "model_id": bi.model_id(),
            "chunking_version": bi._chunking_version(),
            "documents": {},
            "chunks": {
                "docA::m1": {
                    "source_path": "docA.java", "source_type": "SOURCE_CODE", "symbol": "m1",
                    "start_line": 1, "end_line": 3, "content": "customer lookup logic",
                    "vector": [1.0, 0.0, 0.0],
                },
                "docB::m2": {
                    "source_path": "docB.md", "source_type": "ARCHITECTURE_DOC", "symbol": "m2",
                    "start_line": None, "end_line": None, "content": "deployment verification rules",
                    "vector": [0.0, 1.0, 0.0],
                },
            },
        }

    def tearDown(self):
        bi._loaded_index = self._orig_loaded

    def test_top_k_is_respected(self):
        with mock.patch("backend_rag_index.embed_query", return_value=[1.0, 0.0, 0.0]):
            results = bi.semantic_search("customer", top_k=1)
        self.assertEqual(len(results), 1)

    def test_metadata_returned_on_every_result(self):
        with mock.patch("backend_rag_index.embed_query", return_value=[1.0, 0.0, 0.0]):
            results = bi.semantic_search("customer", top_k=2)
        for key in ("rank", "score", "chunk_id", "source_path", "source_type", "symbol",
                    "start_line", "end_line", "content"):
            self.assertIn(key, results[0])

    def test_source_type_filter_narrows_results(self):
        with mock.patch("backend_rag_index.embed_query", return_value=[0.5, 0.5, 0.0]):
            results = bi.semantic_search("anything", top_k=5, source_type="ARCHITECTURE_DOC")
        self.assertTrue(all(r["source_type"] == "ARCHITECTURE_DOC" for r in results))
        self.assertEqual(len(results), 1)

    def test_empty_source_type_filter_match_returns_empty_list(self):
        with mock.patch("backend_rag_index.embed_query", return_value=[1.0, 0.0, 0.0]):
            results = bi.semantic_search("anything", top_k=5, source_type="TEST")
        self.assertEqual(results, [])

    def test_similarity_ordering_is_descending(self):
        with mock.patch("backend_rag_index.embed_query", return_value=[0.9, 0.1, 0.0]):
            results = bi.semantic_search("customer-ish", top_k=2)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_model_mismatch_raises_clear_error(self):
        bi._loaded_index["model_id"] = "some-other-model"
        with self.assertRaises(RuntimeError):
            bi.semantic_search("customer")


if __name__ == "__main__":
    unittest.main()
