"""Hermetic tests for the /interviewer Interviewer Brief page.

Static HTML/CSS + route + nav wiring. No network, no model.
Facts on the page must stay within Owner-confirmed career wording
(recruiters_source, 2026-10-21): headline "AI Engineer · Forward Deployed Engineer
· AI Solutions" (2026-10-23); NRG since March 2022 through Remote; no Architect job title on NRG; the personal platform
is separate from NRG.
"""
from __future__ import annotations

import pathlib
import re
import unittest

WEB = pathlib.Path(__file__).resolve().parent / "web"
HTML = (WEB / "interviewer.html").read_text(encoding="utf-8")
CSS = (WEB / "interviewer.css").read_text(encoding="utf-8")
NAV = (WEB / "nav.js").read_text(encoding="utf-8")
SERVER = (pathlib.Path(__file__).resolve().parent / "web_server.py").read_text(encoding="utf-8")

# Same spirit as recruiters forbidden-claims scan: never invent titles / years / salary.
FORBIDDEN = [
    (r"(?i)€\s*\d|EUR\s*\d|available (immediately|in \d)", "salary/availability figure"),
    (r"(?i)architect (at|for|title at) NRG|NRG.{0,40}Architect", "Architect title on NRG"),
    (r"(?i)multi-agent orchestration platform", "overclaim multi-agent"),
    (r"(?i)production-scale vector", "overclaim vector infrastructure"),
]


class InterviewerPageTestCase(unittest.TestCase):
    def test_files_exist(self):
        self.assertTrue((WEB / "interviewer.html").is_file())
        self.assertTrue((WEB / "interviewer.css").is_file())

    def test_route_is_wired(self):
        self.assertIn('Route("/interviewer", interviewer_page', SERVER)
        self.assertIn("async def interviewer_page", SERVER)
        self.assertIn('WEB_DIR / "interviewer.html"', SERVER)

    def test_nav_entry(self):
        self.assertIn('{ href: "/interviewer", label: "Interviewer Brief" }', NAV)
        # Near recruiters; recruiters unchanged.
        self.assertIn('{ href: "/recruiters", label: "For Recruiters" }', NAV)
        rec_i = NAV.index('{ href: "/recruiters"')
        iv_i = NAV.index('{ href: "/interviewer"')
        self.assertLess(rec_i, iv_i, "Interviewer Brief should sit after For Recruiters")

    def test_page_uses_canonical_nav(self):
        self.assertIn('<script src="/nav.js">', HTML)
        self.assertRegex(HTML, r'<nav class="top-nav" id="top-nav"[^>]*>\s*</nav>')
        self.assertIn('href="/interviewer.css"', HTML)
        self.assertIn('data-surface="interviewer"', HTML)

    def test_role_framing(self):
        self.assertIn('<p class="iv-role">AI Engineer · Forward Deployed Engineer · AI Solutions</p>', HTML)
        self.assertNotIn("Junior AI Architect", HTML)
        self.assertRegex(HTML, r"(?i)technical interviewer")

    def test_nrg_facts(self):
        compact = " ".join(HTML.split())
        for phrase in ("Since March 2022 I have worked for NRG Energy through Remote, my employer",
                       "one of a handful of engineers in the initial core AI team at NRG",
                       "cutting routine work time by about 20%"):
            self.assertIn(phrase, compact)

    def test_workbench_card_says_a_person_approves_first(self):
        compact = " ".join(HTML.split())
        self.assertIn("A person approves before anything changes.", compact)

    def test_proof_card_links(self):
        required = [
            "/workbench#verified-run-panel",
            "/triage",
            "/eval",
            "/ask-codebase",
            "https://agentic-platform-backend-production.up.railway.app/",
        ]
        for href in required:
            self.assertIn(f'href="{href}"', HTML, f"missing proof link {href}")
        # Standing Interview left the public surfaces (2026-10-21).
        self.assertNotIn('href="/standing-interview"', HTML)
        self.assertIn('href="/recruiters"', HTML)

    def test_how_it_runs_card(self):
        compact = " ".join(HTML.split())
        for phrase in ("single model gateway", "Postgres event ledger with versioned pricing",
                       "separate from NRG"):
            self.assertIn(phrase, compact)

    def test_not_a_job_ad_count_page(self):
        # Recruiters page is the posting-count map; this brief must not mirror it.
        self.assertNotIn("Thirteen", HTML)
        self.assertNotIn("13 real", HTML)
        self.assertNotIn("asked_by", HTML)

    def test_no_forbidden_claims(self):
        for pat, name in FORBIDDEN:
            self.assertIsNone(re.search(pat, HTML), f"forbidden claim: {name}")

    def test_workbench_anchor_exists(self):
        wb = (WEB / "workbench.html").read_text(encoding="utf-8")
        self.assertIn('id="verified-run-panel"', wb)

    def test_home_scope_anchor_exists(self):
        home = (WEB / "home.html").read_text(encoding="utf-8")
        self.assertIn('id="scope"', home)
        self.assertIn('href="/#scope"', HTML)

    def test_css_is_self_contained_light_theme(self):
        self.assertIn("--paper:", CSS)
        self.assertNotIn("fonts.googleapis.com", HTML)
        self.assertNotIn("/style.css", HTML)


if __name__ == "__main__":
    unittest.main()
