"""Hermetic tests for the GitHub knowledge pipeline (github_knowledge.py).

No network, no model: GitHub responses are fixtures and the embedder is a
deterministic bag-of-words stand-in that counts how many texts it embedded.
"""
import json
import unittest
from unittest import mock

import github_knowledge as gk

VOCAB = ["budget", "postgres", "kraken", "page", "eval", "injection", "video",
         "nav", "deleted", "readme", "draft", "merged", "open", "closed", "tour", "secret"]


class FakeEmbedder:
    def __init__(self):
        self.embedded = 0

    def texts(self, texts):
        self.embedded += len(texts)
        return [self.query(t) for t in texts]

    @staticmethod
    def query(text):
        words = text.lower().split()
        return [float(sum(w.startswith(v) for w in words)) + 0.01 for v in VOCAB]


def pr(n, title, body="", state="closed", merged=True, updated="2026-11-26T10:00:00Z"):
    return {"number": n, "title": title, "body": body, "state": state, "html_url": f"https://x/{n}",
            "updated_at": updated, "pull_request": {"merged_at": "2026-11-26T10:00:00Z" if merged else None}}


def issue(n, title, body="", state="open"):
    return {"number": n, "title": title, "body": body, "state": state, "html_url": f"https://x/i{n}",
            "updated_at": "2026-11-26T09:00:00Z"}


V1 = [pr(1, "Budget caps in postgres"), pr(2, "Kraken page"), pr(3, "Draft video", merged=False, state="open"),
      issue(4, "Deleted secret issue", "secret secret")]
# v2: #2 retitled, #3 merged, #4 deleted, #5 new, #1 untouched.
V2 = [pr(1, "Budget caps in postgres"), pr(2, "Kraken page with tour"),
      pr(3, "Draft video", merged=True, state="closed", updated="2026-11-26T12:00:00Z"),
      pr(5, "Injection eval")]


class GithubKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.store, self.emb = gk.KnowledgeStore(), FakeEmbedder()

    def _sync(self, items, at):
        return gk.sync(self.store, items, self.emb.texts, now=at)

    def test_normalize_states_and_kinds(self):
        self.assertEqual(gk.normalize(pr(1, "t"))["state"], "merged")
        self.assertEqual(gk.normalize(pr(3, "t", merged=False, state="open"))["state"], "open")
        d = gk.normalize(issue(4, "t"))
        self.assertEqual((d["kind"], d["key"], d["access_level"]), ("issue", "issue#4", "public"))

    def test_first_sync_embeds_everything(self):
        r = self._sync(V1, "t1")
        self.assertEqual((r["added"], r["updated"], r["deleted"], r["embedded"]), (4, 0, 0, 4))

    def test_second_sync_embeds_only_changed_and_removes_deleted(self):
        self._sync(V1, "t1")
        self.emb.embedded = 0
        r = self._sync(V2, "t2")
        self.assertEqual((r["added"], r["updated"], r["unchanged"], r["deleted"]), (1, 2, 1, 1))
        self.assertEqual(self.emb.embedded, 3, "only #2, #3 and the new #5 may be re-embedded")
        self.assertEqual(self.store.docs["pr#1"]["indexed_at"], "t1", "unchanged doc keeps its index time")
        self.assertEqual(self.store.docs["pr#3"]["indexed_at"], "t2")

    def test_deleted_item_is_never_returned(self):
        self._sync(V1, "t1")
        self._sync(V2, "t2")
        hits = gk.search(self.store, "deleted secret issue", FakeEmbedder.query, k=10)
        self.assertNotIn("issue#4", [h["key"] for h in hits])
        self.assertFalse(any("secret" in h["excerpt"] for h in hits))

    def test_answers_reflect_latest_state_with_freshness(self):
        self._sync(V1, "t1")
        self._sync(V2, "t2")
        top = gk.search(self.store, "draft video merged", FakeEmbedder.query, k=1)[0]
        self.assertEqual((top["key"], top["state"]), ("pr#3", "merged"))
        self.assertEqual(top["updated_at"], "2026-11-26T12:00:00Z")
        self.assertEqual((top["indexed_at"], top["synced_at"]), ("t2", "t2"))
        old = [h for h in gk.search(self.store, "kraken page", FakeEmbedder.query, k=5) if h["key"] == "pr#2"][0]
        self.assertIn("with tour", old["title"])

    def test_failed_embedding_keeps_last_good_index(self):
        self._sync(V1, "t1")

        def boom(_):
            raise RuntimeError("embedder down")
        with self.assertRaises(RuntimeError):
            gk.sync(self.store, V2, boom, now="t2")
        self.assertIn("issue#4", self.store.docs)
        self.assertEqual(self.store.synced_at, "t1")

    def test_failed_fetch_keeps_last_good_index_and_reports(self):
        self._sync(V1, "t1")
        def down(_url):
            raise OSError("rate limited")
        with mock.patch.object(gk, "_embed_fns", lambda: (self.emb.texts, FakeEmbedder.query)):
            r = gk.sync_live(self.store, get_json=down)
        self.assertIn("rate limited", r["error"])
        self.assertEqual(len(self.store.docs), 4)
        self.assertIn("rate limited", self.store.status()["last_error"])

    def test_fetch_paginates_and_stops(self):
        pages = {1: [pr(i, "t") for i in range(100)], 2: [pr(100 + i, "t") for i in range(7)]}
        calls = []

        def get(url):
            n = int(url.rsplit("page=", 1)[1])
            calls.append(n)
            return pages.get(n, [])
        self.assertEqual(len(gk.fetch_items(get)), 107)
        self.assertEqual(calls, [1, 2])

    def test_committed_snapshot_is_valid_and_public_repo_only(self):
        snap = json.loads(gk.SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(snap["repo"], gk.REPO)
        self.assertGreater(len(snap["items"]), 0)
        for it in snap["items"]:
            self.assertTrue(it["html_url"].startswith(f"https://github.com/{gk.REPO}/"))


if __name__ == "__main__":
    unittest.main()
