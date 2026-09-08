"""
Week 1 planning agent.

Reads a plain-text software requirement and asks Claude to produce a
numbered implementation plan. It does not read the Java repository and
does not modify any files.
"""

import os
import sys

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-5"
MODEL = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)

PROMPT_TEMPLATE = """You are a senior software engineer helping plan a change to an \
existing Spring Boot (Java 17) application.

Given the following requirement, produce a numbered implementation plan with \
these sections:

1. What needs to change
2. Likely files/classes affected
3. Order of implementation
4. Tests that should be added
5. Risks or edge cases

Requirement:
{requirement}
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


def build_plan(requirement: str, api_key: str) -> str:
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[
            {"role": "user", "content": PROMPT_TEMPLATE.format(requirement=requirement)}
        ],
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

    plan = build_plan(requirement, api_key)
    print(plan)


if __name__ == "__main__":
    main()
