"""Site changes of 21 Oct 2026: internal pages behind a flag, Token X-ray,
favicon, friendly 404, link-preview meta. Hermetic: TestClient + file reads."""
from __future__ import annotations

import os
import pathlib
import re
import unittest
from unittest import mock

from starlette.testclient import TestClient

import web_server as ws

WEB = ws.WEB_DIR
INTERNAL = ("/usage", "/usage/session/abc123", "/dashboard", "/usage.html", "/dashboard.html",
            "/api/dashboard", "/api/sessions", "/api/sessions/history", "/api/sessions/history/abc")


class InternalPagesFlagTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)

    def test_internal_pages_are_404_by_default(self):
        with mock.patch.dict(os.environ, {"SHOW_INTERNAL_PAGES": ""}):
            for path in INTERNAL:
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path, follow_redirects=False).status_code, 404)

    def test_flag_on_serves_the_pages_again(self):
        with mock.patch.dict(os.environ, {"SHOW_INTERNAL_PAGES": "1"}):
            for path in ("/usage", "/dashboard", "/usage.html"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_no_public_page_links_to_internal_pages(self):
        for name in ("home.html", "workbench.html", "workbench.js", "eval.html", "nav.js",
                     "showcase.js", "tokens.html", "interviewer.html"):
            text = (WEB / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertIsNone(re.search(r'["\'`]/(usage|dashboard)["\'`/?#]', text))


class TokenXrayPageTest(unittest.TestCase):
    HTML = (WEB / "tokens.html").read_text(encoding="utf-8")

    def test_route_serves(self):
        r = TestClient(ws.app).get("/tokens")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Token X-ray", r.text)

    def test_real_numbers_and_the_caveat(self):
        for needle in ("4.5x the tokens", "4.2x the cost", "56,188", "12,601", "$0.205 vs $0.048",
                       "6 tasks, Claude models only", "21 Oct 2026"):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.HTML)

    def test_no_course_branding(self):
        for banned in ("Kamal", "Digiflowhub", "Digiflow", "course", "Session 1"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned.lower(), self.HTML.lower())

    def test_every_chart_exists(self):
        for src in re.findall(r'src="(/img/[^"]+)"', self.HTML):
            with self.subTest(src=src):
                self.assertTrue((WEB / src.lstrip("/")).is_file())

    def test_in_the_nav(self):
        self.assertIn('{ href: "/tokens", label: "Token X-ray" }', (WEB / "nav.js").read_text(encoding="utf-8"))


class FaviconAnd404Test(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)

    def test_favicon(self):
        for path in ("/favicon.ico", "/favicon.svg"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_unknown_page_gets_the_friendly_404(self):
        r = self.client.get("/no-such-page-here")
        self.assertEqual(r.status_code, 404)
        self.assertIn("This page is not here.", r.text)
        self.assertIn('href="/"', r.text)

    def test_unknown_api_path_stays_json(self):
        r = self.client.get("/api/no-such-endpoint")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json(), {"detail": "Not Found"})


class LinkPreviewMetaTest(unittest.TestCase):
    def test_main_pages_have_og_tags(self):
        for name in ("home.html", "tokens.html", "workbench.html", "triage.html", "ask-codebase.html",
                     "eval.html", "recruiters.html", "interviewer.html", "case-study-durable-agent.html"):
            text = (WEB / name).read_text(encoding="utf-8")
            for prop in ("og:title", "og:description", "og:image"):
                with self.subTest(page=name, prop=prop):
                    self.assertIn(f'property="{prop}"', text)
        self.assertTrue((WEB / "img/tokens/og-token-xray.png").is_file())


class HomeHeroTest(unittest.TestCase):
    HOME = (WEB / "home.html").read_text(encoding="utf-8")

    def test_token_hero(self):
        self.assertIn("AI Engineer. <em>Same answer, fewer tokens.</em>", self.HOME)
        self.assertIn("4.5x the tokens and 4.2x the cost</b> for the same output, measured on 6 real tasks (Claude only).", self.HOME)
        self.assertIn('href="/tokens">See the Token X-ray</a>', self.HOME)
        self.assertIn('href="/workbench">Try the Workbench (one click)</a>', self.HOME)
        self.assertIn('/img/tokens/wrong-vs-right.webp', self.HOME)


if __name__ == "__main__":
    unittest.main()
