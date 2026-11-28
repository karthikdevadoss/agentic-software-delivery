"""Hermetic checks for /how-i-build (2026-11-28).

Every claim on the page points at evidence, so the evidence must exist: each
repository file it links to is a real file, each pull request it cites is one
whose number exists in the committed GitHub snapshot or is recent, the route is
wired, and the authorship statement stays honest.
"""
from __future__ import annotations

import pathlib
import re
import unittest

AGENT = pathlib.Path(__file__).resolve().parent
REPO = AGENT.parent
HTML = (AGENT / "web" / "how-i-build.html").read_text(encoding="utf-8")
SERVER = (AGENT / "web_server.py").read_text(encoding="utf-8")
BLOB = "https://github.com/karthikdevadoss/agentic-software-delivery/blob/master/"


class HowIBuildPageTests(unittest.TestCase):
    def test_route_is_wired(self):
        self.assertIn('Route("/how-i-build", how_i_build_page', SERVER)

    def test_every_linked_repository_file_exists(self):
        files = re.findall(re.escape(BLOB) + r'([^"#]+)', HTML)
        self.assertGreaterEqual(len(files), 5)
        for rel in files:
            with self.subTest(file=rel):
                self.assertTrue((REPO / rel).is_file(), f"page links to {rel}, which does not exist")

    def test_authorship_is_stated_plainly(self):
        squashed = " ".join(HTML.split())
        self.assertIn("Most of the code on this platform is written by Claude Code", squashed)
        self.assertNotRegex(squashed, r"(?i)\bI (hand-)?wrote (all|every|the) code")

    def test_reviewer_really_has_no_write_tools(self):
        agent_def = (REPO / ".claude" / "agents" / "qa-evaluator.md").read_text(encoding="utf-8")
        self.assertRegex(agent_def, r"disallowedTools:.*Write")
        self.assertRegex(agent_def, r"disallowedTools:.*Edit")

    def test_rules_quoted_are_in_the_rules_file(self):
        rules = " ".join((REPO / "CLAUDE.md").read_text(encoding="utf-8").split())
        for phrase in ("observed failing", "SKIPPED is not PASSED", "remembered API",
                       "isolated git worktree", "computed, not judged"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, rules)

    def test_internal_links_are_served(self):
        for href in set(re.findall(r'href="(/[^"#?]*)', HTML)):
            if href.endswith(".css") or href == "/":
                continue
            with self.subTest(href=href):
                self.assertIn(f'Route("{href}"', SERVER)


if __name__ == "__main__":
    unittest.main()
