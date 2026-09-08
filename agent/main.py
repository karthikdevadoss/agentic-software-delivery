"""
Ticket-to-implementation-plan agent (V2, repository-aware).

Reads a plain-text software requirement, collects a compact summary of the
actual local repository (Java source structure + docs), and asks Claude to
produce a numbered implementation plan grounded in that real context. It
does not modify any files.
"""

import os
import sys

from dotenv import load_dotenv
from anthropic import Anthropic

from repo_context import build_repository_context

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-5"
MODEL = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

PROMPT_TEMPLATE = """You are a senior software engineer helping plan a change to an \
existing Spring Boot (Java 17) application.

You are given (1) a repository context extracted directly from the actual \
codebase, and (2) a change ticket. Treat the repository context as ground \
truth about what already exists. Do not invent files, classes, methods, or \
endpoints that are not shown in it — if something you would expect is \
missing, say so explicitly using the exact phrase "not found in repository \
context" instead of guessing or assuming it exists.

Repository context:
{repo_context}

Ticket:
{requirement}

Produce a numbered implementation plan with these sections:

1. Existing components (verified from repository context)
   - List the actual existing files/classes relevant to this ticket, using \
their real package and class names as shown in the repository context above. \
If something relevant to the ticket is not present (e.g. an update-email \
endpoint), state plainly that it was "not found in repository context".
2. Required changes (from the ticket)
   - What must change to satisfy the ticket, referencing existing files/classes \
by their real names where possible.
3. Recommended changes / assumptions needing confirmation
   - Anything you are recommending or assuming beyond the literal ticket text \
(e.g. normalization rules, error response shape) that should be confirmed \
with the team before implementation.
4. Order of implementation
5. Tests that should be added
6. Risks or edge cases
"""


def read_requirement(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
    except FileNotFoundError:
        print(f"Error: requirement file not found: {path}")
        sys.exit(1)

    if not content:
        print(f"Error: requirement file is empty: {path}")
        sys.exit(1)

    return content


def get_api_key() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Error: ANTHROPIC_API_KEY is not set. "
            "Set it in your environment or in a .env file."
        )
        sys.exit(1)
    return api_key


def build_plan(requirement: str, repo_context: str, api_key: str) -> str:
    client = Anthropic(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(repo_context=repo_context, requirement=requirement)
    message = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )

    text_blocks = [block.text for block in message.content if block.type == "text"]

    if not text_blocks:
        block_types = [block.type for block in message.content]
        raise RuntimeError(
            f"No text block in response (stop_reason={message.stop_reason!r}, "
            f"content block types={block_types!r})"
        )

    return "".join(text_blocks)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python main.py <path-to-requirement.txt>")
        sys.exit(1)

    requirement_path = sys.argv[1]
    requirement = read_requirement(requirement_path)
    api_key = get_api_key()
    repo_context = build_repository_context()

    plan = build_plan(requirement, repo_context, api_key)
    print(plan)


if __name__ == "__main__":
    main()
