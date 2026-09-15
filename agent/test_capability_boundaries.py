"""
Architecture tests (Base Architecture V3 Section 6): mechanically enforce
real capability-boundary rules from docs/CAPABILITY_SECURITY_MODEL.md,
proven by deliberate violation -- not just described in prose.

Run: python agent/test_capability_boundaries.py
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QA_EVALUATOR_PATH = REPO_ROOT / ".claude" / "agents" / "qa-evaluator.md"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _csv_field(fields: dict, key: str) -> set:
    raw = fields.get(key, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


class QaEvaluatorCapabilityBoundaryTestCase(unittest.TestCase):
    """docs/CAPABILITY_SECURITY_MODEL.md's real, harness-enforced claim:
    qa-evaluator structurally cannot mutate source, because its frontmatter
    excludes Write/Edit/NotebookEdit. This makes that claim an executable
    regression instead of prose that could silently go stale."""

    def test_qa_evaluator_frontmatter_still_excludes_source_mutation_tools(self):
        text = QA_EVALUATOR_PATH.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        disallowed = _csv_field(fields, "disallowedTools")
        for tool in ("Write", "Edit", "NotebookEdit"):
            self.assertIn(
                tool, disallowed,
                f"qa-evaluator.md's disallowedTools no longer excludes {tool!r} -- "
                f"this is the real, harness-enforced capability boundary that lets "
                f"the QA role certify without being able to modify what it's certifying "
                f"(see docs/CAPABILITY_SECURITY_MODEL.md); this must never silently regress.",
            )

    def test_qa_evaluator_allowed_tools_never_include_a_mutation_tool_either(self):
        # Defense-in-depth against the allow-list itself being edited to
        # readd a mutation tool without updating disallowedTools to match.
        text = QA_EVALUATOR_PATH.read_text(encoding="utf-8")
        fields = _parse_frontmatter(text)
        allowed = _csv_field(fields, "tools")
        for tool in ("Write", "Edit", "NotebookEdit"):
            self.assertNotIn(tool, allowed)

    def test_the_parser_itself_correctly_extracts_a_known_good_fixture(self):
        # Guards the test logic itself against a false sense of security --
        # if this fails, the two tests above could be silently vacuous.
        fixture = "---\nname: x\ntools: Read, Bash\ndisallowedTools: Write, Edit\n---\nbody"
        fields = _parse_frontmatter(fixture)
        self.assertEqual(_csv_field(fields, "tools"), {"Read", "Bash"})
        self.assertEqual(_csv_field(fields, "disallowedTools"), {"Write", "Edit"})


if __name__ == "__main__":
    unittest.main()
