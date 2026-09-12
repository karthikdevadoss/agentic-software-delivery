"""
Focused tests for agent/learn_pdf.py — the downloadable Learn PDF book
(P0-C), generated from the SAME canonical learn-tree.json the interactive
UI uses.

Run: python agent/test_learn_pdf.py
"""

import io
import unittest
from pathlib import Path

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


class MasterInterviewBookTestCase(unittest.TestCase):
    """P0 'JOB-FIRST MASTER INTERVIEW BOOK V1' -- programmatic validation
    so PDF defects are caught by the test suite, never discovered manually
    by the Owner (P0_PROMPT.txt Section 13)."""

    @classmethod
    def setUpClass(cls):
        cls.pdf_bytes, _, _ = learn_pdf.get_or_generate_pdf()
        cls.reader = PdfReader(io.BytesIO(cls.pdf_bytes))
        cls.pages_text = [p.extract_text() or "" for p in cls.reader.pages]
        cls.text = "\n".join(cls.pages_text)

    def test_page_size_is_a4(self):
        box = self.reader.pages[0].mediabox
        self.assertAlmostEqual(float(box.width), 595.27, delta=2)
        self.assertAlmostEqual(float(box.height), 841.89, delta=2)

    def test_every_page_has_a_matching_sequential_page_number(self):
        import re
        for i, text in enumerate(self.pages_text):
            self.assertRegex(text, r"Page " + str(i + 1) + r"\b",
                              f"page {i + 1} is missing its own footer page number")

    def test_front_matter_present(self):
        for marker in ("How to Use This Book", "2-Day Priority Reading Path",
                        "Fast Interview Revision Path", "Domain Index",
                        "Labels Used in This Book"):
            self.assertIn(marker, self.text)

    def test_all_13_new_broad_domains_present(self):
        for domain in ("Java Core", "JVM Internals", "Spring / Spring Boot",
                        "Database / SQL / JPA", "REST / API Design",
                        "Microservices / Distributed Systems", "Redis / Caching",
                        "Kafka / Event-Driven Architecture", "Application Security",
                        "Testing / Quality", "Observability / Production",
                        "Cloud / DevOps", "Architecture & Delivery Leadership"):
            self.assertIn(domain, self.text)

    def test_17_part_schema_labels_present(self):
        for label in ("HISTORY & EVOLUTION", "WHY NOW / WHEN", "BIG-PICTURE SYSTEM DESIGN",
                       "DESIGN INTELLECT", "HOW EXACTLY", "LOW-LEVEL INTERNALS",
                       "INDUSTRY KNOWLEDGE", "BUSINESS KNOWLEDGE", "PRODUCT KNOWLEDGE",
                       "COST / ECONOMICS / PROFIT", "FAILURE / INCIDENT",
                       "ALTERNATIVES / TRADE-OFFS", "CURRENT INDUSTRY STATUS"):
            self.assertIn(label, self.text)

    def test_priority_and_classification_tags_present(self):
        for tag in ("INTERVIEW ESSENTIAL", "STUDY SCENARIO", "CURRENT PROJECT EXPERIENCE"):
            self.assertIn(tag, self.text)

    def test_no_fabricated_real_professional_experience_claim(self):
        # The front-matter legend legitimately NAMES the label to explain
        # it, so this checks the canonical tree's own metrics (no node is
        # ever actually tagged with it) rather than raw PDF text.
        import learn_tree
        metrics = learn_tree.load_tree()["metrics"]
        self.assertEqual(metrics.get("real_professional_experience_topics"), 0)

    def test_no_literal_html_entities_leaked(self):
        import re
        leaked = re.findall(r"&amp;amp;|&lt;[a-z]|&gt;[a-z]", self.text)
        self.assertEqual(leaked, [])

    def test_no_mojibake_replacement_characters(self):
        self.assertNotIn("�", self.text)

    def test_no_named_html_entities_other_than_the_escaping_triad(self):
        # Real defect found by independent QA (2026-09-12): a named entity
        # like &bull; has no guaranteed ToUnicode mapping in reportlab's
        # generated PDF, so some extractors (PyMuPDF) decode it as U+FFFD
        # while others (pypdf) decode it as a control character -- neither
        # of which this test's own sibling check above happens to catch,
        # since it only looks for the literal U+FFFD glyph under pypdf's
        # specific decode path. The real fix is structural: learn_pdf.py's
        # Paragraph markup must only ever contain a real literal Unicode
        # character (e.g. the actual "•" bullet), never a named HTML
        # entity, except the three produced by _esc()'s own escaping
        # (&amp; &lt; &gt;). This statically guards the source itself so
        # the defect class can't quietly return via a different entity.
        import re
        source = (Path(__file__).resolve().parent / "learn_pdf.py").read_text(encoding="utf-8")
        named_entities = set(re.findall(r"&(?!amp;|lt;|gt;)[a-zA-Z]+;", source))
        self.assertEqual(named_entities, set(),
                          f"found named HTML entities with no guaranteed PDF ToUnicode "
                          f"mapping: {named_entities} -- use a real literal Unicode "
                          f"character instead")

    def test_interview_mode_answers_present(self):
        for label in ("15-SECOND ANSWER", "30-SECOND ANSWER", "2-MINUTE ANSWER"):
            self.assertIn(label, self.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
