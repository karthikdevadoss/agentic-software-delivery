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
        self.assertEqual(payload.get("count", 0), 8)
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
        self.assertEqual(data["count"], 8)
        # Newest-posted first
        dates = [p["posted"] for p in data["packs"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        # Location TOP filter (policy v32): no London-only / Munich-only /
        # Amsterdam / Paris / Stockholm primary rows.
        for pack in data["packs"]:
            loc = (pack.get("location") or "").lower()
            if "remote" in loc and any(x in loc for x in ("europe", "emea", "germany", "global", "worldwide")):
                continue  # remote Europe with optional London mention OK (e.g. Tavily)
            if "berlin" in loc:
                continue
            for city in ("london", "stockholm", "munich", "paris", "amsterdam"):
                self.assertNotIn(city, loc, pack.get("slug"))
        pdf_dir = WEB / "applications_pdf"
        for p in data["packs"]:
            self.assertTrue((pdf_dir / p["cv_pdf"]).is_file(), p["cv_pdf"])
            self.assertTrue(p.get("cover_letter"))


if __name__ == "__main__":
    unittest.main()


class ApplicationsApproveQueueTest(unittest.TestCase):
    """Sprint 13: Approve records Owner yes; queue gated; never auto-applies."""

    def setUp(self):
        self._prev = os.environ.pop("APPLICATIONS_REVIEW_TOKEN", None)
        ws.APPLICATIONS_REVIEW_TOKEN = TOKEN
        self._tmpdir = pathlib.Path(self._mk_tmp())
        self._queue = self._tmpdir / "apply_queue.json"
        self._prev_q = os.environ.get("APPLICATIONS_APPLY_QUEUE_PATH")
        os.environ["APPLICATIONS_APPLY_QUEUE_PATH"] = str(self._queue)
        # Reload path resolution uses env each call — no module reload needed.
        self.client = TestClient(ws.app)
        packs = self.client.get("/applications.json", params={"k": TOKEN}).json()["packs"]
        self.pack_id = packs[0]["id"]

    def _mk_tmp(self):
        import tempfile
        return tempfile.mkdtemp(prefix="apq-")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("APPLICATIONS_REVIEW_TOKEN", None)
        else:
            os.environ["APPLICATIONS_REVIEW_TOKEN"] = self._prev
        ws.APPLICATIONS_REVIEW_TOKEN = (
            os.environ.get("APPLICATIONS_REVIEW_TOKEN", TOKEN).strip() or TOKEN
        )
        if self._prev_q is None:
            os.environ.pop("APPLICATIONS_APPLY_QUEUE_PATH", None)
        else:
            os.environ["APPLICATIONS_APPLY_QUEUE_PATH"] = self._prev_q
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_approve_without_key_is_404(self):
        r = self.client.post("/applications/approve", json={"pack_id": self.pack_id})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(self._queue.is_file())

    def test_approve_wrong_key_is_404(self):
        r = self.client.post(
            "/applications/approve",
            params={"k": "wrong"},
            json={"pack_id": self.pack_id},
        )
        self.assertEqual(r.status_code, 404)

    def test_approve_records_owner_yes_and_pending_apply(self):
        r = self.client.post(
            "/applications/approve",
            params={"k": TOKEN},
            json={"pack_id": self.pack_id},
        )
        self.assertEqual(r.status_code, 200, r.text[:300])
        body = r.json()
        self.assertTrue(body.get("ok"))
        self.assertFalse(body.get("applied"), "web must never mark applied on Approve")
        item = body["item"]
        self.assertTrue(item["owner_approved"])
        self.assertTrue(item["approved_at"])
        self.assertEqual(item["status"], "pending_apply")
        self.assertEqual(item["pack_id"], self.pack_id)
        self.assertTrue(self._queue.is_file())

        q = self.client.get("/applications/queue", params={"k": TOKEN})
        self.assertEqual(q.status_code, 200)
        items = q.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["pack_id"], self.pack_id)

    def test_approve_idempotent(self):
        a = self.client.post(
            "/applications/approve", params={"k": TOKEN}, json={"pack_id": self.pack_id}
        ).json()["item"]
        b = self.client.post(
            "/applications/approve", params={"k": TOKEN}, json={"pack_id": self.pack_id}
        ).json()["item"]
        self.assertEqual(a["approved_at"], b["approved_at"])
        q = self.client.get("/applications/queue", params={"k": TOKEN}).json()
        self.assertEqual(len(q["items"]), 1)

    def test_approve_unknown_pack_is_404(self):
        r = self.client.post(
            "/applications/approve",
            params={"k": TOKEN},
            json={"pack_id": "no-such-pack-id"},
        )
        self.assertEqual(r.status_code, 404)

    def test_queue_update_applied_with_proof(self):
        self.client.post(
            "/applications/approve", params={"k": TOKEN}, json={"pack_id": self.pack_id}
        )
        r = self.client.post(
            "/applications/queue/update",
            params={"k": TOKEN},
            json={
                "pack_id": self.pack_id,
                "status": "applied",
                "proof": {"method": "employer_form", "confirmation": "test-only"},
            },
        )
        self.assertEqual(r.status_code, 200, r.text[:300])
        item = r.json()["item"]
        self.assertEqual(item["status"], "applied")
        self.assertEqual(item["proof"]["method"], "employer_form")
        self.assertTrue(item["applied_at"])

    def test_queue_without_key_is_404(self):
        self.assertEqual(self.client.get("/applications/queue").status_code, 404)
