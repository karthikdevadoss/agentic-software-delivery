# Update Email V3 Replay — Real Evidence Summary

Base commit (immediate parent of `4440f6d`, the real commit that first
implemented Update Email on the actual project history):
`26bcff087793b75964c70f5f1618f6722ef93dd6`

Branch: `trainer-replay/update-email-v3` (isolated worktree at
`C:\Users\Hemapriya\trainer-replay-update-email`, never merged to master,
never deployed).

Mechanism: the real V4.1 direct-tool-calling agent
(`agent/execution_agent.py`'s real `run_agent_loop` +
`EXECUTION_TOOL_SCHEMAS`/`dispatch_execution_tool_call`, driven via
`agent/replay_driver.py`, a new driver script using
`execution_tools.set_approval_prompt()` — a real, pre-existing extension
point documented in that module's own source as existing "for automated
tests and for a future non-CLI trusted host," not invented for this
replay).

## Real runs performed (4 completed — Run 4 reached a real candidate)

**Run 1** (`run1_real_tool_trace.log`) — `MAX_TOOL_CALLS=8` (the real,
unmodified historical default). Real result: all 8 calls consumed by
read-only investigation (`list_repository_files`, 6×`read_file`,
1×`search_code`), never reached a proposal. Tool budget exhausted before
investigation completed.

**Run 2** (`run2_real_tool_trace.log`) — `MAX_TOOL_CALLS` raised to 20 (a
disclosed, transparent runtime adaptation — see `replay_driver.py`'s own
comment; does not touch any approval/write-scope/security boundary).
Real result: 20 real tool calls, still all read-only investigation, still
budget-exhausted before proposing. Produced a real, substantive partial
finding: **no workspace/tenant/ownership concept exists anywhere in this
codebase** — every demo JWT carries the same global scope set with no
customer-id/tenant claim, so the ticket's "a user must not update another
workspace/customer" requirement cannot be satisfied by anything beyond a
scope check with the code as it stands. This is a genuine investigation
finding, not fabricated.

**Run 3** (`run3_real_tool_trace.log`) — `MAX_TOOL_CALLS=32`. Real result:
27 real tool calls (stopped itself before hitting the raised ceiling),
producing a complete, real 6-part implementation plan (Existing
components / Required changes / Recommended changes / Order of
implementation / Tests / Risks), explicitly confirming the workspace-gap
finding from Run 2 and adding real detail: a proposed
`CustomerEmailUpdateRequest` DTO (mirroring the existing
`CustomerPreferenceUpdateRequest` pattern), 6 concrete test cases to add,
and a named `SecurityConfig` matcher-ordering risk. The agent's own last
line: *"I have not made any code changes yet — this is the planning
deliverable requested... Let me know if you'd like me to proceed with
implementation."* **It never called `propose_source_change`.**

**Honest evidence-preservation gap**: Run 3's full final plan text was
written to a JSON evidence file that was deleted before Run 4 (to avoid a
real, observed side effect — Run 2's evidence file, written inside the
repo tree, was itself read back by Run 3's own `read_file` calls, a
genuine methodological contamination risk fixed by moving evidence
output outside the repo tree for Run 4). Only the tool-call trace and a
partial view of the final text (captured in the coordinating session's
own terminal output, not re-transcribed here to avoid embellishing what
was actually preserved) survive for Run 3. This gap is disclosed, not
hidden.

**Run 4, attempt 1 (2026-09-15)** — added one explicit instruction to the
ticket ("after forming your plan, proceed directly to
`propose_source_change`... rather than waiting for a separate
confirmation") to close the real behavioral gap Runs 1-3 exposed (the
base `SYSTEM_PROMPT`, shared from V2/V3, literally asks for "a numbered
implementation plan" with no instruction to implement afterward — a
real, disclosed prompt-design gap, not a scripted trick). **Failed
before any tool use**: a direct minimal test call independently
confirmed `anthropic.BadRequestError: Your credit balance is too low to
access the Anthropic API` — a genuine, persistent billing block, not
transient (re-tested once, same error).

**Run 4, attempt 2 (2026-09-16, `run4_real_tool_trace.log`,
`run4_evidence.json`)** — re-run of the exact same corrected ticket/prompt
after Karthik confirmed (live in the Anthropic Console, not assumed)
organization credits restored ($19.89, no unpaid balance). Real result:
`run_id=trainer-replay-update-email-1789551491`,
`base_sha=febc26cdecc0e650da247a8cdab528f19e1146db`, 29 real read-only
tool calls (broader investigation than Runs 1-3: also inspected
`SecurityIntegrationTest.java`, `CustomerPreferenceResponse.java`,
`docs/PROJECT_STATE.json`, `docs/ACTION_QUEUE.json`'s
`PHASE-3-UPDATE-EMAIL-BACKEND-DEMO` entry, and `app/pom.xml`), then **two
real `propose_source_change` calls** — the fix-forward instruction
worked. Both proposals add one method to `CustomerService.java`:

```java
public Customer updateEmail(Long id, String newEmail) {
    Customer customer = getById(id);
    customer.setEmail(newEmail);
    return customerRepository.save(customer);
}
```

(attempt 1, `edit_id=d085a363`, `candidate_hash=6f06eb1e...`, included an
explanatory Javadoc comment; attempt 2, `edit_id=70bc47ab`,
`candidate_hash=239ddd43...`, the bare version after the first was
rejected). Both were **genuinely rejected** by `replay_driver.py`'s
`_capture_and_reject` (no real human approver present in this automated
replay — fail-closed by design, exactly as the real architecture
requires), never approved on the Owner's behalf. The agent's own final
text after both rejections asked clarifying questions rather than
resubmitting blindly (HTTP verb/path choice, raw-`String` vs. DTO
parameter, whether the workspace-authorization gap must be resolved
first) — a real instance of the agent recognizing repeated rejection as
a signal to ask, not just retry.

**This proposal is a partial slice, not the full ticket** — it adds only
the service-layer method. No controller/endpoint, no DTO, no validation,
no authorization check, and no test were proposed in this run (the
9-line diff was small enough that reaching a full working feature would
need further turns/proposals this run did not take, since the agent
stopped to ask for design confirmation after two rejections instead of
continuing). The known workspace/tenant-isolation gap (Run 2's finding,
reconfirmed in Run 3's plan) remains real and unresolved by this diff.

## What this means for the trainer exercise

The real V3/V4.1 agent's requirement-interpretation and repository-
investigation phases are fully, genuinely demonstrated across all 4 runs
(84 real tool calls total: 55 from Runs 1-3 + 29 from Run 4 attempt 2),
including real findings (the workspace-authorization gap) that persisted
correctly across runs. **The propose→approval boundary was reached for
the first time in Run 4 attempt 2** — two real candidates were proposed
and both were genuinely, correctly rejected by the fail-closed replay
harness (no human present), exactly demonstrating the designed boundary:
the agent cannot approve its own proposal, and no code was written to
disk anywhere in this worktree as a result of this run (verified: `git
status --short` on this branch is clean after the run).

**A real candidate now exists for a human to review** — see the diff and
both candidate/diff hashes above, or `run4_evidence.json` for the full
machine-readable record (including the complete final agent text). If
the Owner wants this specific candidate applied, that requires a fresh
run of `agent/execution_agent.py` (the real interactive CLI, not this
automated replay driver) so a real terminal-attached human can type a
real "y" — `replay_driver.py`'s automated rejection is intentional and
cannot itself apply anything. This candidate is also, by the Owner's own
review above, incomplete relative to the full ticket (service method
only) — a fuller candidate would need controller/DTO/validation/
authorization/test additions the agent did not reach in this run.
