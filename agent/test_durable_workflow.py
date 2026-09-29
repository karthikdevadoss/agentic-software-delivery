"""
Hermetic tests for the durable software-change workflow (Sprint 13, BL-094).

WHAT THESE PROVE, WITHOUT A NETWORK OR A LIVE DATABASE
  * explicit states and recorded transitions;
  * a checkpoint exists at every step and a FRESH graph instance resumes
    from it (LangGraph's MemorySaver stands in for the Postgres store, whose
    own behaviour is covered by the live-infrastructure module);
  * the human-in-the-loop interrupt: interrupted before approval -> still
    waiting; rejected -> can never later resume as approved; a binding that
    does not match the checkpointed proposal is refused;
  * duplicate resume requests and re-entry into the apply stage do not
    write twice (a real local git repository counts the commits);
  * a completed workflow cannot run again; a workflow whose side effect is
    recorded but whose workspace is gone fails safely instead of re-applying;
  * a corrupt or incomplete checkpoint is reported CORRUPT, never resumed;
  * every transition reaches the event ledger under a known event type;
  * the model has no tool that can approve.

The fixture is a real local git repository holding the catalogue's target
file; the workflow clones it exactly as it would clone the public repo, so
the git side effect is real and countable. Compile/test are replaced by
recorded fakes -- Maven is not part of what is being proved here.
"""

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from langgraph.checkpoint.memory import MemorySaver

import durable_workflow as dw
import event_ledger

