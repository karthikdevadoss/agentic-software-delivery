"""Hermetic tests for scripts/live_check.py (no network)."""
import importlib.util
import json
import pathlib
import unittest

_PATH = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "live_check.py"
_spec = importlib.util.spec_from_file_location("live_check", _PATH)
live_check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(live_check)

HEADERS = {h: "x" for h in live_check.REQUIRED_HEADERS}
BUDGET = json.dumps({"gateway": {"daily_usd_cap": 5.0}})


def make_fetch(si_status, overrides=None):
    overrides = overrides or {}

    def fetch(url):
        path = url.split("example.test", 1)[1] or "/"
        if path in overrides:
            return overrides[path]
        if path == "/api/standing-interview/status":
            return 200, {}, json.dumps(si_status)
        if path == "/api/budget":
            return 200, {}, BUDGET
        return 200, dict(HEADERS), "<html></html>"
    return fetch


class LiveCheckTests(unittest.TestCase):
    def test_all_good_passes(self):
        f = live_check.check_base("https://example.test", make_fetch({"loaded": True, "chunks": 361}))
        self.assertEqual(f, [])

    def test_missing_corpus_fails(self):
        """The 25 Nov regression: pages 200, corpus absent. Must FAIL."""
        f = live_check.check_base(
            "https://example.test",
            make_fetch({"loaded": False, "chunks": 0, "reason": "no corpus file on this instance"}))
        self.assertEqual(len(f), 1)
        self.assertIn("Standing Interview has NO knowledge base", f[0])
        self.assertIn("deploy_platform_with_si_corpus.sh", f[0])

    def test_loaded_but_zero_chunks_fails(self):
        f = live_check.check_base("https://example.test", make_fetch({"loaded": True, "chunks": 0}))
        self.assertTrue(any("NO knowledge base" in x for x in f))

    def test_broken_page_fails(self):
        f = live_check.check_base(
            "https://example.test",
            make_fetch({"loaded": True, "chunks": 5}, {"/workbench": (502, {}, "bad gateway")}))
        self.assertTrue(any("/workbench: HTTP 502" in x for x in f))

    def test_missing_security_header_fails(self):
        hdrs = dict(HEADERS)
        del hdrs["strict-transport-security"]
        f = live_check.check_base(
            "https://example.test",
            make_fetch({"loaded": True, "chunks": 5}, {"/": (200, hdrs, "")}))
        self.assertTrue(any("strict-transport-security" in x for x in f))

    def test_standing_interview_is_checked_as_a_page(self):
        self.assertIn("/standing-interview", live_check.PAGES)


if __name__ == "__main__":
    unittest.main()
