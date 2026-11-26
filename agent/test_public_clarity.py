"""Hermetic tests for two public-clarity changes (2026-11-26).

1. Evals is in the public nav (the strongest proof of measured AI quality),
   while the earlier Owner removals (Usage, Showcase, Standing Interview) stay out.
2. Standing Interview says plainly, above the question box, that it is an AI
   answering from the owner's notes and not the owner.
"""
import pathlib
import re
import unittest

WEB = pathlib.Path(__file__).resolve().parent / "web"
NAV = (WEB / "nav.js").read_text(encoding="utf-8")
SI = (WEB / "standing-interview.html").read_text(encoding="utf-8")


def _nav_hrefs():
    block = NAV.split("const CANONICAL_NAV_DESTINATIONS = [", 1)[1].split("];", 1)[0]
    return re.findall(r'^\s*\{ href: "([^"]+)"', block, re.M)


class PublicClarityTests(unittest.TestCase):
    def test_evals_in_nav_after_ask_codebase(self):
        hrefs = _nav_hrefs()
        self.assertIn("/eval", hrefs)
        self.assertEqual(hrefs.index("/eval"), hrefs.index("/ask-codebase") + 1)
        self.assertIn('{ href: "/eval", label: "Evals" }', NAV)

    def test_earlier_owner_removals_stay_out_of_nav(self):
        hrefs = _nav_hrefs()
        for removed in ("/usage", "/standing-interview", "/dashboard", "/kraken"):
            self.assertNotIn(removed, hrefs)

    def test_standing_interview_says_it_is_an_ai(self):
        self.assertIn('id="si-ai-note"', SI)
        self.assertIn("This is an AI assistant, not me.", SI)
        self.assertIn("it can be wrong", SI)
        # The label sits above the intro and the question box.
        self.assertLess(SI.index('id="si-ai-note"'), SI.index('class="si-intro"', SI.index("<h1")))


if __name__ == "__main__":
    unittest.main()
