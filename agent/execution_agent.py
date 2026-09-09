"""
V4.1 live execution agent CLI.

Unlike agent/main.py (read-only planning only), this entry point gives
Claude the ability to propose and apply source changes and run compile/test
— gated by a synchronous human approve/reject prompt inside
execution_tools.propose_source_change. The LLM has no tool that can approve
its own proposal; only a human typing at this terminal can (see
execution_tools.py's module docstring for the exact invariant and how it's
enforced/tested).

Run: python agent/execution_agent.py requirements/sample_requirement.txt
"""

import sys

from main import read_requirement, get_api_key
from agent_loop import run_agent_loop
from execution_tools import EXECUTION_TOOL_SCHEMAS, dispatch_execution_tool_call

EXECUTION_SYSTEM_PROMPT_SUFFIX = """

You additionally have four more tools for this session:
- propose_source_change: propose a full-file content change. This pauses \
for a real human approve/reject decision before returning — you cannot \
approve your own proposal.
- apply_approved_source_change: write a proposal to disk. Only works if a \
human already approved it.
- run_controlled_compile / run_controlled_tests: run the Customer app's \
build/test verification.

Workflow: understand the ticket using your existing read-only tools first. \
Only propose a change once you have concrete evidence for what needs to \
change and where. After a change is applied, run the controlled compile \
(and tests, if relevant) to verify it, and report the real result — do not \
claim success without having run the verification tool.
"""


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python agent/execution_agent.py <path-to-requirement.txt>")
        sys.exit(1)

    requirement = read_requirement(sys.argv[1])
    api_key = get_api_key()

    result = run_agent_loop(
        requirement,
        api_key,
        tool_schemas=EXECUTION_TOOL_SCHEMAS,
        dispatch_fn=dispatch_execution_tool_call,
        system_prompt_suffix=EXECUTION_SYSTEM_PROMPT_SUFFIX,
    )
    print(result)


if __name__ == "__main__":
    main()
