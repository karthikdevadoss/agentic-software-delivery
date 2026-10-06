import unittest

from check_task_template import check_contract, REQUIRED_TOP_LEVEL_SECTIONS

VALID_CONTRACT = """
# Some Sprint Contract

## Role / session identity

Role: Indra. Model: Sonnet.

## Bounded production calls

zero production calls this session.

## Hard stop / exit rules

Stop after 5 hours.

## Mission

Do the thing.

## Verified facts only, never asserted

- Facts verified before this contract was written: branch exists (git branch -a)
- Facts assumed/hypothesised: none

## Task queue

### T1 -- Fix the thing (~30 min)
- **What:** fix it
- **Why:** it's broken
- **Page purpose:** N/A -- not a page change
- **Quality acceptance:** the fix is correct, not just present
- **Done when:** tests pass
- **Skip if:** blocked by missing credentials

### T2 -- Update the page (~40 min)
- **What:** update copy
- **Why:** jargon cleanup
- **Page purpose:** explains the Usage page's metrics in plain English
- **Quality acceptance:** a non-technical reader understands the numbers
- **Done when:** copy committed
- **Skip if:** never

## Out of scope

- Production deploys
- Other teams' work

## Committed report

Write docs/indra/RETRO.md with the task table.
"""

MISSING_SECTIONS_CONTRACT = """
# Some Sprint Contract

## Mission

Do the thing.

## Task queue

### T1 -- Fix the thing (~30 min)
- **What:** fix it
"""

MISSING_TASK_FIELDS_CONTRACT = VALID_CONTRACT.replace(
    "- **Page purpose:** N/A -- not a page change\n", ""
).replace(
    "- **Quality acceptance:** explains the Usage page's metrics in plain English\n",
    "",
)


class TestCheckTaskTemplate(unittest.TestCase):
    def test_valid_contract_has_no_problems(self):
        self.assertEqual(check_contract(VALID_CONTRACT), [])

    def test_contract_missing_most_sections_fails_and_names_each(self):
        # This fixture is observed failing first, for the real reason: it
        # is missing most required sections, and the detector must name
        # all of them, not just the first one found.
        problems = check_contract(MISSING_SECTIONS_CONTRACT)
        self.assertTrue(problems)
        for heading in REQUIRED_TOP_LEVEL_SECTIONS:
            if heading in ("Mission", "Task queue"):
                continue
            self.assertTrue(
                any(heading in p for p in problems),
                f"expected a problem naming missing section '{heading}', got: {problems}",
            )

    def test_task_entry_missing_page_purpose_is_caught(self):
        problems = check_contract(MISSING_TASK_FIELDS_CONTRACT)
        self.assertTrue(
            any("Page purpose" in p and "T1" in p for p in problems),
            f"expected T1's missing Page purpose to be caught, got: {problems}",
        )

    def test_task_queue_with_no_task_entries_is_caught(self):
        no_entries = VALID_CONTRACT.split("## Task queue")[0] + "## Task queue\n\n## Out of scope\n\nnone\n\n## Committed report\n\nhere\n"
        problems = check_contract(no_entries)
        self.assertTrue(any("no '### " in p for p in problems))


if __name__ == "__main__":
    unittest.main()
