"""
Layer 6 (real git, not mocks-only) and Layer 7 (deployment identity)
tests for agent/demo_execution.py (RELIABILITY/CORRECTION PHASE,
2026-09-13).

Every git-workflow test here uses a REAL local git repository (a plain
`git init` directory acting as "origin") — never a mock of `subprocess`
or of git's own behavior, per the Owner's explicit requirement that
critical Git evidence not rest on mocks alone. Railway-dependent
functions (deployment listing/waiting) ARE mocked here (no real Railway
account access from a test suite) but are exercised as real subprocess
calls elsewhere in this task's real production acceptance run.

Run: python agent/test_demo_execution.py
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import demo_execution as de


def _git(args, cwd):
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


class RealLocalGitWorkflowTestCase(unittest.TestCase):
    """A real, disposable local git repository stands in for 'the real
    public GitHub repo' — create_isolated_workspace/commit_change/
    get_commit_sha/get_changed_files/push_to_remote are exercised against
    genuine git subprocess calls end to end."""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp(prefix="test-origin-")
        self.addCleanup(lambda: shutil.rmtree(self.tmp_root, ignore_errors=True))
        self.origin = Path(self.tmp_root) / "origin"
        self.origin.mkdir()
        _git(["init", "-q", "-b", "master"], self.origin)
        _git(["config", "user.email", "test@example.com"], self.origin)
        _git(["config", "user.name", "Test"], self.origin)
        (self.origin / "app").mkdir()
        (self.origin / "app" / "src" / "main" / "resources" / "static").mkdir(parents=True)
        self.target_rel = "app/src/main/resources/static/index.html"
        (self.origin / self.target_rel).write_text("<footer>OLD</footer>\n", encoding="utf-8")
        (self.origin / "README.md").write_text("hello\n", encoding="utf-8")
        _git(["add", "-A"], self.origin)
        _git(["commit", "-q", "-m", "initial"], self.origin)
        self.workspaces = []
        self.addCleanup(self._cleanup_workspaces)

    def _cleanup_workspaces(self):
        for w in self.workspaces:
            de.cleanup_workspace(w)

    def _clone(self, run_id="run-abc12345"):
        workspace, ok, out = de.create_isolated_workspace(run_id, repo_url=str(self.origin))
        self.workspaces.append(workspace)
        self.assertTrue(ok, out)
        return workspace

    def test_create_isolated_workspace_really_clones_the_repo(self):
        workspace = self._clone()
        self.assertTrue((workspace / self.target_rel).is_file())
        self.assertTrue((workspace / ".git").is_dir())

    def test_cleanup_workspace_really_removes_the_directory(self):
        workspace = self._clone()
        self.assertTrue(workspace.exists())
        de.cleanup_workspace(workspace)
        self.assertFalse(workspace.exists())
        self.workspaces.remove(workspace)

    def test_commit_change_creates_dedicated_branch_not_master(self):
        workspace = self._clone()
        (workspace / self.target_rel).write_text("<footer>NEW</footer>\n", encoding="utf-8")
        branch, ok, out = de.commit_change(workspace, "run-abc12345", self.target_rel, "Demo: change footer")
        self.assertTrue(ok, out)
        self.assertEqual(branch, "demo/run-abc12345")
        current_branch = _git(["branch", "--show-current"], workspace).strip()
        self.assertEqual(current_branch, "demo/run-abc12345")
        self.assertNotEqual(current_branch, "master")

    def test_commit_change_only_commits_the_named_file(self):
        workspace = self._clone()
        (workspace / self.target_rel).write_text("<footer>NEW</footer>\n", encoding="utf-8")
        (workspace / "README.md").write_text("UNRELATED CHANGE THAT MUST NOT BE COMMITTED\n", encoding="utf-8")
        branch, ok, out = de.commit_change(workspace, "run-xyz", self.target_rel, "Demo: change footer")
        self.assertTrue(ok, out)
        changed = de.get_changed_files(workspace)
        self.assertEqual(changed, [self.target_rel])
        # The unrelated edit is still sitting uncommitted in the working tree.
        status = _git(["status", "--porcelain"], workspace)
        self.assertIn("README.md", status)

    def test_get_commit_sha_matches_real_git_rev_parse(self):
        workspace = self._clone()
        (workspace / self.target_rel).write_text("<footer>NEW</footer>\n", encoding="utf-8")
        de.commit_change(workspace, "run-sha-test", self.target_rel, "Demo: change footer")
        sha = de.get_commit_sha(workspace)
        real_sha = _git(["rev-parse", "--short", "HEAD"], workspace).strip()
        self.assertEqual(sha, real_sha)
        self.assertTrue(sha)

    def test_push_to_remote_really_delivers_the_commit(self):
        """Real proof that a successful push means the remote actually
        received the commit — not just that the git command exited 0."""
        workspace = self._clone()
        (workspace / self.target_rel).write_text("<footer>PUSHED VALUE</footer>\n", encoding="utf-8")
        branch, ok, _ = de.commit_change(workspace, "run-push-ok", self.target_rel, "Demo: pushed change")
        self.assertTrue(ok)
        pushed_sha = de.get_commit_sha(workspace)

        push_ok, push_out = de.push_to_remote(workspace, str(self.origin), branch)
        self.assertTrue(push_ok, push_out)

        # Independent verification: inspect the ORIGIN repository directly,
        # not the pushing workspace, for the real ref and commit content.
        origin_branches = _git(["branch", "--list", branch], self.origin)
        self.assertIn(branch, origin_branches)
        origin_sha = _git(["rev-parse", "--short", branch], self.origin).strip()
        self.assertEqual(origin_sha, pushed_sha)
        origin_content = _git(["show", f"{branch}:{self.target_rel}"], self.origin)
        self.assertIn("PUSHED VALUE", origin_content)

    def test_push_to_nonexistent_remote_fails_honestly(self):
        workspace = self._clone()
        (workspace / self.target_rel).write_text("<footer>X</footer>\n", encoding="utf-8")
        branch, ok, _ = de.commit_change(workspace, "run-push-fail", self.target_rel, "Demo: change")
        self.assertTrue(ok)
        push_ok, push_out = de.push_to_remote(workspace, str(Path(self.tmp_root) / "does-not-exist"), branch)
        self.assertFalse(push_ok)
        self.assertTrue(push_out)  # real, non-empty git error text

    def test_push_change_without_token_is_honest_and_does_not_touch_network(self):
        """WORKBENCH TRUTHFULNESS FIX (2026-09-13): this exact case — no
        DEMO_GIT_PUSH_TOKEN configured — is an honest, expected
        precondition, not a failure. It must return the distinct
        NOT_CONFIGURED status, never PUSH_STATUS_FAILED, so the caller
        can render it calmly instead of as an alarming error (the real
        Owner-observed defect this fixes, see docs/LESSONS.md)."""
        with mock.patch.object(de, "DEMO_GIT_PUSH_TOKEN", None):
            workspace = self._clone()
            (workspace / self.target_rel).write_text("<footer>X</footer>\n", encoding="utf-8")
            branch, _, _ = de.commit_change(workspace, "run-no-token", self.target_rel, "Demo")
            status, message = de.push_change(workspace, branch)
        self.assertEqual(status, de.PUSH_STATUS_NOT_CONFIGURED)
        self.assertNotEqual(status, de.PUSH_STATUS_FAILED)
        self.assertIn("not configured", message)

    def test_push_change_redacts_the_token_from_any_returned_output(self):
        fake_token = "ghp_FAKE_TEST_TOKEN_1234567890"
        with mock.patch.object(de, "DEMO_GIT_PUSH_TOKEN", fake_token):
            workspace = self._clone()
            (workspace / self.target_rel).write_text("<footer>X</footer>\n", encoding="utf-8")
            branch, _, _ = de.commit_change(workspace, "run-redact", self.target_rel, "Demo")
            # This will genuinely fail (github.com is not reachable to a
            # fake token / may not even resolve in this environment as
            # this exact host) — the point is that IF the token leaked
            # into output, this test would catch it either way.
            status, message = de.push_change(workspace, branch)
        self.assertEqual(status, de.PUSH_STATUS_FAILED)
        self.assertNotIn(fake_token, message)


class DeployTriggerTestCase(unittest.TestCase):
    """RELIABILITY/CORRECTION PHASE (2026-09-13): real bug found live —
    trigger_deploy() previously called `railway up` directly against a
    fresh isolated workspace directory Railway had never linked, and it
    failed fast every real attempt (confirmed via real production
    acceptance runs and real `railway deployment list`/`logs` evidence).
    This exact function had ZERO test coverage before that incident —
    the gap that let it ship. These tests exist so this class of defect
    (an unlinked-directory deploy) can never silently regress again."""

    def test_trigger_deploy_links_before_calling_up(self):
        calls = []

        def fake_run(argv, cwd, timeout_s):
            calls.append(argv)
            return True, ""

        with mock.patch.object(de, "run_controlled", side_effect=fake_run):
            ok, out = de.trigger_deploy(Path("/fake/app"), "proj-id", "svc-name", "production")
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][:2], ["railway", "link"])
        self.assertIn("proj-id", calls[0])
        self.assertIn("svc-name", calls[0])
        self.assertEqual(calls[1][:2], ["railway", "up"])

    def test_trigger_deploy_still_attempts_up_when_link_fails(self):
        """Real incident (2026-09-13, this exact task, two real
        production acceptance runs): a first fix made link failure
        BLOCK the deploy, and a second real run proved that wrong — the
        deployed container's project-scoped RAILWAY_TOKEN can legitimately
        reject `railway link` (already locked to one project), and that
        must never prevent `railway up`'s own explicit
        --project/--service/--environment flags from being tried for
        real. Link is best-effort only, never gating."""
        calls = []

        def fake_run(argv, cwd, timeout_s):
            calls.append(argv)
            if argv[:2] == ["railway", "link"]:
                return False, "could not resolve project"
            return True, "deployed"

        with mock.patch.object(de, "run_controlled", side_effect=fake_run):
            ok, out = de.trigger_deploy(Path("/fake/app"), "proj-id", "svc-name", "production")
        self.assertTrue(ok)
        self.assertIn("non-fatal", out)
        up_calls = [c for c in calls if c[:2] == ["railway", "up"]]
        self.assertEqual(len(up_calls), 1)

    def test_link_workspace_to_railway_passes_exact_project_service_environment(self):
        with mock.patch.object(de, "run_controlled", return_value=(True, "linked")) as mock_run:
            ok, out = de.link_workspace_to_railway(Path("/fake/app"), "proj-id", "svc-name", "production")
        self.assertTrue(ok)
        argv = mock_run.call_args[0][0]
        self.assertEqual(argv, ["railway", "link", "--project", "proj-id", "--service", "svc-name", "--environment", "production"])


class DeploymentIdentityTestCase(unittest.TestCase):
    """Railway itself is mocked here (no real account access from a unit
    test) — the real subprocess/JSON parsing contract is exercised
    against realistic fixture JSON shapes captured from real read-only
    `railway deployment list --json` calls made during this task.

    RELIABILITY/CORRECTION PHASE (2026-09-13): wait_for_new_deployment()
    was rewritten after THREE real production acceptance runs (submitted
    through the live public Workbench) exposed a real bug — the previous
    version identified "the new deployment" as any list entry whose id
    differed from a captured `previous_deployment_id`. In real production,
    a deployment that had genuinely FAILED forty-six minutes earlier (for
    an unrelated reason, still present in Railway's own recent-N list)
    was mistaken for "the new one" this exact way, reporting a false
    failure for a change that had, in real fact, just deployed
    successfully. The fix filters candidates by real `createdAt` against
    a reference timestamp captured immediately before the deploy was
    triggered — test_wait_for_new_deployment_ignores_an_old_unrelated_entry_even_if_its_id_differs
    is the direct regression test for the exact real incident."""

    def test_wait_for_new_deployment_detects_a_real_new_success(self):
        fixture = json.dumps([
            {"id": "new-id", "status": "SUCCESS", "createdAt": "2026-09-13T10:00:00.000Z"},
            {"id": "old-id", "status": "REMOVED", "createdAt": "2026-09-13T09:00:00.000Z"},
        ])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment(
                "proj", "svc", "production", "2026-09-13T09:59:00.000000+00:00", Path("."), max_wait_s=30, poll_interval_s=10)
        self.assertEqual(new_id, "new-id")
        self.assertEqual(status, "SUCCESS")

    def test_wait_for_new_deployment_detects_a_real_new_failure(self):
        fixture = json.dumps([
            {"id": "new-id", "status": "FAILED", "createdAt": "2026-09-13T10:00:00.000Z"},
            {"id": "old-id", "status": "SUCCESS", "createdAt": "2026-09-13T09:00:00.000Z"},
        ])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment(
                "proj", "svc", "production", "2026-09-13T09:59:00.000000+00:00", Path("."), max_wait_s=30, poll_interval_s=10)
        self.assertEqual(new_id, "new-id")
        self.assertEqual(status, "FAILED")

    def test_wait_for_new_deployment_ignores_an_old_unrelated_entry_even_if_its_id_differs(self):
        """THE EXACT REAL INCIDENT (2026-09-13): an old, unrelated
        deployment that genuinely failed 46 minutes earlier must never be
        mistaken for the deployment this run just triggered, merely
        because its id happens to differ from whatever reference id an
        older design might have used. Only a deployment CREATED AFTER the
        real trigger timestamp may ever be considered a candidate."""
        fixture = json.dumps([
            {"id": "old-unrelated-failed-id", "status": "FAILED", "createdAt": "2026-09-13T09:08:00.043Z"},
        ])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment(
                "proj", "svc", "production", "2026-09-13T09:54:32.213824+00:00", Path("."), max_wait_s=20, poll_interval_s=10)
        self.assertIsNone(new_id)
        self.assertEqual(status, "TIMEOUT")

    def test_wait_for_new_deployment_times_out_honestly_when_nothing_new_appears(self):
        with mock.patch.object(de, "run_controlled", return_value=(False, "cli error")), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment(
                "proj", "svc", "production", "2026-09-13T09:59:00.000000+00:00", Path("."), max_wait_s=20, poll_interval_s=10)
        self.assertIsNone(new_id)
        self.assertEqual(status, "TIMEOUT")
        self.assertEqual(waited, 20)

    def test_utc_now_iso_produces_a_real_sortable_utc_timestamp(self):
        before = de.utc_now_iso()
        import time as _time
        _time.sleep(0.01)
        after = de.utc_now_iso()
        self.assertLess(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
