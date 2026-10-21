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

# The real application packs and CV/cover-letter PDFs left the repository on
# 2026-10-21 (Owner decision; gitignored, local-only). The route behaviour is
# tested against one synthetic pack in a temporary web directory instead.
_FIXTURE_DIR = None
_SAVED = {}
FIXTURE_PACK = {
    "id": "synthetic-pack", "slug": "synthetic-pack", "rank": 1,
    "company": "Example Co", "title": "AI Engineer", "location": "Berlin, Germany",
    "posted": "2026-10-01", "fit_oneliner": "Synthetic test pack.",
    "cover_letter": "Synthetic cover letter text.", "cv_pdf": "Synthetic_CV.pdf",
    "url": "https://example.com/job",
}


def setUpModule():
    import json
    import shutil
    import tempfile
    global _FIXTURE_DIR
    _FIXTURE_DIR = pathlib.Path(tempfile.mkdtemp(prefix="apps-web-"))
    shutil.copy(WEB / "applications.html", _FIXTURE_DIR / "applications.html")
    (_FIXTURE_DIR / "applications.json").write_text(
        json.dumps({"count": 1, "packs": [FIXTURE_PACK]}), encoding="utf-8")
    pdf_dir = _FIXTURE_DIR / "applications_pdf"
    pdf_dir.mkdir()
    (pdf_dir / FIXTURE_PACK["cv_pdf"]).write_bytes(b"%PDF-1.4\n% synthetic\n")
    _SAVED.update(WEB_DIR=ws.WEB_DIR, APPLICATIONS_PDF_DIR=ws.APPLICATIONS_PDF_DIR)
    ws.WEB_DIR = _FIXTURE_DIR
    ws.APPLICATIONS_PDF_DIR = pdf_dir


def tearDownModule():
    import shutil
    ws.WEB_DIR = _SAVED["WEB_DIR"]
    ws.APPLICATIONS_PDF_DIR = _SAVED["APPLICATIONS_PDF_DIR"]
    shutil.rmtree(_FIXTURE_DIR, ignore_errors=True)


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
        sample = FIXTURE_PACK["cv_pdf"]
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
        self.assertEqual(payload.get("count", 0), 1)
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
        self.assertIn('{ href: "/interviewer", label: "Interviewer Brief" }', nav)

    def test_standing_interview_page_still_exists(self):
        # Out of the public nav since 2026-10-21; the page itself stays.
        self.assertTrue((WEB / "standing-interview.html").is_file())
        # applications page must not load nav.js (private, no public chrome)
        html = (WEB / "applications.html").read_text(encoding="utf-8")
        self.assertNotIn("nav.js", html)
        self.assertNotIn("top-nav", html)


class ApplicationsReviewDataTest(unittest.TestCase):
    def test_no_application_material_is_tracked_in_git(self):
        """Owner decision 2026-10-21: tailored CVs, cover letters and the pack
        file stay out of the repository."""
        import subprocess
        root = pathlib.Path(__file__).resolve().parent.parent
        tracked = subprocess.run(
            ["git", "ls-files", "agent/web/applications.json", "agent/web/applications_pdf"],
            cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(tracked, "", f"application material is tracked:\n{tracked}")

    def test_missing_pack_file_is_a_plain_404(self):
        client = TestClient(ws.app)
        with mock.patch.object(ws, "WEB_DIR", WEB / "no-such-dir"):
            r = client.get("/applications.json", params={"k": TOKEN})
        self.assertEqual(r.status_code, 404)


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
