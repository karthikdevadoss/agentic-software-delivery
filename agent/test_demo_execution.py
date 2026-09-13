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
        with mock.patch.object(de, "DEMO_GIT_PUSH_TOKEN", None):
            workspace = self._clone()
            (workspace / self.target_rel).write_text("<footer>X</footer>\n", encoding="utf-8")
            branch, _, _ = de.commit_change(workspace, "run-no-token", self.target_rel, "Demo")
            ok, message = de.push_change(workspace, branch)
        self.assertFalse(ok)
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
            ok, message = de.push_change(workspace, branch)
        self.assertNotIn(fake_token, message)


class DeploymentIdentityTestCase(unittest.TestCase):
    """Railway itself is mocked here (no real account access from a unit
    test) — the real subprocess/JSON parsing contract is exercised
    against realistic fixture JSON shapes captured from a real read-only
    `railway deployment list --json` call made during this task."""

    def test_get_latest_deployment_id_parses_real_shape(self):
        fixture = json.dumps([{"id": "74f91bde-d702-4679-a14b-ad8ed635e5b8", "status": "SUCCESS", "createdAt": "2026-09-12T09:41:23.557Z"}])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)):
            result = de.get_latest_deployment_id("proj", "svc", "production", Path("."))
        self.assertEqual(result, "74f91bde-d702-4679-a14b-ad8ed635e5b8")

    def test_get_latest_deployment_id_returns_none_on_cli_failure(self):
        with mock.patch.object(de, "run_controlled", return_value=(False, "error")):
            result = de.get_latest_deployment_id("proj", "svc", "production", Path("."))
        self.assertIsNone(result)

    def test_get_latest_deployment_id_returns_none_on_malformed_json(self):
        with mock.patch.object(de, "run_controlled", return_value=(True, "not json")):
            result = de.get_latest_deployment_id("proj", "svc", "production", Path("."))
        self.assertIsNone(result)

    def test_wait_for_new_deployment_detects_a_real_new_success(self):
        fixture = json.dumps([{"id": "new-id", "status": "SUCCESS"}, {"id": "old-id", "status": "REMOVED"}])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment("proj", "svc", "production", "old-id", Path("."), max_wait_s=30, poll_interval_s=10)
        self.assertEqual(new_id, "new-id")
        self.assertEqual(status, "SUCCESS")

    def test_wait_for_new_deployment_detects_a_real_new_failure(self):
        fixture = json.dumps([{"id": "new-id", "status": "FAILED"}, {"id": "old-id", "status": "SUCCESS"}])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment("proj", "svc", "production", "old-id", Path("."), max_wait_s=30, poll_interval_s=10)
        self.assertEqual(new_id, "new-id")
        self.assertEqual(status, "FAILED")

    def test_wait_for_new_deployment_ignores_the_previous_id_even_if_it_shows_success_again(self):
        """The OLD deployment ID showing SUCCESS is not proof of a NEW
        deployment — must keep waiting, never conflate old-still-healthy
        with new-now-serving."""
        fixture = json.dumps([{"id": "old-id", "status": "SUCCESS"}])
        with mock.patch.object(de, "run_controlled", return_value=(True, fixture)), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment("proj", "svc", "production", "old-id", Path("."), max_wait_s=20, poll_interval_s=10)
        self.assertIsNone(new_id)
        self.assertEqual(status, "TIMEOUT")

    def test_wait_for_new_deployment_times_out_honestly_when_nothing_new_appears(self):
        with mock.patch.object(de, "run_controlled", return_value=(False, "cli error")), \
             mock.patch.object(de.time, "sleep"):
            new_id, status, waited = de.wait_for_new_deployment("proj", "svc", "production", "old-id", Path("."), max_wait_s=20, poll_interval_s=10)
        self.assertIsNone(new_id)
        self.assertEqual(status, "TIMEOUT")
        self.assertEqual(waited, 20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
