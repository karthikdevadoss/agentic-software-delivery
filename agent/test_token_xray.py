"""Token X-ray numbers come from data in the repo, not from prose (2026-10-21).

Owner rule: no invented numbers. The home page and /tokens quote the token
experiment in docs/evidence/token-xray-2026-10-21. These tests fail if the
published JSON drifts from that data, or if either page quotes a token number
or multiple that the data does not contain. Hermetic: file reads only.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import publish_token_xray as ptx

WEB = Path(__file__).resolve().parent / "web"


def _visible_text(html: str) -> str:
    html = re.sub(r"<(script|style)\b.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


class PublishedJsonTest(unittest.TestCase):
    def test_json_is_current(self):
        self.assertEqual((WEB / "token-xray.json").read_text(encoding="utf-8"), ptx.render(ptx.build()),
                         "token-xray.json is stale: run python agent/publish_token_xray.py")

    def test_totals_are_the_sum_of_the_tasks(self):
        d = ptx.build()
        self.assertEqual(d["totals"]["wrong_tokens"], sum(t["wrong_tokens"] for t in d["tasks"]))
        self.assertEqual(d["totals"]["right_tokens"], sum(t["right_tokens"] for t in d["tasks"]))
        self.assertEqual(len(d["tasks"]), 6)
        self.assertEqual(d["provider"], "Anthropic Claude only")

    def test_headline_values(self):
        t = ptx.build()["totals"]
        self.assertEqual((t["wrong_tokens"], t["right_tokens"]), (56188, 12601))
        self.assertEqual((t["token_multiple"], t["cost_multiple"]), ("4.5x", "4.2x"))


class PagesQuoteOnlyTheDataTest(unittest.TestCase):
    """Every 'N.Nx' multiple and every 4-5 digit token count on the page must
    be a value from token-xray.json."""

    @classmethod
    def setUpClass(cls):
        d = ptx.build()
        cls.multiples = {d["totals"]["token_multiple"], d["totals"]["cost_multiple"],
                         d["big_model_small_task_cost_multiple"], d["growing_chat_40_tasks_estimate"],
                         *d["token_multiple_range"]}
        cls.counts = {d["totals"]["wrong_tokens"], d["totals"]["right_tokens"]}
        for t in d["tasks"]:
            cls.multiples |= {t["token_multiple"], t["cost_multiple"]}
            cls.counts |= {t["wrong_tokens"], t["right_tokens"]}
        cls.dollars = {f'${d["totals"]["wrong_usd"]:.3f}', f'${d["totals"]["right_usd"]:.3f}'}

    def _check(self, name: str):
        text = _visible_text((WEB / name).read_text(encoding="utf-8"))
        for m in re.findall(r"\b\d+(?:\.\d)?x\b", text):
            with self.subTest(page=name, multiple=m):
                self.assertIn(m, self.multiples)
        for n in re.findall(r"\b\d{1,3},\d{3}\b", text):
            with self.subTest(page=name, count=n):
                self.assertIn(int(n.replace(",", "")), self.counts)
        for usd in re.findall(r"\$0\.\d{3}\b", text):
            with self.subTest(page=name, usd=usd):
                self.assertIn(usd, self.dollars)

    def test_tokens_page(self):
        self._check("tokens.html")

    def test_home_page(self):
        self._check("home.html")

    def test_every_task_row_on_tokens_page(self):
        html = (WEB / "tokens.html").read_text(encoding="utf-8")
        for t in ptx.build()["tasks"]:
            with self.subTest(task=t["id"]):
                self.assertIn(f'{t["wrong_tokens"]:,} / {t["right_tokens"]:,}', html)
                self.assertIn(f'<td class="num">{t["token_multiple"]}</td><td class="num">{t["cost_multiple"]}</td>', html)

    def test_home_says_claude_only_and_six_tasks(self):
        html = (WEB / "home.html").read_text(encoding="utf-8")
        self.assertIn("6 everyday tasks", html)
        self.assertIn("Claude models only", html)


class RecordedWorkbenchRunTest(unittest.TestCase):
    REC = json.loads((WEB / "workbench-recorded-run.json").read_text(encoding="utf-8"))

    def test_is_a_completed_zero_cost_click(self):
        r = self.REC["response"]
        self.assertEqual(r["mode"], "sandbox")
        self.assertEqual(r["result"]["status"], "COMPLETED")
        self.assertEqual(r["result"]["checked_value"], r["result"]["new_value"])
        self.assertEqual(r["cost"], {"model_calls": 0, "tokens": 0, "usd": 0.0, "model_key_needed": False})
        self.assertIsNone(r["result"]["preview_id"])

    def test_workbench_shows_it_at_the_old_anchor(self):
        html = (WEB / "workbench.html").read_text(encoding="utf-8")
        self.assertIn('id="verified-run-panel"', html)
        self.assertIn("/workbench-recorded-run.json", (WEB / "workbench.js").read_text(encoding="utf-8"))

    def test_old_test_run_text_is_gone_from_the_site(self):
        for p in WEB.rglob("*"):
            if p.is_file() and p.suffix in (".html", ".js", ".json"):
                with self.subTest(file=p.name):
                    self.assertNotIn("saravanan", p.read_text(encoding="utf-8", errors="ignore").lower())


if __name__ == "__main__":
    unittest.main()
