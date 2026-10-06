"""Automation Sprint 4 / S5: web fonts are served from this site.

Every page used to load its fonts from fonts.googleapis.com/fonts.gstatic.com,
sending each visitor's IP address to Google, while the home footer says the
site uses no third-party trackers. Hermetic: files and the in-process app.
"""
import pathlib
import re
import unittest

from starlette.testclient import TestClient

import web_server

WEB = pathlib.Path(__file__).resolve().parent / "web"
FONTS = WEB / "fonts"
GOOGLE = re.compile(r"fonts\.(googleapis|gstatic)\.com")

# Standing Interview is out of scope for automation sprints (Owner rule), so
# its page still links Google Fonts. Listed here so the exception is visible
# and deliberate; delete the entry when that page switches to /fonts/fonts.css
# (the ratchet test below then keeps it switched).
KNOWN_EXCEPTIONS = {"standing-interview.html"}


def _faces():
    css = (FONTS / "fonts.css").read_text(encoding="utf-8")
    return re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)


class NoGoogleFontsTestCase(unittest.TestCase):
    def test_no_page_or_stylesheet_requests_google_fonts(self):
        for p in sorted(list(WEB.glob("*.html")) + list(WEB.glob("*.css")) + list(WEB.glob("*.js"))):
            if p.name in KNOWN_EXCEPTIONS:
                continue
            with self.subTest(file=p.name):
                self.assertIsNone(GOOGLE.search(p.read_text(encoding="utf-8")),
                                  f"{p.name} still requests Google Fonts")

    def test_known_exceptions_are_still_exceptions(self):
        for name in KNOWN_EXCEPTIONS:
            with self.subTest(file=name):
                self.assertRegex((WEB / name).read_text(encoding="utf-8"), GOOGLE,
                                 f"{name} no longer uses Google Fonts: remove it from KNOWN_EXCEPTIONS")

    def test_pages_that_used_web_fonts_load_the_local_stylesheet(self):
        for name in ("home.html", "case-study-durable-agent.html", "workbench.html", "triage.html",
                     "ask-codebase.html", "showcase.html", "usage.html", "dashboard.html"):
            with self.subTest(page=name):
                self.assertIn('<link rel="stylesheet" href="/fonts/fonts.css">',
                              (WEB / name).read_text(encoding="utf-8"))


class LocalFontFilesTestCase(unittest.TestCase):
    def test_every_face_points_at_a_file_that_exists(self):
        faces = _faces()
        self.assertGreater(len(faces), 0)
        for face in faces:
            for url in re.findall(r"url\(([^)]+)\)", face):
                with self.subTest(url=url):
                    self.assertTrue(url.startswith("/fonts/"), url)
                    self.assertFalse(GOOGLE.search(url))
                    path = WEB / url.lstrip("/")
                    self.assertTrue(path.is_file(), url)
                    self.assertEqual(path.read_bytes()[:4], b"wOF2", f"{url} is not a woff2 file")

    def test_every_family_the_css_asks_for_is_self_hosted_and_licensed(self):
        css = (WEB / "style.css").read_text(encoding="utf-8")
        wanted = {v.strip().strip('"') for v in re.findall(r"--font-(?:body|display):\s*([^;]+);", css)}
        wanted |= {"JetBrains Mono", "Inter"}
        hosted = {re.search(r"font-family:\s*'([^']+)'", f).group(1) for f in _faces()}
        self.assertEqual(wanted - hosted, set(), "families used by style.css but not self-hosted")
        licences = {p.name for p in (FONTS / "licenses").glob("*-OFL.txt")}
        for family in hosted:
            slug = family.lower().replace(" ", "")
            with self.subTest(family=family):
                self.assertIn(f"{slug}-OFL.txt", licences)
                self.assertIn("SIL OPEN FONT LICENSE Version 1.1",
                              (FONTS / "licenses" / f"{slug}-OFL.txt").read_text(encoding="utf-8"))

    def test_the_app_serves_the_stylesheet_and_a_font_file(self):
        client = TestClient(web_server.app)
        r = client.get("/fonts/fonts.css")
        self.assertEqual(r.status_code, 200)
        first = re.search(r"url\((/fonts/[^)]+\.woff2)\)", r.text).group(1)
        f = client.get(first)
        self.assertEqual(f.status_code, 200)
        self.assertEqual(f.content[:4], b"wOF2")


if __name__ == "__main__":
    unittest.main()
