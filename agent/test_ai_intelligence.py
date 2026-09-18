import shutil
import unittest
from pathlib import Path

import ai_intelligence


class AiIntelligenceTestCase(unittest.TestCase):
    def setUp(self):
        self._orig_dir = ai_intelligence.DAILY_DIR
        self._tmp_dir = Path(__file__).resolve().parent / "_tmp_ai_intelligence_test"
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)
        self._tmp_dir.mkdir(parents=True)
        ai_intelligence.DAILY_DIR = self._tmp_dir

    def tearDown(self):
        ai_intelligence.DAILY_DIR = self._orig_dir
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)

    def test_list_dates_empty_when_directory_missing(self):
        shutil.rmtree(self._tmp_dir)
        self.assertEqual(ai_intelligence.list_dates(), [])

    def test_list_dates_empty_when_directory_exists_but_has_no_files(self):
        self.assertEqual(ai_intelligence.list_dates(), [])

    def test_list_dates_ignores_non_dated_files(self):
        (self._tmp_dir / "README.md").write_text("not a dated file", encoding="utf-8")
        (self._tmp_dir / "2026-09-15.md").write_text("real", encoding="utf-8")
        self.assertEqual(ai_intelligence.list_dates(), ["2026-09-15"])

    def test_list_dates_sorted_newest_first(self):
        for d in ("2026-09-10", "2026-09-17", "2026-09-13"):
            (self._tmp_dir / f"{d}.md").write_text("x", encoding="utf-8")
        self.assertEqual(
            ai_intelligence.list_dates(), ["2026-09-17", "2026-09-13", "2026-09-10"]
        )

    def test_read_day_returns_none_for_missing_file(self):
        self.assertIsNone(ai_intelligence.read_day("2026-01-01"))

    def test_read_day_rejects_a_path_traversal_attempt(self):
        # A real security boundary, not just a happy-path convenience --
        # the date regex must reject anything that isn't a bare YYYY-MM-DD,
        # since this value flows straight into a filesystem path.
        (self._orig_dir.parent).mkdir(parents=True, exist_ok=True)
        self.assertIsNone(ai_intelligence.read_day("../../etc/passwd"))
        self.assertIsNone(ai_intelligence.read_day("2026-09-15/../../../secret"))

    def test_read_day_returns_real_content(self):
        (self._tmp_dir / "2026-09-15.md").write_text("## Heading\nbody text", encoding="utf-8")
        self.assertEqual(
            ai_intelligence.read_day("2026-09-15"), "## Heading\nbody text"
        )

    def test_parse_sections_splits_on_h2_headers(self):
        md = "## First\nline one\nline two\n\n## Second\nline three\n"
        sections = ai_intelligence.parse_sections(md)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["heading"], "First")
        self.assertIn("line one", sections[0]["body"])
        self.assertEqual(sections[1]["heading"], "Second")
        self.assertIn("line three", sections[1]["body"])

    def test_parse_sections_ignores_content_before_first_header(self):
        md = "some preamble\n## Real Section\nreal body\n"
        sections = ai_intelligence.parse_sections(md)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["heading"], "Real Section")

    def test_parse_sections_drops_empty_sections(self):
        md = "## Empty\n\n## HasContent\nsomething real\n"
        sections = ai_intelligence.parse_sections(md)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["heading"], "HasContent")

    def test_parse_sections_empty_markdown_returns_empty_list(self):
        self.assertEqual(ai_intelligence.parse_sections(""), [])


if __name__ == "__main__":
    unittest.main()
