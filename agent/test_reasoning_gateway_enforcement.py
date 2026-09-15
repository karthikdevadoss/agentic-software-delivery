"""
Deterministic enforcement (Base Architecture V3 Phase 3/Section 2): fails
if ANY Python file under agent/ imports the Anthropic SDK directly, other
than the small, explicitly-approved allowlist below. This is the
mechanical guard the directive asks for -- "add deterministic enforcement
that fails if new direct provider access is introduced outside approved
gateway modules" -- so this rule survives future sessions/code review
memory, not just a one-time audit.

Full inventory as of this check (docs/INTELLIGENCE_PLACEMENT_V3.md /
docs/DETERMINISTIC_VS_LLM_DECISIONS.md): exactly 3 files have a real,
justified reason to import the SDK directly. Everything else -- including
any FUTURE file -- must route through agent/reasoning_gateway.py.

Run: python agent/test_reasoning_gateway_enforcement.py
"""

import re
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent

# Each entry names the file and the real, evidence-based reason it's
# allowed to import the SDK directly instead of going through
# reasoning_gateway.call() -- see docs/ARCHITECTURE_V3_DECISIONS.md D5.
APPROVED_DIRECT_IMPORT_FILES = {
    "reasoning_gateway.py": "IS the gateway -- this is where the one sanctioned SDK import lives",
    "agent_loop.py": "V3's multi-turn TOOL-CALLING loop -- a genuinely different shape from a "
                      "single-shot advisory call; flattening it into the gateway would be a much "
                      "larger, riskier redesign than justified so far (documented scope decision)",
    "backend_planning.py": "analyze_with_llm has a materially different response contract "
                            "(structured JSON fields, not a stripped text blob) from the gateway's "
                            "single-shot text contract (documented scope decision)",
}

_IMPORT_RE = re.compile(r"^\s*(?:import anthropic\b|from anthropic import)", re.MULTILINE)


def _files_with_direct_anthropic_import():
    """Returns {relative_filename: True} for every agent/*.py file that
    imports the anthropic SDK directly -- a real static-source scan, not
    a maintained hand list that could drift from reality."""
    found = {}
    for path in AGENT_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if _IMPORT_RE.search(text):
            found[path.name] = True
    return found


class ReasoningGatewayCentralizationTestCase(unittest.TestCase):
    def test_no_unapproved_file_imports_the_anthropic_sdk_directly(self):
        actual = set(_files_with_direct_anthropic_import())
        approved = set(APPROVED_DIRECT_IMPORT_FILES)
        unapproved = actual - approved
        self.assertEqual(
            unapproved, set(),
            f"New direct Anthropic SDK import(s) found outside the approved allowlist: "
            f"{sorted(unapproved)}. Route through agent/reasoning_gateway.call() instead, "
            f"or add the file here with a real, documented reason (see "
            f"docs/ARCHITECTURE_V3_DECISIONS.md D5) if a single-shot gateway call genuinely "
            f"cannot express what this call site needs.",
        )

    def test_every_approved_file_still_actually_exists_and_still_imports_directly(self):
        # Guards the allowlist itself against drift: an entry that no
        # longer applies (file deleted, or refactored to use the gateway
        # like main.py was) should be removed, not left stale.
        actual = _files_with_direct_anthropic_import()
        for filename in APPROVED_DIRECT_IMPORT_FILES:
            self.assertTrue((AGENT_DIR / filename).exists(), f"{filename} no longer exists -- remove it from the allowlist")
            self.assertIn(
                filename, actual,
                f"{filename} is on the allowlist but no longer imports anthropic directly -- "
                f"remove it from APPROVED_DIRECT_IMPORT_FILES (it's been migrated to the gateway)",
            )

    def test_main_py_was_migrated_off_the_allowlist(self):
        # The concrete proof this check works both directions: main.py
        # used to import anthropic directly and is now gateway-routed.
        self.assertNotIn("main.py", APPROVED_DIRECT_IMPORT_FILES)
        actual = _files_with_direct_anthropic_import()
        self.assertNotIn("main.py", actual)


if __name__ == "__main__":
    unittest.main()
