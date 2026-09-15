"""
Trainer Session 2 homework -- REAL historical replay of the V3/V4.1 direct-
tool-calling agent against the real pre-Update-Email commit (26bcff0), the
immediate parent of 4440f6d (where Update Email was first genuinely
implemented on the real project history).

This is a REAL execution: real Anthropic API calls, real repository
investigation via the real read-only tools, a real propose_source_change
call against write_tools.py's real validation/diffing, real approval-gate
behavior. Nothing here is scripted/fabricated.

APPROVAL: execution_tools.set_approval_prompt() is a real, pre-existing
extension point (see its own docstring: "exists for automated tests and
for a future non-CLI trusted host") -- not invented for this replay. This
driver uses it to CAPTURE the full pending-edit evidence (id, path, diff,
candidate hash, diff hash) for every real proposal the agent makes, then
genuinely REJECTS each one (never approves on the Owner's behalf) so the
real fail-closed architecture is exercised honestly, and the pending
artifact is preserved for a real human to review and approve later.

Run: python agent/replay_driver.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import agent_loop
from main import get_api_key
from agent_loop import run_agent_loop
from execution_tools import EXECUTION_TOOL_SCHEMAS, dispatch_execution_tool_call, set_approval_prompt

# TRANSPARENT, DISCLOSED ADAPTATION (not silently done): the real historical
# MAX_TOOL_CALLS=8 budget was exhausted entirely by read-only investigation
# on the first real run of this exact ticket (7 real read_file/search_code
# calls across Controller/Service/Customer/SecurityConfig/Preference files),
# never reaching propose_source_change at all. This is a resource-budget
# constant, NOT a security/approval boundary -- raising it does not weaken
# write-scope restrictions, path security, or the real human-approval gate
# (still enforced below via set_approval_prompt, never bypassed). Raised
# here at runtime only (the committed agent_loop.py constant is untouched)
# so the real agent can reach a real proposal for this multi-file,
# security-sensitive ticket in one continuous session.
agent_loop.MAX_TOOL_CALLS = 32

REPO_ROOT = Path(__file__).resolve().parent.parent
# Written OUTSIDE the repo tree during the run (methodological cleanliness:
# an earlier run's evidence file, when written inside docs/training/, was
# itself picked up by list_repository_files/read_file on the NEXT replay
# run -- a real, disclosed side effect, not hidden). Copied into
# docs/training/ only after the run completes.
EVIDENCE_PATH = Path(r"C:\Users\Hemapriya\agentic-software-delivery\.scratch\update_email_replay_evidence.json")

TICKET = """Update customer email.

A customer must be able to update only their email address.

The customer's name and unrelated customer fields must remain unchanged.

Validate the new email address.

An authenticated USER must only be able to update a customer they are
authorized to access.

A user must not update another workspace/customer.

The new email must actually persist and be returned by a subsequent read.

Missing customers must fail correctly.

After you finish investigating and have formed your plan, proceed directly
to calling propose_source_change for the bounded, primary code change
(start with the single file most central to the change) rather than
stopping at the plan alone and waiting for a separate confirmation to
propose."""

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

_captured_proposals = []


def _real_git_head_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


def _capture_and_reject(edit) -> bool:
    """The real approval gate for this replay: preserves the exact pending
    artifact, then genuinely rejects (never approves on the Owner's
    behalf). If the Owner later reviews docs/training/
    update_email_replay_evidence.json and wants to proceed, THEY must
    re-run this exact candidate through a real approval."""
    candidate_hash = hashlib.sha256(edit.new_content.encode("utf-8")).hexdigest()
    diff_hash = hashlib.sha256((edit.diff or "").encode("utf-8")).hexdigest()
    record = {
        "edit_id": edit.id,
        "path": edit.path,
        "is_new_file": edit.is_new_file,
        "base_sha": _real_git_head_sha(),
        "candidate_hash": candidate_hash,
        "diff_hash": diff_hash,
        "diff": edit.diff,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "REJECTED (no real human approver present in this autonomous replay -- fail-closed by design, exactly as the real architecture requires)",
    }
    _captured_proposals.append(record)
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"REAL PROPOSAL CAPTURED (edit_id={edit.id}, path={edit.path})", file=sys.stderr)
    print(f"candidate_hash={candidate_hash}", file=sys.stderr)
    print(f"diff_hash={diff_hash}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    return False


def main() -> None:
    set_approval_prompt(_capture_and_reject)
    api_key = get_api_key()
    run_id = f"trainer-replay-update-email-{int(datetime.now(timezone.utc).timestamp())}"

    print(f"RUN_ID: {run_id}", file=sys.stderr)
    print(f"BASE_SHA: {_real_git_head_sha()}", file=sys.stderr)

    final_text = run_agent_loop(
        TICKET, api_key,
        tool_schemas=EXECUTION_TOOL_SCHEMAS,
        dispatch_fn=dispatch_execution_tool_call,
        system_prompt_suffix=EXECUTION_SYSTEM_PROMPT_SUFFIX,
    )

    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    evidence = {
        "run_id": run_id,
        "base_sha": _real_git_head_sha(),
        "ticket": TICKET,
        "final_agent_text": final_text,
        "proposals": _captured_proposals,
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"\nEvidence written: {EVIDENCE_PATH}", file=sys.stderr)
    print(f"Real proposals captured: {len(_captured_proposals)}", file=sys.stderr)


if __name__ == "__main__":
    main()
