"""Hermetic HTTP + static tests for the /ai-usage page and /api/ai-usage/* routes.

Real Starlette app through TestClient: no network, no model, no database
(the public view is the in-memory demo dataset; live needs the owner token
and is refused before any database is touched).
"""
from __future__ import annotations

import os
import pathlib
import re
import unittest
from unittest import mock

from starlette.testclient import TestClient

import web_server as ws

WEB = pathlib.Path(__file__).resolve().parent / "web"
HTML = (WEB / "ai-usage.html").read_text(encoding="utf-8")
JS = (WEB / "ai-usage.js").read_text(encoding="utf-8")
TOKEN = "test-owner-token-not-real"


class AiUsageHttpTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(ws.app)

    def test_page_served(self):
        r = self.client.get("/ai-usage")
        self.assertEqual(r.status_code, 200)
        self.assertIn('id="au-tiles"', r.text)

    def test_public_views_are_demo_and_labelled(self):
        for view in ("overview", "breakdown", "sessions", "recommendations", "models", "learning"):
            r = self.client.get(f"/api/ai-usage/{view}?dataset=demo&range=30d")
            self.assertEqual(r.status_code, 200, view)
            body = r.json()
            self.assertEqual(body["dataset"], "demo", view)
            self.assertIn("Fictional", body["demo_label"], view)

    def test_public_live_is_403_not_demo(self):
        with mock.patch.dict(os.environ, {"OWNER_API_TOKEN": TOKEN}):
            for path in ("/api/ai-usage/overview?dataset=live", "/api/ai-usage/sessions/x?dataset=live"):
                self.assertEqual(self.client.get(path).status_code, 403, path)
            wrong = self.client.get("/api/ai-usage/overview?dataset=live", headers={"X-Owner-Token": "wrong"})
            self.assertEqual(wrong.status_code, 403)

    def test_public_writes_refused(self):
        with mock.patch.dict(os.environ, {"OWNER_API_TOKEN": TOKEN}):
            r = self.client.post("/api/ai-usage/outcomes", json={"task_id": "t", "outcome_type": "x",
                                                                  "status": "completed", "evidence": "human"})
            self.assertEqual(r.status_code, 403)
            r = self.client.post("/api/ai-usage/learning-records", json={"records": []})
            self.assertEqual(r.status_code, 403)

    def test_bad_input(self):
        self.assertEqual(self.client.get("/api/ai-usage/nope").status_code, 404)
        self.assertEqual(self.client.get("/api/ai-usage/overview?range=forever").status_code, 400)
        self.assertEqual(self.client.get("/api/ai-usage/breakdown?by=email").status_code, 400)
        self.assertEqual(self.client.get("/api/ai-usage/sessions/does-not-exist").status_code, 404)

    def test_meta(self):
        r = self.client.get("/api/ai-usage/meta")
        self.assertEqual(r.status_code, 200)
        self.assertIn("objective", r.json()["evidence"])


class AiUsageStaticTests(unittest.TestCase):
    def test_no_innerhtml(self):
        # Every value is written with textContent; demo/live data never becomes markup.
        self.assertNotRegex(JS, r"innerHTML|outerHTML|insertAdjacentHTML|document\.write")

    def test_every_js_id_exists_in_html(self):
        ids = set(re.findall(r'\$\("([a-zA-Z0-9_-]+)"\)', JS))
        ids |= {f"f-{f}" for f in ("team_id", "user_id", "project_id", "model", "activity_category")}
        missing = sorted(i for i in ids if f'id="{i}"' not in HTML)
        self.assertEqual(missing, [])

    def test_token_never_in_url_or_localstorage(self):
        self.assertNotIn("localStorage", JS)
        self.assertNotRegex(JS, r"[?&]token=")
        self.assertIn("X-Owner-Token", JS)

    def test_no_external_scripts(self):
        self.assertEqual(re.findall(r'<script[^>]+src="https?:', HTML), [])


if __name__ == "__main__":
    unittest.main()
