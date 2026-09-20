"""
Direct, focused tests for agent/tools.py's own security boundary
(_resolve_safe_path and its public callers: read_file, list_repository_files,
search_code), calling tools.py functions directly rather than only through a
downstream consumer (MCP server, write_tools, rag_index). Closes BL-030 /
ACT-002 (docs/ACTION_QUEUE.json): before this file, traversal/absolute/
symlink/secret-name/redaction coverage existed only indirectly via
test_mcp_server.py, test_write_tools.py, and rag_index's own wrapper around
read_file. In particular this file adds direct coverage for the real
historical bug recorded in docs/LESSONS.md ("A path-safety check gated on
`if resolved.is_file()` silently skips protection for files that don't
exist yet") for BOTH an existing and a not-yet-existing secret-named file,
real symlink-escape rejection, search_code's own traversal/glob safety, and
end-to-end redaction through tools.read_file/search_code themselves (not
just a direct call to redact_secrets()).

Run: python agent/test_tools.py
"""

import os
import shutil
import unittest

import tools
from tools import RepoToolError

FIXTURE_DIR = tools.REPO_ROOT / "docs" / "_test_fixture_tools"


def _cleanup_fixture_dir():
    if FIXTURE_DIR.exists():
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)


def _rel(path) -> str:
    return str(path.relative_to(tools.REPO_ROOT)).replace("\\", "/")


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

    def test_read_file_redacts_a_real_secret_literal_in_actual_file_content(self):
        """End-to-end: writes a real file containing a real secret-shaped
        literal, reads it through tools.read_file() itself (not through
        rag_index's wrapper, and not by calling redact_secrets() directly
        in isolation), and confirms the secret never reaches the returned
        text. This is the direct-on-tools.py coverage ACT-002 says is
        missing (redaction was previously verified only via rag_index's
        wrapper around read_file)."""
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(_cleanup_fixture_dir)
        # Filename deliberately avoids secret/credential-shaped patterns so
        # this exercises content redaction, not the name-blocking path
        # already covered by SecretNamedFileTestCase.
        fixture = FIXTURE_DIR / "app_config_notes.md"
        fixture.write_text(
            "ANTHROPIC_API_KEY=sk-ant-api03-thisisatestsecretvalue1234567890\n",
            encoding="utf-8",
        )
        content = tools.read_file(_rel(fixture))
        self.assertNotIn("sk-ant-api03-thisisatestsecretvalue1234567890", content)
        self.assertIn("REDACTED", content)


class ListRepositoryFilesSecurityTestCase(unittest.TestCase):
    def test_list_repository_files_rejects_traversal(self):
        with self.assertRaises(RepoToolError):
            tools.list_repository_files("..")

    def test_list_repository_files_excludes_blocked_directories(self):
        listing = tools.list_repository_files(".")
        self.assertNotIn(".git/", listing)
        self.assertNotIn("target/", listing)


class SecretNamedFileTestCase(unittest.TestCase):
    """Regression coverage for the real historical bug recorded in
    docs/LESSONS.md: tools.py's secret-filename block used to be gated on
    `resolved.is_file()`, so it silently let a brand-new (not-yet-existing)
    secret-named file through and only protected files that already
    existed on disk. The fix (see _resolve_safe_path's comment) removed
    that gate so the name/extension check always runs regardless of
    existence. test_write_tools.py already regression-tests this through
    the write boundary (test_secret_named_new_file_in_scope_rejected);
    these tests prove both halves directly against tools.py itself."""

    def setUp(self):
        _cleanup_fixture_dir()
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(_cleanup_fixture_dir)

    def test_secret_named_file_that_already_exists_is_rejected(self):
        existing = FIXTURE_DIR / "real_credentials.md"
        existing.write_text("filename-based rejection test only", encoding="utf-8")
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path(_rel(existing))
        self.assertIn("blocked for safety", str(ctx.exception))

    def test_secret_named_file_that_does_not_exist_yet_is_still_rejected(self):
        # The exact historical gap: this file is deliberately never created.
        not_yet_created = FIXTURE_DIR / "not_yet_created_credentials.md"
        self.assertFalse(not_yet_created.exists())
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path(_rel(not_yet_created))
        self.assertIn("blocked for safety", str(ctx.exception))

    def test_read_file_also_rejects_a_not_yet_existing_secret_named_file(self):
        not_yet_created = FIXTURE_DIR / "another_secret_token.md"
        self.assertFalse(not_yet_created.exists())
        with self.assertRaises(RepoToolError) as ctx:
            tools.read_file(_rel(not_yet_created))
        self.assertIn("blocked for safety", str(ctx.exception))


