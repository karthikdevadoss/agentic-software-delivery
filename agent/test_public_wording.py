"""Owner wording rules for the public pages and Standing Interview (2026-10-21).

Hermetic: reads the committed page sources and the Standing Interview module.
Every phrase below was removed on the Owner's instruction; this keeps it out.
"""
from __future__ import annotations

import pathlib
import re
import unittest

AGENT = pathlib.Path(__file__).resolve().parent
WEB = AGENT / "web"

PAGES = {
    "home": WEB / "home.html",
    "interviewer": WEB / "interviewer.html",
    "recruiters.html": WEB / "recruiters.html",
    "recruiters.js": WEB / "recruiters.js",
    "recruiters.json": WEB / "recruiters.json",
    "recruiters_source": AGENT / "recruiters_source.yaml",
    "workbench.html": WEB / "workbench.html",
    "workbench.js": WEB / "workbench.js",
    "standing_interview": AGENT / "standing_interview.py",
}

BANNED = [
    (r"Junior AI Architect", "retired headline"),
    (r"Senior Backend / Software Engineer", "retired headline"),
    (r"open to contract", "retired work-mode wording"),
    (r"since (mid-|July )2021", "wrong NRG start date"),
    (r"no formal AI-leadership title", "retired title wording"),
    (r"Wildau", "location must read Berlin, Germany"),
    (r"near Berlin", "location must read Berlin, Germany"),
    (r"YogaCRM|Tekdoors", "not in summaries or headlines"),
    (r"deployed automatically, with no human approval", "Workbench needs a person's approval"),
    (r"no human approval", "Workbench needs a person's approval"),
    (r"Not in this portfolio|Honest gaps", "gap section"),
]

HEADLINE = "AI Engineer – Full Stack"


class BannedWording(unittest.TestCase):
    def test_no_banned_phrase_on_any_public_surface(self):
        for name, path in PAGES.items():
            text = path.read_text(encoding="utf-8")
            for pattern, why in BANNED:
                with self.subTest(surface=name, pattern=pattern):
                    self.assertIsNone(re.search(pattern, text, re.I), f"{name}: {why}")


class Headline(unittest.TestCase):
    def test_headline_on_home_interviewer_and_recruiters(self):
        home = (WEB / "home.html").read_text(encoding="utf-8")
        self.assertIn(f'<p class="role">{HEADLINE}</p>', home)
        self.assertIn(f"<title>Karthikeyan Devadoss — {HEADLINE}</title>", home)
        self.assertIn(f'<p class="iv-role">{HEADLINE}</p>',
                      (WEB / "interviewer.html").read_text(encoding="utf-8"))
        self.assertIn(f"headline: {HEADLINE}",
                      (AGENT / "recruiters_source.yaml").read_text(encoding="utf-8"))

    def test_location_is_berlin_germany(self):
        self.assertIn("Berlin, Germany", (WEB / "home.html").read_text(encoding="utf-8"))
        self.assertIn("Berlin, Germany", (WEB / "interviewer.html").read_text(encoding="utf-8"))


class WorkbenchApprovalWording(unittest.TestCase):
    def test_workbench_says_a_person_approves_first(self):
        html = (WEB / "workbench.html").read_text(encoding="utf-8")
        self.assertIn("A person approves before anything changes", html)


class StandingInterviewNav(unittest.TestCase):
    def test_standing_interview_is_not_in_the_nav(self):
        nav = (WEB / "nav.js").read_text(encoding="utf-8")
        self.assertNotIn('href: "/standing-interview"', nav)
        self.assertTrue((WEB / "standing-interview.html").is_file(),
                        "the page stays reachable by direct link")


if __name__ == "__main__":
    unittest.main()
