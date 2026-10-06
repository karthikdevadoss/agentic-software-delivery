"""Automation Sprint 11: Applications Review gate and nav isolation.

Hermetic: TestClient against the real app; no network. Asserts:
- missing / wrong ?k= → 404 (page, json, pdf) with no hint
- correct ?k= → 200
- public nav.js does not link to Applications /applications
- Standing Interview surface is untouched
"""
from __future__ import annotations

import os
import pathlib
import unittest
from unittest import mock

from starlette.testclient import TestClient

import web_server as ws

WEB = pathlib.Path(__file__).resolve().parent / "web"
TOKEN = ws.DEFAULT_APPLICATIONS_REVIEW_TOKEN


class ApplicationsReviewGateTest(unittest.TestCase):
    def setUp(self):
        # Ensure default local token is active for these tests.
        self._prev = os.environ.pop("APPLICATIONS_REVIEW_TOKEN", None)
        ws.APPLICATIONS_REVIEW_TOKEN = TOKEN
        self.client = TestClient(ws.app)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("APPLICATIONS_REVIEW_TOKEN", None)
        else:
            os.environ["APPLICATIONS_REVIEW_TOKEN"] = self._prev
        ws.APPLICATIONS_REVIEW_TOKEN = (
            os.environ.get("APPLICATIONS_REVIEW_TOKEN", TOKEN).strip() or TOKEN
        )

    def test_default_token_constant_for_local_tests(self):
        self.assertEqual(TOKEN, "local-test-applications-review")
        self.assertTrue(TOKEN)

    def test_no_key_returns_404_for_page_json_and_pdf(self):
        pdfs = sorted((WEB / "applications_pdf").glob("*.pdf"))
        self.assertTrue(pdfs, "expected baked CV PDFs under applications_pdf/")
        sample = pdfs[0].name
        for path in (
            "/applications",
            "/applications.json",
            f"/applications_pdf/{sample}",
        ):
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 404, r.text[:200])
                body = r.text.lower()
                self.assertNotIn("token", body)
                self.assertNotIn("applications review", body)
                self.assertNotIn("unauthorized", body)

    def test_wrong_key_returns_404(self):
        for path in ("/applications", "/applications.json"):
            with self.subTest(path=path):
                r = self.client.get(path, params={"k": "wrong-key-not-it"})
                self.assertEqual(r.status_code, 404)

    def test_right_key_returns_200_page_and_json(self):
        page = self.client.get("/applications", params={"k": TOKEN})
        self.assertEqual(page.status_code, 200, page.text[:200])
        self.assertIn("text/html", page.headers.get("content-type", ""))
        self.assertIn("ap-main", page.text)

        data = self.client.get("/applications.json", params={"k": TOKEN})
        self.assertEqual(data.status_code, 200)
        payload = data.json()
        self.assertGreaterEqual(payload.get("count", 0), 35)
        self.assertEqual(len(payload["packs"]), payload["count"])
        first = payload["packs"][0]
        for key in ("rank", "company", "title", "location", "posted", "fit_oneliner",
                    "cover_letter", "cv_pdf", "url"):
            self.assertIn(key, first)

    def test_right_key_serves_pdf(self):
        data = self.client.get("/applications.json", params={"k": TOKEN}).json()
        name = data["packs"][0]["cv_pdf"]
        r = self.client.get(f"/applications_pdf/{name}", params={"k": TOKEN})
        self.assertEqual(r.status_code, 200)
        self.assertIn("pdf", r.headers.get("content-type", "").lower())
        self.assertTrue(r.content[:4] == b"%PDF" or len(r.content) > 1000)

    def test_unknown_or_unsafe_pdf_name_is_404(self):
        # Missing file
        r = self.client.get("/applications_pdf/no-such-pack.pdf", params={"k": TOKEN})
        self.assertEqual(r.status_code, 404)
        # Extension must be .pdf (handler rejects non-pdf names)
        r2 = self.client.get("/applications_pdf/applications.json", params={"k": TOKEN})
        self.assertEqual(r2.status_code, 404)

    def test_raw_applications_html_is_404(self):
        r = self.client.get("/applications.html")
        self.assertEqual(r.status_code, 404)
        r2 = self.client.get("/applications.html", params={"k": TOKEN})
        self.assertEqual(r2.status_code, 404)

    def test_env_token_override(self):
        custom = "custom-live-style-token-xyz"
        with mock.patch.object(ws, "APPLICATIONS_REVIEW_TOKEN", custom):
            self.assertEqual(self.client.get("/applications", params={"k": TOKEN}).status_code, 404)
            self.assertEqual(self.client.get("/applications", params={"k": custom}).status_code, 200)


class ApplicationsReviewNavTest(unittest.TestCase):
    def test_nav_does_not_include_applications(self):
        nav = (WEB / "nav.js").read_text(encoding="utf-8")
        self.assertNotIn("/applications", nav)
        self.assertNotIn("Applications", nav)
        self.assertNotIn("job-packs", nav)
        # Still has For Recruiters (public HR page) — unchanged.
        self.assertIn('{ href: "/recruiters", label: "For Recruiters" }', nav)

    def test_standing_interview_untouched(self):
        nav = (WEB / "nav.js").read_text(encoding="utf-8")
        self.assertIn("/standing-interview", nav)
        self.assertTrue((WEB / "standing-interview.html").is_file())
        # applications page must not load nav.js (private, no public chrome)
        html = (WEB / "applications.html").read_text(encoding="utf-8")
        self.assertNotIn("nav.js", html)
        self.assertNotIn("top-nav", html)


class ApplicationsReviewDataTest(unittest.TestCase):
    def test_baked_json_and_pdfs_exist(self):
        data_path = WEB / "applications.json"
        self.assertTrue(data_path.is_file())
        import json
        data = json.loads(data_path.read_text(encoding="utf-8"))
        self.assertEqual(data["count"], len(data["packs"]))
        self.assertGreaterEqual(data["count"], 35)
        # Newest-posted first
        dates = [p["posted"] for p in data["packs"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        pdf_dir = WEB / "applications_pdf"
        for p in data["packs"]:
            self.assertTrue((pdf_dir / p["cv_pdf"]).is_file(), p["cv_pdf"])
            self.assertTrue(p.get("cover_letter"))


if __name__ == "__main__":
    unittest.main()