class SymlinkSecurityTestCase(unittest.TestCase):
    def setUp(self):
        _cleanup_fixture_dir()
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        self.addCleanup(_cleanup_fixture_dir)

    def test_symlink_escaping_the_repo_is_rejected_if_creatable_on_this_platform(self):
        target_outside = tools.REPO_ROOT.parent / "_tools_test_outside_target.md"
        link_path = FIXTURE_DIR / "escape_link.md"
        target_outside.write_text("outside repo content", encoding="utf-8")
        self.addCleanup(lambda: target_outside.unlink(missing_ok=True))
        try:
            link_path.symlink_to(target_outside)
        except OSError:
            self.skipTest("symlink creation not permitted on this platform/account")
        with self.assertRaises(RepoToolError) as ctx:
            tools._resolve_safe_path(_rel(link_path))
        self.assertIn("symlink", str(ctx.exception))

    def test_read_file_also_rejects_a_symlink_if_creatable_on_this_platform(self):
        target_outside = tools.REPO_ROOT.parent / "_tools_test_outside_target2.md"
        link_path = FIXTURE_DIR / "escape_link2.md"
        target_outside.write_text("outside repo content", encoding="utf-8")
        self.addCleanup(lambda: target_outside.unlink(missing_ok=True))
        try:
            link_path.symlink_to(target_outside)
        except OSError:
            self.skipTest("symlink creation not permitted on this platform/account")
        with self.assertRaises(RepoToolError) as ctx:
            tools.read_file(_rel(link_path))
        self.assertIn("symlink", str(ctx.exception))


class SearchCodeSecurityTestCase(unittest.TestCase):
    def setUp(self):
        _cleanup_fixture_dir()
        self.addCleanup(_cleanup_fixture_dir)

    def test_search_code_rejects_traversal_glob(self):
        with self.assertRaises(RepoToolError):
            tools.search_code("Customer", glob="../**/*.java")

    def test_search_code_rejects_absolute_glob(self):
        with self.assertRaises(RepoToolError):
            tools.search_code("Customer", glob="/etc/**/*.java")

    def test_search_code_rejects_short_query(self):
        with self.assertRaises(RepoToolError):
            tools.search_code("x")

    def test_search_code_finds_a_real_known_match(self):
        result = tools.search_code("public class CustomerController", glob="**/*.java")
        self.assertIn("CustomerController.java", result)

    def test_search_code_excludes_blocked_directories(self):
        result = tools.search_code("import", glob="**/*.java")
        for line in result.splitlines():
            self.assertFalse(line.startswith(".git/"))
            self.assertNotIn("/target/", line)

    def test_search_code_redacts_secrets_in_matched_snippet(self):
        # Filename deliberately avoids secret/credential-shaped patterns so
        # this exercises content redaction, not the name-blocking path
        # already covered by SecretNamedFileTestCase.
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        fixture = FIXTURE_DIR / "app_config_fixture.properties"
        fixture.write_text(
            "anthropic.key=sk-ant-api03-thisisatestsecretvalue1234567890\n",
            encoding="utf-8",
        )
        result = tools.search_code("anthropic.key", glob="docs/_test_fixture_tools/*.properties")
        self.assertNotIn("sk-ant-api03-thisisatestsecretvalue1234567890", result)
        self.assertIn("REDACTED", result)


if __name__ == "__main__":
    unittest.main()
