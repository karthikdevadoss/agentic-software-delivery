"""Automation Sprint 4 / S4: home-page claims match what the code does.

- CI: the eval step in .github/workflows/ci.yml runs only when the steps
  before it pass (no `if: always()`). The home page used to say "Measured on
  every build ... The build fails if the scores drop", while master CI was red
  and the eval step skipped. The page must say the step can be skipped for as
  long as the workflow says so.
- Deploy: the platform is deployed by hand with the Railway CLI; a Workbench
  run deploys the Customer App change it made by triggering the same CLI step
  itself (demo_execution.trigger_deploy). Home and Workbench must not
  contradict each other on that.
Hermetic: reads files only.
"""
import pathlib
import re
import unittest

import test_public_surface_gate as surface

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOME = surface._visible_text((ROOT / "agent/web/home.html").read_text(encoding="utf-8"))
WORKBENCH = surface._visible_text((ROOT / "agent/web/workbench.html").read_text(encoding="utf-8"))
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")


def _eval_step():
    m = re.search(r"- name: RAG/MCP retrieval \+ routing evals.*?(?=\n      - |\n  \S|\Z)", CI, re.S)
    assert m, "eval step not found in ci.yml"
    return m.group(0)


class HomeCiClaimTestCase(unittest.TestCase):
    def test_no_unconditional_every_build_claim(self):
        self.assertNotRegex(HOME.lower(), r"measured on every build")
        self.assertNotRegex(HOME.lower(), r"build fails if the scores drop")

    def test_home_says_the_eval_can_be_skipped_while_ci_can_skip_it(self):
        step = _eval_step()
        self.assertIn("eval_runner.py all", step)
        runs_always = re.search(r"if:\s*(always\(\)|\$\{\{\s*always\(\)\s*\}\})", step)
        if not runs_always:
            self.assertIn("If an earlier step fails, the evaluation does not run", HOME)
        self.assertIn("fails the build if a score drops below its recorded threshold", HOME)


class DeployClaimsAgreeTestCase(unittest.TestCase):
    def test_home_scope_names_both_deploy_paths(self):
        self.assertIn("the platform itself is deployed by a manually triggered Railway CLI command", HOME)
        self.assertIn("a Workbench run deploys the small Customer App change", HOME)
        # The old line said only "manually triggered deployment scripts", which
        # read as a contradiction of the Workbench's automatic deploy.
        self.assertNotIn("and manually triggered deployment scripts.", HOME)

    def test_workbench_says_what_it_deploys(self):
        self.assertIn("deployed to the Customer App automatically", WORKBENCH)

    def test_the_workbench_claim_is_backed_by_code(self):
        src = (ROOT / "agent/web_server.py").read_text(encoding="utf-8")
        self.assertIn("demo_execution.trigger_deploy(", src)
        self.assertIn("railway up", (ROOT / "agent/demo_execution.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
