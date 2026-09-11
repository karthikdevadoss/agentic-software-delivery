"""
Focused tests for agent/learn_pdf.py — the downloadable Learn PDF book
(P0-C), generated from the SAME canonical learn-tree.json the interactive
UI uses.

Run: python agent/test_learn_pdf.py
"""

import io
import unittest

import learn_pdf
from pypdf import PdfReader


class PdfGenerationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_bytes, cls.generated_at, cls.is_fresh = learn_pdf.get_or_generate_pdf()
        cls.reader = PdfReader(io.BytesIO(cls.pdf_bytes))
        cls.text = "\n".join(p.extract_text() or "" for p in cls.reader.pages)

    def test_pdf_is_non_empty_and_real_pdf(self):
        self.assertGreater(len(self.pdf_bytes), 1000)
        self.assertTrue(self.pdf_bytes.startswith(b"%PDF-"))

    def test_pdf_has_multiple_pages(self):
        self.assertGreater(len(self.reader.pages), 5)

    def test_pdf_contains_canonical_domains_and_topics(self):
        for term in ("System Design", "Connection Pooling", "HikariCP", "AI-Assisted Software Engineering"):
            self.assertIn(term, self.text)

    def test_pdf_hierarchy_order_preserved_domain_before_child(self):
        idx_domain = self.text.find("System Design")
        idx_child = self.text.find("Connection Pooling")
        self.assertGreater(idx_child, idx_domain)

    def test_pdf_contains_what_why_how_when_sections(self):
        for label in ("WHAT", "WHY", "HOW", "WHEN"):
            self.assertIn(label, self.text)

    def test_pdf_contains_development_steps_section(self):
        self.assertIn("DEVELOPMENT STEPS", self.text)

    def test_pdf_contains_interview_section(self):
        self.assertIn("INTERVIEW PREPARATION", self.text)

    def test_pdf_contains_metadata_and_git_commit(self):
        self.assertIn("Generated:", self.text)
        self.assertIn("Knowledge version (git commit):", self.text)

    def test_pdf_contains_no_known_secret_shaped_strings(self):
        # Never generated from raw telemetry/secrets -- purely from the
        # authored/migrated tree -- so no API-key-shaped or .env content
        # should ever appear.
        lowered = self.text.lower()
        for bad in ("sk-ant-", "anthropic_api_key", "database_url=", "railway_token"):
            self.assertNotIn(bad, lowered)

    def test_missing_optional_sections_do_not_break_generation(self):
        # Real leaf topics (e.g. plain reference-catalog entries) have
        # only a 'what' section and no development_steps/interview at
        # all -- if generation reached this point without raising, that
        # already proves this; assert at least one such sparse topic's
        # title made it into the document.
        self.assertIn("Machine Learning", self.text)  # a plain reference-catalog leaf

    def test_cache_is_reused_when_tree_unchanged(self):
        _, _, is_fresh_again = learn_pdf.get_or_generate_pdf()
        self.assertFalse(is_fresh_again)


if __name__ == "__main__":
    unittest.main(verbosity=2)
