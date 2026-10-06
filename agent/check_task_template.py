"""
Deterministic, zero-LLM gate for a Claude Code task contract (BL-125/127/128).

Checks that a task-contract markdown file (built from
docs/templates/CLAUDE_CODE_TASK_TEMPLATE.md) carries every REQUIRED
top-level section, and that every task entry under "## Task queue" carries
its own "Page purpose" and "Quality acceptance" lines (BL-127). This is
structural enforcement only -- it cannot and does not judge truthfulness
of the content (that is the five evidence rules' job, CLAUDE.md), only
that the required fields exist before a task is considered launch-ready.

Run:  python agent/check_task_template.py <path-to-contract.md>
      python agent/check_task_template.py <path> --list   (prints required sections, checks nothing)
"""

import re
import sys
from pathlib import Path

REQUIRED_TOP_LEVEL_SECTIONS = [
    "Role / session identity",
    "Bounded production calls",
    "Hard stop / exit rules",
    "Mission",
    "Verified facts only, never asserted",
    "Task queue",
    "Out of scope",
    "Committed report",
]

TASK_ENTRY_REQUIRED_FIELDS = [
    "Page purpose",
    "Quality acceptance",
    "Done when",
    "Skip if",
]

# A task entry heading looks like "### T1 -- Title (~25 min)" in the
# template, or any "### " line in a real filled-in contract.
TASK_HEADING_RE = re.compile(r"^###\s+\S", re.MULTILINE)


def _section_present(text: str, heading: str) -> bool:
    # Match "## <heading>" optionally followed by " **REQUIRED**" or other
    # trailing text, case-insensitive, anchored to a markdown heading line.
    pattern = re.compile(
        r"^##\s+" + re.escape(heading) + r"\b", re.MULTILINE | re.IGNORECASE
    )
    return bool(pattern.search(text))


def _split_task_entries(text: str):
    """Return the raw text of each '### ...' task entry block."""
    starts = [m.start() for m in TASK_HEADING_RE.finditer(text)]
    if not starts:
        return []
    starts.append(len(text))
    return [text[starts[i]:starts[i + 1]] for i in range(len(starts) - 1)]


def check_contract(text: str) -> list:
    """Return a list of human-readable problems; empty means the contract
    has every required structural field."""
    problems = []

    for heading in REQUIRED_TOP_LEVEL_SECTIONS:
        if not _section_present(text, heading):
            problems.append(f"missing required section: ## {heading}")

    if _section_present(text, "Task queue"):
        # Only check inside the Task queue section onward, so an unrelated
        # "###" heading elsewhere in the document isn't misread as a task.
        tq_start = re.search(
            r"^##\s+Task queue\b", text, re.MULTILINE | re.IGNORECASE
        ).start()
        next_h2 = re.search(r"^##\s+", text[tq_start + 1:], re.MULTILINE)
        tq_end = tq_start + 1 + next_h2.start() if next_h2 else len(text)
        task_entries = _split_task_entries(text[tq_start:tq_end])

        if not task_entries:
            problems.append(
                "Task queue section has no '### <task id>' entries"
            )
        for entry in task_entries:
            first_line = entry.splitlines()[0].strip()
            for field_name in TASK_ENTRY_REQUIRED_FIELDS:
                field_pattern = re.compile(
                    r"\*\*" + re.escape(field_name) + r"[^*:]*:\*\*|"
                    r"\*\*" + re.escape(field_name) + r"\*\*\s*:",
                    re.IGNORECASE,
                )
                if not field_pattern.search(entry):
                    problems.append(
                        f"task entry '{first_line}' missing required field: {field_name}"
                    )

    return problems


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[-1] == "--list":
        print("Required top-level sections:")
        for h in REQUIRED_TOP_LEVEL_SECTIONS:
            print(f"  - {h}")
        print("Required per-task-entry fields:")
        for f in TASK_ENTRY_REQUIRED_FIELDS:
            print(f"  - {f}")
        return 0

    path = Path(argv[1])
    if not path.exists():
        print(f"FAIL: no such file: {path}")
        return 2

    text = path.read_text(encoding="utf-8")
    problems = check_contract(text)
    if problems:
        print(f"FAIL: {path} is not launch-ready ({len(problems)} problem(s)):")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"PASS: {path} carries every required structural field.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
