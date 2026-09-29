"""
LIVE-INFRASTRUCTURE tests for the Postgres checkpoint store (BL-094).

Needs EVENT_LEDGER_DATABASE_URL (the same Railway Postgres that holds the
event ledger). Deliberately NOT in the hermetic CI tier -- see
agent/ci_python_tests.py's LIVE_INFRA_MODULES. Every thread id used here is
unique and deleted at the end, so nothing is left in the shared database.

What is proven against the REAL store, not a fake:
  * put / get_tuple round-trip of a checkpoint with channel_values;
  * latest-wins when several checkpoints exist for a thread;
  * pending writes survive and come back with the checkpoint;
  * list() ordering and limit;
  * a corrupt blob raises (so describe_workflow reports CORRUPT);
  * delete_thread leaves no rows behind;
  * the whole durable graph runs through this store: start -> waiting,
    then a FRESH checkpointer instance (a new connection, no cache) resumes
    it to completion with exactly one commit.
"""

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import uuid
from unittest import mock

try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import event_ledger
import workflow_checkpointer as wc

HAVE_DB = bool(os.environ.get("EVENT_LEDGER_DATABASE_URL"))


def _cfg(tid, cid=None):
    return {"configurable": {"thread_id": tid, "checkpoint_ns": "", "checkpoint_id": cid}}


def _ckpt(cid, values):
    return {"v": 1, "id": cid, "ts": "2026-09-29T00:00:00+00:00", "channel_values": values,
            "channel_versions": {k: "1" for k in values}, "versions_seen": {}, "updated_channels": list(values)}


@unittest.skipUnless(HAVE_DB, "EVENT_LEDGER_DATABASE_URL not set -- live store not reachable")
class PostgresCheckpointerTestCase(unittest.TestCase):
    def setUp(self):
        self.saver = wc.PostgresWorkflowCheckpointer()
        self.tid = "test-" + uuid.uuid4().hex[:10]

    def tearDown(self):
        self.saver.delete_thread(self.tid)

    def test_put_and_get_round_trip_with_values(self):
        cfg = self.saver.put(_cfg(self.tid), _ckpt("0001", {"state": "RECEIVED", "n": 1}),
                             {"source": "input", "step": 0, "parents": {}}, {"state": "1", "n": "1"})
        self.assertEqual(cfg["configurable"]["checkpoint_id"], "0001")
        tup = self.saver.get_tuple(_cfg(self.tid))
        self.assertEqual(tup.checkpoint["channel_values"], {"state": "RECEIVED", "n": 1})
        self.assertEqual(tup.metadata["step"], 0)
        self.assertIsNone(tup.parent_config)

    def test_latest_checkpoint_wins_and_parent_is_linked(self):
        c1 = self.saver.put(_cfg(self.tid), _ckpt("0001", {"state": "RECEIVED"}), {"step": 0}, {})
        self.saver.put(c1, _ckpt("0002", {"state": "PROPOSED"}), {"step": 1}, {})
        tup = self.saver.get_tuple(_cfg(self.tid))
        self.assertEqual(tup.checkpoint["id"], "0002")
        self.assertEqual(tup.parent_config["configurable"]["checkpoint_id"], "0001")
        old = self.saver.get_tuple(_cfg(self.tid, "0001"))
        self.assertEqual(old.checkpoint["channel_values"]["state"], "RECEIVED")

    def test_pending_writes_survive(self):
        cfg = self.saver.put(_cfg(self.tid), _ckpt("0001", {"state": "WAITING"}), {"step": 0}, {})
        self.saver.put_writes(cfg, [("__interrupt__", {"action": "approve_or_reject"})], task_id="t1")
        tup = self.saver.get_tuple(_cfg(self.tid))
        self.assertEqual(tup.pending_writes, [("t1", "__interrupt__", {"action": "approve_or_reject"})])

    def test_list_orders_newest_first_and_honours_limit(self):
        c = _cfg(self.tid)
        for i in range(1, 4):
            c = self.saver.put(c, _ckpt(f"000{i}", {"state": f"S{i}"}), {"step": i}, {})
        ids = [t.checkpoint["id"] for t in self.saver.list(_cfg(self.tid))]
        self.assertEqual(ids, ["0003", "0002", "0001"])
        self.assertEqual(len(list(self.saver.list(_cfg(self.tid), limit=2))), 2)

    def test_a_corrupt_blob_raises_rather_than_returning_partial_state(self):
        self.saver.put(_cfg(self.tid), _ckpt("0001", {"state": "RECEIVED"}), {"step": 0}, {})
        conn = event_ledger._connect()   # noqa: SLF001
        try:
            with conn, conn.cursor() as cur:
                cur.execute("UPDATE workflow_checkpoints SET checkpoint=%s WHERE thread_id=%s",
                            (wc.psycopg2_binary(b"\x00garbage"), self.tid))
        finally:
            conn.close()
        with self.assertRaises(Exception):
            self.saver.get_tuple(_cfg(self.tid))

    def test_delete_thread_leaves_nothing(self):
        cfg = self.saver.put(_cfg(self.tid), _ckpt("0001", {"state": "RECEIVED"}), {"step": 0}, {})
        self.saver.put_writes(cfg, [("x", 1)], task_id="t1")
        self.saver.delete_thread(self.tid)
        self.assertIsNone(self.saver.get_tuple(_cfg(self.tid)))


