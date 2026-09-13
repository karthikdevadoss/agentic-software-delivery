"""
Smoke tests for agent/dev_check.py's command dispatch table — a thin
runner over real subprocess/network calls, so what's actually worth
unit-testing is that the dispatch table itself is well-formed and that
`main()` fails closed on an unknown command, not the underlying
commands' real external behavior (those are exercised for real by
running the tool itself, per its own docstring)."""

import unittest
from unittest import mock

import dev_check


class DispatchTableTestCase(unittest.TestCase):
    def test_every_documented_command_is_registered(self):
        for name in ("python-regression", "node-regression", "customer-app-tests",
                     "backend-catalogue-tests", "deployment-status", "production-verify", "all"):
            self.assertIn(name, dev_check.COMMANDS)

    def test_unknown_command_exits_non_zero_not_silently_succeeding(self):
        with mock.patch.object(dev_check.sys, "argv", ["dev_check.py", "not-a-real-command"]), \
             self.assertRaises(SystemExit) as ctx:
            dev_check.main()
        self.assertNotEqual(ctx.exception.code, 0)

    def test_no_arguments_exits_non_zero(self):
        with mock.patch.object(dev_check.sys, "argv", ["dev_check.py"]), \
             self.assertRaises(SystemExit) as ctx:
            dev_check.main()
        self.assertNotEqual(ctx.exception.code, 0)

    def test_main_propagates_the_real_subcommand_exit_code(self):
        with mock.patch.dict(dev_check.COMMANDS, {"fake": lambda args: 7}, clear=False), \
             mock.patch.object(dev_check.sys, "argv", ["dev_check.py", "fake"]), \
             self.assertRaises(SystemExit) as ctx:
            dev_check.main()
        self.assertEqual(ctx.exception.code, 7)

    def test_production_verify_never_reports_ok_for_a_mismatched_status(self):
        """A real regression class this tool must never have: silently
        treating an unexpected HTTP status as success."""
        with mock.patch.object(dev_check.urllib.request, "urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.status = 500
            mock_urlopen.return_value.__enter__.return_value = mock_resp
            rc = dev_check.production_verify()
        self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