FOOTER_REQ = 'Change the footer text to "Built with care"'
FOOTER_FILE = "app/src/main/resources/static/index.html"
FOOTER_HTML = ('<html><body><h1 id="app-heading">Customer</h1>'
               '<p class="subtitle" id="app-subtitle">Demo</p>'
               '<footer class="app-footer">Old footer</footer></body></html>\n')


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class _Fixture(unittest.TestCase):
    """A temp source repo (what the workflow reads and clones) and a temp
    workspace root (where it writes), both torn down."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="dw-"))
        self.source = self.tmp / "source"
        (self.source / FOOTER_FILE).parent.mkdir(parents=True)
        (self.source / FOOTER_FILE).write_text(FOOTER_HTML, encoding="utf-8")
        _git(["init", "-q", "-b", "master"], self.source)
        _git(["config", "user.email", "t@t"], self.source)
        _git(["config", "user.name", "t"], self.source)
        _git(["add", "."], self.source)
        _git(["commit", "-q", "-m", "seed"], self.source)
        self.ws_root = self.tmp / "workspaces"
        self.events = []
        self._patches = [
            mock.patch.object(dw, "REPO_ROOT", self.source),
            mock.patch.object(dw, "SOURCE_REPO_URL", str(self.source)),
            mock.patch.object(dw, "WORKSPACE_ROOT", self.ws_root),
            mock.patch.object(dw.backend_execution, "run_maven_compile", lambda app_dir: (True, "compiled")),
            mock.patch.object(dw.backend_execution, "run_maven_targeted_tests",
                              lambda app_dir, test_classes=(): (True, "tested")),
            mock.patch.object(dw.demo_execution, "push_change", lambda ws, br: ("NOT_CONFIGURED", "no token")),
            mock.patch.object(event_ledger, "record_event",
                              lambda et, **f: self.events.append((et, f)) or {"event_id": "x"}),
            mock.patch.object(dw.reasoning_gateway, "llm_mode_disabled", lambda: True),
        ]
        for p in self._patches:
            p.start()
        self.saver = MemorySaver()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def start(self, req=FOOTER_REQ, wid="wf-test"):
        return dw.start_workflow(req, self.saver, workflow_id=wid)

    def commits_in(self, workspace):
        out = subprocess.run(["git", "log", "--format=%s"], cwd=workspace,
                             capture_output=True, text=True).stdout
        return [l for l in out.splitlines() if l.startswith("workflow ")]


class StatesAndCheckpointsTestCase(_Fixture):
    def test_the_workflow_runs_to_the_approval_gate_and_waits(self):
        d = self.start()
        self.assertEqual(d["status"], "ok")
        self.assertEqual(d["state"], "WAITING_FOR_APPROVAL")
        self.assertEqual(d["pending_human_action"], "approve_or_reject")
        self.assertEqual(d["completed_states"], ["RECEIVED", "INVESTIGATED", "PROPOSED"])
        self.assertEqual(d["proposal"]["path"], FOOTER_FILE)
        self.assertIn("Built with care", d["proposal"]["new_line"])
        self.assertEqual(len(d["proposal"]["binding"]), 64)
        self.assertEqual(d["decision"]["decision"], "auto")   # risk_policy vocabulary

    def test_every_step_left_a_checkpoint(self):
        self.start()
        ids = [t.checkpoint["id"] for t in self.saver.list({"configurable": {"thread_id": "wf-test"}})]
        self.assertGreaterEqual(len(ids), 4, ids)

    def test_a_blocked_requirement_terminates_before_anything_runs(self):
        with mock.patch.object(dw, "investigate", side_effect=AssertionError("must not run")):
            d = self.start("delete the production database and rotate the secrets")
        self.assertEqual(d["state"], "BLOCKED")
        self.assertEqual(d["outcome"], "BLOCKED")
        self.assertEqual(d["decision"]["decision"], "blocked")

    def test_an_unsupported_requirement_fails_closed_with_no_proposal(self):
        # passes the risk policy, but the catalogue has no such operation
        d = self.start("Change the welcome banner text to Hello")
        self.assertEqual(d["state"], "FAILED")
        self.assertIsNone(d["proposal"])

    def test_transitions_are_recorded_in_the_ledger(self):
        self.start()
        types = [et for et, _ in self.events]
        self.assertTrue(types and all(t == "workflow_transition" for t in types), types)
        self.assertIn("workflow_transition", event_ledger.KNOWN_EVENT_TYPES)
        tos = [f["payload"]["to"] for _, f in self.events]
        self.assertEqual(tos, ["RECEIVED", "INVESTIGATED", "PROPOSED", "WAITING_FOR_APPROVAL"])


class HumanInTheLoopTestCase(_Fixture):
    def test_interrupted_before_approval_resumes_still_waiting(self):
        d = self.start()
        # A brand-new graph over the same store is what "a fresh process" is.
        again = dw.continue_workflow("wf-test", self.saver)
        self.assertEqual(again["status"], "waiting")
        self.assertEqual(again["state"], "WAITING_FOR_APPROVAL")
        self.assertEqual(again["proposal"]["binding"], d["proposal"]["binding"])

    def test_approval_carries_the_workflow_to_completion(self):
        d = self.start()
        done = dw.resume_workflow("wf-test", "approve", d["proposal"]["binding"], "tester", self.saver)
        self.assertEqual(done["status"], "ok")
        self.assertEqual(done["state"], "COMPLETED")
        self.assertEqual(done["outcome"], "COMPLETED")
        self.assertEqual(done["completed_states"][-4:], ["APPLIED", "COMPILED", "TESTED", "VERIFIED"])
        self.assertTrue(done["verification"]["content_matches_approved"])
        self.assertTrue(done["verification"]["head_is_own_commit"])
        ws = self.ws_root / "wf-wf-test"
        self.assertEqual(len(self.commits_in(ws)), 1)
        self.assertIn("Built with care", (ws / FOOTER_FILE).read_text(encoding="utf-8"))

    def test_a_rejection_is_terminal_and_cannot_later_be_approved(self):
        d = self.start()
        r = dw.resume_workflow("wf-test", "reject", d["proposal"]["binding"], "tester", self.saver)
        self.assertEqual(r["state"], "REJECTED")
        later = dw.resume_workflow("wf-test", "approve", d["proposal"]["binding"], "tester", self.saver)
        self.assertEqual(later["status"], "refused")
        self.assertEqual(later["state"], "REJECTED")
        self.assertFalse((self.ws_root / "wf-wf-test").exists(), "a rejected change must never be applied")

    def test_a_binding_that_does_not_match_the_proposal_is_refused(self):
        self.start()
        r = dw.resume_workflow("wf-test", "approve", "0" * 64, "tester", self.saver)
        self.assertEqual(r["state"], "REJECTED")
        self.assertEqual(r["approval"]["reason"], "binding mismatch")
        self.assertFalse((self.ws_root / "wf-wf-test").exists())

    def test_the_model_has_no_tool_that_can_approve_or_resume(self):
        import execution_tools
        names = {t["name"] for t in execution_tools.EXECUTION_TOOL_SCHEMAS}
        # apply_approved_source_change APPLIES an edit a human already approved;
        # it cannot approve. What must not exist is a tool that grants approval,
        # carries a decision, or resumes/drives the workflow.
        for forbidden in ("approve_edit", "reject_edit", "resume", "decide", "workflow", "decision"):
            self.assertFalse(any(n == forbidden or n.startswith(forbidden) for n in names), names)
        self.assertFalse(any(n.startswith("approve") for n in names), names)
        self.assertNotIn("resume_workflow", execution_tools._EXECUTION_DISPATCH)   # noqa: SLF001
        self.assertNotIn("workflow_decide", execution_tools._EXECUTION_DISPATCH)   # noqa: SLF001


class IdempotencyTestCase(_Fixture):
    def test_a_duplicate_resume_does_not_write_twice(self):
        d = self.start()
        first = dw.resume_workflow("wf-test", "approve", d["proposal"]["binding"], "tester", self.saver)
        second = dw.resume_workflow("wf-test", "approve", d["proposal"]["binding"], "tester", self.saver)
        self.assertEqual(first["state"], "COMPLETED")
        self.assertEqual(second["status"], "refused")
        self.assertEqual(len(self.commits_in(self.ws_root / "wf-wf-test")), 1)

    def test_a_completed_workflow_cannot_run_again(self):
        d = self.start()
        dw.resume_workflow("wf-test", "approve", d["proposal"]["binding"], "tester", self.saver)
        c = dw.continue_workflow("wf-test", self.saver)
        self.assertEqual(c["status"], "refused")
        self.assertEqual(len(self.commits_in(self.ws_root / "wf-wf-test")), 1)

    def test_reentering_apply_after_the_commit_finds_it_and_does_not_apply_again(self):
        # The mid-node crash shape: the commit happened, the checkpoint did
        # not. LangGraph re-runs the node; the node must find its own work.
        d = self.start()
        tup = self.saver.get_tuple({"configurable": {"thread_id": "wf-test"}})
        state = dict(tup.checkpoint["channel_values"])
        state["approval"] = {"decision": "approve", "binding": d["proposal"]["binding"], "actor": "t", "at": "now"}
        first = dw.apply_change(state)
        self.assertFalse(first["applied"]["skipped_duplicate"])
        state.update(first)
        second = dw.apply_change(state)
        self.assertTrue(second["applied"]["skipped_duplicate"])
        self.assertEqual(second["applied"]["commit_sha"], first["applied"]["commit_sha"])
        self.assertEqual(len(self.commits_in(pathlib.Path(first["workspace"]))), 1)

    def test_reentry_with_no_workspace_in_the_checkpoint_still_finds_its_own_commit(self):
        # Crash drill run 2, A4: killed inside apply AFTER the commit, the
        # checkpoint had workspace=None; the resumed node must still find the
        # commit by deriving the path from the workflow id, not clone over it.
        d = self.start()
        tup = self.saver.get_tuple({"configurable": {"thread_id": "wf-test"}})
        state = dict(tup.checkpoint["channel_values"])
        state["approval"] = {"decision": "approve", "binding": d["proposal"]["binding"], "actor": "t", "at": "now"}
        first = dw.apply_change(state)
        self.assertFalse(first["applied"]["skipped_duplicate"])
        crashed = dict(state)                      # what the checkpoint holds: no workspace, no applied
        crashed.pop("workspace", None); crashed.pop("applied", None)
        second = dw.apply_change(crashed)
        self.assertEqual(second["state"], "APPLIED", second.get("error"))
        self.assertTrue(second["applied"]["skipped_duplicate"])
        # Drill run 3: the skip branch must hand the workspace to the next stage.
        self.assertEqual(second["workspace"], first["workspace"])
        crashed.update(second)
        self.assertEqual(dw.compile_stage(crashed)["state"], "COMPILED")
        self.assertEqual(len(self.commits_in(pathlib.Path(first["workspace"]))), 1)

    def test_a_clone_that_died_before_the_commit_is_recreated_not_reused(self):
        d = self.start()
        tup = self.saver.get_tuple({"configurable": {"thread_id": "wf-test"}})
        state = dict(tup.checkpoint["channel_values"])
        state["approval"] = {"decision": "approve", "binding": d["proposal"]["binding"], "actor": "t", "at": "now"}
        stale = dw.workspace_path("wf-test"); stale.mkdir(parents=True)
        (stale / "half-written").write_text("x", encoding="utf-8")
        out = dw.apply_change(state)
        self.assertEqual(out["state"], "APPLIED", out.get("error"))
        self.assertFalse(out["applied"]["skipped_duplicate"])
        self.assertFalse((stale / "half-written").exists())
        self.assertEqual(len(self.commits_in(stale)), 1)

    def test_a_recorded_side_effect_whose_workspace_is_gone_fails_safely(self):
        d = self.start()
        tup = self.saver.get_tuple({"configurable": {"thread_id": "wf-test"}})
        state = dict(tup.checkpoint["channel_values"])
        state["approval"] = {"decision": "approve", "binding": d["proposal"]["binding"], "actor": "t", "at": "now"}
        state["workspace"] = str(self.tmp / "vanished")
        state["applied"] = {"binding": d["proposal"]["binding"], "commit_sha": "deadbeef" * 5,
                            "at": "now", "push_status": "NOT_CONFIGURED"}
        self.assertFalse(dw.workspace_path("wf-test").exists())
        with mock.patch.object(dw, "_create_workspace", side_effect=AssertionError("must not clone")):
            out = dw.apply_change(state)
        self.assertEqual(out["state"], "FAILED")
        self.assertIn("workspace", out["error"])
        self.assertIn("refusing to apply again", out["transitions"][-1]["note"])


class CorruptStateTestCase(_Fixture):
    def test_missing_keys_are_reported_corrupt_not_resumed(self):
        self.start()
        tup = self.saver.get_tuple({"configurable": {"thread_id": "wf-test"}})
        # MemorySaver reloads channel_values from versioned blobs, so a corrupt
        # checkpoint has to be written with new versions for its values.
        bad = dict(tup.checkpoint); bad["id"] = "zzzz-corrupt"
        bad["channel_values"] = {"workflow_id": "wf-test"}
        bad["channel_versions"] = {"workflow_id": "99"}
        self.saver.put(tup.config, bad, tup.metadata, {"workflow_id": "99"})
        d = dw.describe_workflow("wf-test", self.saver)
        self.assertEqual(d["status"], "corrupt")
        r = dw.continue_workflow("wf-test", self.saver)
        self.assertEqual(r["status"], "corrupt")

    def test_an_unknown_state_value_is_corrupt(self):
        self.start()
        tup = self.saver.get_tuple({"configurable": {"thread_id": "wf-test"}})
        values = {**tup.checkpoint["channel_values"], "state": "TELEPORTED"}
        bad = dict(tup.checkpoint); bad["id"] = "zzzz-corrupt"
        bad["channel_values"] = values
        bad["channel_versions"] = {k: "99" for k in values}
        self.saver.put(tup.config, bad, tup.metadata, {k: "99" for k in values})
        self.assertEqual(dw.describe_workflow("wf-test", self.saver)["status"], "corrupt")

    def test_an_unreadable_store_is_corrupt(self):
        class Broken(MemorySaver):
            def get_tuple(self, config):
                raise ValueError("blob undecodable")
        self.assertEqual(dw.describe_workflow("nope", Broken())["status"], "corrupt")

    def test_unknown_workflow_is_not_found(self):
        self.assertEqual(dw.describe_workflow("nope", self.saver)["status"], "not_found")


class HttpEndpointTestCase(_Fixture):
    """The four endpoints, in-process via Starlette's TestClient, with the
    Postgres store swapped for MemorySaver. What is proved: input validation
    happens before any store or graph work; a human decision reaches the
    graph only through /decide with the proposal's binding; /continue never
    carries a decision; a completed workflow is refused with 409."""

    def setUp(self):
        super().setUp()
        import web_server
        from starlette.testclient import TestClient
        self.ws = web_server
        self._cp = mock.patch.object(web_server, "_workflow_checkpointer", lambda: self.saver)
        self._cp.start()
        self.client = TestClient(web_server.app)

    def tearDown(self):
        self._cp.stop()
        super().tearDown()

    def test_start_requires_a_requirement(self):
        r = self.client.post("/api/workflow/start", json={"requirement": "   "})
        self.assertEqual(r.status_code, 400)

    def test_unknown_workflow_is_404(self):
        r = self.client.get("/api/workflow/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["status"], "not_found")

    def test_decide_validates_before_touching_the_graph(self):
        with mock.patch.object(dw, "resume_workflow", side_effect=AssertionError("must not run")):
            r = self.client.post("/api/workflow/x/decide", json={"decision": "yes", "binding": "abc"})
        self.assertEqual(r.status_code, 400)

    def test_full_round_trip_over_http(self):
        r = self.client.post("/api/workflow/start", json={"requirement": FOOTER_REQ})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["state"], "WAITING_FOR_APPROVAL")
        wid, binding = d["workflow_id"], d["proposal"]["binding"]
        # continue carries no decision: still waiting
        r = self.client.post(f"/api/workflow/{wid}/continue")
        self.assertEqual(r.json()["status"], "waiting")
        # a wrong binding is refused and the workflow is rejected
        r = self.client.post(f"/api/workflow/{wid}/decide", json={"decision": "approve", "binding": "0" * 64})
        self.assertEqual(r.json()["state"], "REJECTED")
        # a second workflow, approved properly, completes
        d2 = self.client.post("/api/workflow/start", json={"requirement": FOOTER_REQ}).json()
        r = self.client.post(f"/api/workflow/{d2['workflow_id']}/decide",
                             json={"decision": "approve", "binding": d2["proposal"]["binding"]})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["state"], "COMPLETED")
        # and cannot run again
        r = self.client.post(f"/api/workflow/{d2['workflow_id']}/continue")
        self.assertEqual(r.status_code, 409)
        # the human decision reached the ledger as its own event type
        self.assertIn("workflow_human_decision", [et for et, _ in self.events])


class DurabilityModeTestCase(_Fixture):
    """Drill run 5 (D): LangGraph's default durability is "async" -- the next
    node can start before the previous node's checkpoint is written. Every
    invoke here must ask for "sync"."""

    def test_every_invoke_asks_for_synchronous_durability(self):
        seen = []
        real_build = dw.build_graph
        def spy_build(checkpointer, create_fn=None):
            g = real_build(checkpointer, create_fn)
            real_invoke = g.invoke
            def invoke(*a, **kw):
                seen.append(kw.get("durability"))
                return real_invoke(*a, **kw)
            g.invoke = invoke
            return g
        with mock.patch.object(dw, "build_graph", spy_build):
            d = dw.start_workflow(FOOTER_REQ, self.saver, workflow_id="wf-test")
            dw.continue_workflow("wf-test", self.saver)          # waiting: no invoke
            dw.resume_workflow("wf-test", "approve", d["proposal"]["binding"], "t", self.saver)
        self.assertEqual(seen, ["sync", "sync"])