@unittest.skipUnless(HAVE_DB, "EVENT_LEDGER_DATABASE_URL not set -- live store not reachable")
class GraphOnRealStoreTestCase(unittest.TestCase):
    """The whole graph, on the real store, resumed by a FRESH instance."""

    FOOTER_REQ = 'Change the footer text to "Built with care"'
    FOOTER_FILE = "app/src/main/resources/static/index.html"

    def setUp(self):
        import durable_workflow as dw
        self.dw = dw
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="dwlive-"))
        src = self.tmp / "source"
        (src / self.FOOTER_FILE).parent.mkdir(parents=True)
        (src / self.FOOTER_FILE).write_text('<footer class="app-footer">Old</footer>\n', encoding="utf-8")
        for args in (["init", "-q", "-b", "master"], ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"], ["add", "."], ["commit", "-q", "-m", "seed"]):
            subprocess.run(["git", *args], cwd=src, check=True, capture_output=True)
        self.wid = "live-" + uuid.uuid4().hex[:10]
        self._patches = [
            mock.patch.object(dw, "REPO_ROOT", src),
            mock.patch.object(dw, "SOURCE_REPO_URL", str(src)),
            mock.patch.object(dw, "WORKSPACE_ROOT", self.tmp / "ws"),
            mock.patch.object(dw.backend_execution, "run_maven_compile", lambda a: (True, "ok")),
            mock.patch.object(dw.backend_execution, "run_maven_targeted_tests", lambda a, test_classes=(): (True, "ok")),
            mock.patch.object(dw.demo_execution, "push_change", lambda w, b: ("NOT_CONFIGURED", "")),
            mock.patch.object(dw.reasoning_gateway, "llm_mode_disabled", lambda: True),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        wc.PostgresWorkflowCheckpointer().delete_thread(self.wid)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_start_then_resume_from_a_fresh_instance(self):
        first = wc.PostgresWorkflowCheckpointer()
        d = self.dw.start_workflow(self.FOOTER_REQ, first, workflow_id=self.wid)
        self.assertEqual(d["state"], "WAITING_FOR_APPROVAL")
        fresh = wc.PostgresWorkflowCheckpointer()          # no shared cache
        again = self.dw.describe_workflow(self.wid, fresh)
        self.assertEqual(again["state"], "WAITING_FOR_APPROVAL")
        done = self.dw.resume_workflow(self.wid, "approve", d["proposal"]["binding"], "live-test", fresh)
        self.assertEqual(done["state"], "COMPLETED", done.get("error"))
        log = subprocess.run(["git", "log", "--format=%s"], cwd=done["applied"] and (self.tmp / "ws" / f"wf-{self.wid}"),
                             capture_output=True, text=True).stdout
        self.assertEqual(sum(1 for l in log.splitlines() if l.startswith("workflow ")), 1)
        # and a third instance sees it as terminal
        self.assertEqual(self.dw.continue_workflow(self.wid, wc.PostgresWorkflowCheckpointer())["status"], "refused")
