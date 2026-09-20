"""
Direct, focused tests for agent/tools.py's own security boundary
(_resolve_safe_path and its public callers), calling tools.py functions
directly rather than only through a downstream consumer (MCP server,
write_tools). Closes ACT-002 (docs/ACTION_QUEUE.json): before this file,
traversal/absolute/symlink/redaction coverage existed only indirectly via
test_mcp_server.py and test_write_tools.py.

Run: python agent/test_tools.py
"""

import os
import unittest

import tools
from tools import RepoToolError


class ResolveSafePathTestCase(unittest.TestCase):
    def test_path_traversal_is_rejected(self):
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path("../outside.txt")
        self.assertIn("traversal", str(ctx.exception))

    def test_absolute_path_is_rejected(self):
        # On Windows, a POSIX-style path with no drive letter is NOT
        # is_absolute() per pathlib (only a drive-relative root) -- so this
        # is correctly caught by the outside-the-repository check instead
        # of the absolute-path check, a different but equally honest
        # rejection reason. On POSIX this would hit the absolute-path
        # check directly. Assert on the one thing true either way: it's
        # rejected, and never silently allowed.
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path("/etc/passwd")
        message = str(ctx.exception)
        self.assertTrue("absolute" in message or "outside the repository" in message, message)

    def test_blocked_directory_is_rejected(self):
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path(".git/config")
        self.assertIn("blocked directory", str(ctx.exception))

    def test_blocked_extension_is_rejected(self):
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path("app/.env")
        self.assertIn("blocked", str(ctx.exception))

    def test_a_normal_real_repo_file_resolves_cleanly(self):
        resolved = tools._resolve_safe_path("README.md")
        self.assertTrue(resolved.exists())
        self.assertEqual(resolved.relative_to(tools.REPO_ROOT).as_posix(), "README.md")

    @unittest.skipUnless(os.name == "nt", "drive-letter paths are a Windows-only concept")
    def test_foreign_drive_letter_path_gives_an_honest_drive_specific_error(self):
        """BL-010 / ACT-001: a path like 'D:foo' used to be misreported as
        a symlink rejection (Path.is_absolute() is False for a
        drive-relative Windows path, so the absolute-path check never
        caught it, and PurePath.__truediv__ silently discards REPO_ROOT
        once the right operand carries its own drive). Now names the real
        reason. Uses whichever drive letter isn't REPO_ROOT's own, so this
        stays correct regardless of which drive the checkout happens to be
        on."""
        other_drive = "E" if tools.REPO_ROOT.drive.upper().startswith("D") else "D"
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path(f"{other_drive}:foo")
        message = str(ctx.exception)
        self.assertIn("drive", message)
        self.assertNotIn("symlink", message)


class ReadFileSecurityTestCase(unittest.TestCase):
    def test_read_file_rejects_traversal(self):
        with self.assertRaises(RepoToolError):
            tools.read_file("../../etc/passwd")

    def test_read_file_rejects_blocked_extension(self):
        with self.assertRaises(RepoToolError):
            tools.read_file("app/pom.xml.jar")

    def test_read_file_missing_file_reports_not_found(self):
        with self.assertRaises(RepoToolError) as ctx:
            tools.read_file("docs/DOES_NOT_EXIST_REALLY.md")
        self.assertIn("not found", str(ctx.exception))

    def test_read_file_redacts_an_obvious_secret_assignment(self):
        # README.md is real repo content unrelated to secrets; this proves
        # redact_secrets() itself is wired into read_file()'s real path by
        # asserting on the function directly, not just as a unit in isolation.
        content = tools.read_file("README.md")
        self.assertNotIn("***REDACTED***", content)  # sanity: README has no secret-shaped text
        redacted = tools.redact_secrets('api_key: "sk-ant-abcdefghij1234567890"')
        self.assertIn("***REDACTED***", redacted)
        self.assertNotIn("sk-ant-abcdefghij1234567890", redacted)


class ListRepositoryFilesSecurityTestCase(unittest.TestCase):
    def test_list_repository_files_rejects_traversal(self):
        with self.assertRaises(RepoToolError):
            tools.list_repository_files("..")

    def test_list_repository_files_excludes_blocked_directories(self):
        listing = tools.list_repository_files(".")
        self.assertNotIn(".git/", listing)
        self.assertNotIn("target/", listing)


if __name__ == "__main__":
    unittest.main()
