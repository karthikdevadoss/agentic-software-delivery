"""Hermetic tests for the unlisted /kraken AI Foundations map (2026-11-26).

Static HTML + route + fixture checks. No network, no model.
Every posting quote must be verbatim from the captured posting text, every
internal link must be a wired route, every GitHub source link must name a file
that exists in this repo, and the page must stay out of the nav and out of
search engines.
"""
from __future__ import annotations

import html
import pathlib
import re
import unittest

AGENT = pathlib.Path(__file__).resolve().parent
REPO = AGENT.parent
WEB = AGENT / "web"
HTML = (WEB / "kraken.html").read_text(encoding="utf-8")
NAV = (WEB / "nav.js").read_text(encoding="utf-8")
SERVER = (AGENT / "web_server.py").read_text(encoding="utf-8")
POSTING = (AGENT / "fixtures" / "kraken_ai_foundations_posting_2026-11-26.txt").read_text(encoding="utf-8")
BLOB = "https://github.com/karthikdevadoss/agentic-software-delivery/blob/master/"

FORBIDDEN = [
    (r"(?i)€\s*\d|EUR\s*\d|available (immediately|in \d)", "salary/availability figure"),
    (r"(?i)architect (at|for|title at) NRG|NRG.{0,40}Architect", "Architect title on NRG"),
    (r"(?i)multi-agent orchestration platform", "overclaim multi-agent"),
    (r"(?i)production-scale vector", "overclaim vector infrastructure"),
    (r"(?i)kubernetes in production\s*:?\s*(yes|done|running)", "overclaim Kubernetes"),
]


def _squash(s: str) -> str:
    return " ".join(s.split())


class KrakenPageTestCase(unittest.TestCase):
    def test_route_is_wired(self):
        self.assertIn('Route("/kraken", kraken_page', SERVER)
        self.assertIn('WEB_DIR / "kraken.html"', SERVER)

    def test_unlisted(self):
        self.assertIn('<meta name="robots" content="noindex, nofollow">', HTML)
        self.assertNotIn('"/kraken"', NAV, "/kraken must not appear in the site nav")

    def test_canonical_nav_and_styles(self):
        self.assertIn('<script src="/nav.js">', HTML)
        self.assertIn('href="/interviewer.css"', HTML)
        self.assertIn(".kr-quote", (WEB / "interviewer.css").read_text(encoding="utf-8"))
        self.assertNotIn("fonts.googleapis.com", HTML)

    def test_headline_and_nrg_facts_match_cv(self):
        self.assertIn('<p class="iv-role">Senior AI Platform Engineer</p>', HTML)
        compact = _squash(HTML)
        for phrase in ("Since March 2022 I have worked for NRG Energy through Remote, my employer",
                       "one of a handful of engineers in the initial core AI team at NRG",
                       "cutting routine work time by about 20%",
                       "separate from NRG"):
            self.assertIn(phrase, compact)

    def test_all_four_areas_and_three_squads(self):
        for h in ("Access", "Context", "Enablement", "Governance", "Tooling", "Evals &amp; Observability"):
            self.assertIn(f"<h3>{h}</h3>", HTML)

    def test_quotes_are_verbatim_from_the_posting(self):
        quotes = re.findall(r'<blockquote class="kr-quote">“(.*?)”</blockquote>', HTML, re.S)
        self.assertEqual(len(quotes), 7, quotes)
        posting = _squash(POSTING)
        for q in quotes:
            self.assertIn(_squash(html.unescape(q)), posting, f"not verbatim: {q!r}")

    def test_internal_links_are_wired_routes(self):
        for href in set(re.findall(r'href="(/[^"#?]*)', HTML)):
            if href.endswith(".css") or href == "/":
                continue
            self.assertIn(f'Route("{href}"', SERVER, f"no route for {href}")
        wb = (WEB / "workbench.html").read_text(encoding="utf-8")
        self.assertIn('id="verified-run-panel"', wb)

    def test_github_links_name_real_files(self):
        links = re.findall(re.escape(BLOB) + r'([^"]+)"', HTML)
        self.assertGreaterEqual(len(links), 8)
        for rel in links:
            self.assertTrue((REPO / rel).exists(), f"GitHub link to missing file: {rel}")

    def test_honest_gaps_are_stated(self):
        compact = _squash(HTML)
        for phrase in ("Kubernetes in production:", "AWS Bedrock, Inspect AI, Ragas:",
                       "not on the public site", "reset on a redeploy",
                       "Notion and Slack connectors are not built",
                       "re-embeds only what changed", "removes deleted items",
                       "OpenTelemetry trace as a"):
            self.assertIn(phrase, compact)

    def test_sixty_second_tour_is_first_and_has_three_free_steps(self):
        self.assertIn('id="tour"', HTML)
        self.assertLess(HTML.index('id="tour"'), HTML.index("The four areas"))
        tour = HTML.split('id="tour"', 1)[1].split("</section>", 1)[0]
        links = re.findall(r'<li>\s*<a href="([^"]+)"', tour)
        self.assertEqual(links[0].split("?")[0], "/ask-codebase")
        self.assertIn("?q=", links[0])
        self.assertEqual(links[1:], ["/workbench#verified-run-panel", "/eval"])
        self.assertIn("no model call", tour)

    def test_ask_codebase_supports_the_deep_link(self):
        js = (WEB / "ask-codebase.js").read_text(encoding="utf-8")
        self.assertIn('new URLSearchParams(window.location.search).get("q")', js)
        self.assertIn(".slice(0, 300)", js)

    def test_walkthrough_video_is_embedded_and_small(self):
        media = WEB / "media"
        video, poster = media / "walkthrough.webm", media / "walkthrough-poster.png"
        self.assertTrue(video.is_file() and poster.is_file())
        self.assertLess(video.stat().st_size, 8 * 1024 * 1024, "keep the repo and page light")
        self.assertIn('src="/media/walkthrough.webm"', HTML)
        self.assertIn('poster="/media/walkthrough-poster.png"', HTML)
        self.assertIn('preload="none"', HTML)
        self.assertLess(HTML.index('class="kr-video"'), HTML.index("The four areas"))

    def test_no_forbidden_claims(self):
        for pat, name in FORBIDDEN:
            self.assertIsNone(re.search(pat, HTML), f"forbidden claim: {name}")


if __name__ == "__main__":
    unittest.main()
