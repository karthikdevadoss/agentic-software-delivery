"""Favicon (23 Oct 2026): /favicon.ico returned 404 in production because no
icon file existed in agent/web/, so the static mount had nothing to serve.
Hermetic: files and the in-process app."""
import pathlib
import unittest

from starlette.testclient import TestClient

import web_server

WEB = pathlib.Path(__file__).resolve().parent / "web"

# Standing Interview is out of scope for automation sprints (Owner rule); the
# browser still requests /favicon.ico for it by default.
KNOWN_EXCEPTIONS = {"standing-interview.html"}


class FaviconTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(web_server.app)

    def test_icon_files_are_served(self):
        for path, magic in (("/favicon.ico", b"\x00\x00\x01\x00"),
                            ("/favicon.svg", b"<svg"),
                            ("/apple-touch-icon.png", b"\x89PNG")):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.content.startswith(magic))

    def test_every_page_links_the_icon(self):
        for page in sorted(WEB.glob("*.html")):
            if page.name in KNOWN_EXCEPTIONS:
                continue
            text = page.read_text(encoding="utf-8")
            with self.subTest(page=page.name):
                self.assertIn('<link rel="icon" href="/favicon.svg" type="image/svg+xml">', text)
                self.assertIn('<link rel="icon" href="/favicon.ico" sizes="any">', text)


if __name__ == "__main__":
    unittest.main()
