# Prompt Engineering Lessons

Real, evidenced lessons about prompting/context design from building this
project — not generic prompt-engineering advice. Each lesson names the
actual mechanism this project uses today because of it.

## 1. Context beats cleverness for factual grounding

The single biggest quality jump in this project's history was not a better
prompt — it was giving the model real repository context to reason from.
V1 (ticket text only) hallucinated plausible-but-nonexistent components.
V2 (static repo context injected into the prompt) fixed most of that. V3
(the model choosing what to inspect via tools) improved further because the
model could pull exactly the context relevant to *this* requirement instead
of a fixed bundle. **Lesson: before tuning prompt wording, ask whether the
model actually has access to the ground truth it needs.**

## 2. Retrieved context must be provably non-authoritative until verified

RAG search results are candidates, not facts. This project's agent still
calls `read_file`/`search_code` to confirm anything a semantic search
surfaces before treating it as true — and a deterministic groundedness
checker (`agent/backend_planning.py::check_groundedness`) flags any file the
model *claims* to have used that it never actually retrieved. **Lesson:
"the model cited a source" and "the model actually verified that source's
current content" are different claims — build the check for the second one,
don't assume it from the first.**

## 3. A security/authorization boundary belongs in code, never in the prompt alone

No instruction in this project's system prompt is the thing preventing the
model from, say, deleting a repository or pushing to `master` — the actual
boundary is Python code (`write_tools.py`'s scope restriction,
`risk_policy.py`'s classification, approve/reject never being a
model-callable tool at all). Adversarial testing against the live
risk-classification endpoint found real *text-classifier* gaps (a prompt
correctly worded to sound authorized) — all of them were still blocked by
the independent, code-level file-scope allowlist regardless. **Lesson:
treat the prompt/classifier layer as a UX/efficiency improvement, never the
actual security boundary — verify the boundary holds even when the prompt
layer is adversarially defeated.**

## 4. Distinguish "must never happen" from "should ideally not happen" in acceptance criteria

`.claude/skills/requirement-contract/SKILL.md`'s Verification Contract
design exists because a vague "make sure it works" acceptance criterion
produces vague verification. Explicit `negative_cases`,
`security_expectations`, and `required_test_categories` fields force a
requirement author (human or the model interpreting a requirement) to state
what a genuinely acceptable answer excludes, not just what it includes.
**Lesson: an acceptance criterion phrased only as a positive outcome
("returns the customer") is under-specified — pair it with what a
plausible-but-wrong answer would look like.**

## 5. A model's own PASS/FAIL self-report is a UX signal, not evidence

The pipeline's own terminal-outcome banner (COMPLETED/FAILED/TIMEOUT) is
useful for a human watching the Workbench live — but AEQ-013 proved it can
be wrong in both directions (false TIMEOUT twice, false FAILED once) while
the underlying delivery had genuinely succeeded. Real verification always
came from an independent source: a direct `curl` against production, real
`railway logs`, real `railway deployment list --json`. **Lesson: design the
self-report for legibility to a human, and design a completely separate,
independently-sourced check for the actual pass/fail decision — never let
the same process grade its own homework, even when its grading logic looks
reasonable.**

## 6. Investigation cost is not proportional to change size

A "TINY" requirement's token cost is dominated by how much the model has to
*read* to confirm the change is safe and correct, not by how much code it
writes. AEQ-005's real measurement (126% over a heuristic's own predicted
range) came entirely from a single file read plus a single compile call.
**Lesson: size cost estimates by expected investigation depth (how many
files/tools the task plausibly requires touching), not by the size of the
expected diff.**

## 7. Every content-generation task should checkpoint before expensive verification, not after

A large body of genuinely good work (13 new domains, 23 new interview
topics) once sat uncommitted across a session-quota boundary purely because
verification was still in progress when the session ran out. **Lesson: for
any long task, commit+push as soon as the work is internally consistent and
minimally test-passing — treat full independent QA/deploy as a separate,
later step that a checkpoint should never be blocked on. This is now a
standing operational rule (docs/LESSONS.md), not a one-off fix.**

## 8. State machine changes need an explicit consumer audit, not a targeted patch

Adding one new terminal state (`NO_CHANGE_NEEDED`) to fix one bug
immediately broke SSE stream termination elsewhere, because a second,
duplicated terminal-state list existed that nobody thought to check in the
same change. **Lesson: when a prompt/harness change introduces a new
state/label/category the model or the system can produce, explicitly
enumerate every consumer of the old set (execution, persistence, UI,
tests, docs) rather than trusting that "the one place I changed" was the
only place that mattered.**

## 9. A fixture that's supposed to mirror the real artifact will silently stop doing so

`agent/demo_catalogue.py`'s self-test claimed to check anchors "against the
REAL baseline file" but actually read a separately-committed, long-stale
copy — invisible until a human happened to notice while doing unrelated
work (AEQ-014). **Lesson: when writing a test/prompt/context source that's
supposed to represent "the real current state of X," either make it read X
directly or add a drift-detection check — a hand-maintained mirror will
eventually diverge, silently, and nothing will say so until someone
notices by accident.**

## 10. Never let a prompt-layer classifier be the only thing standing between a user request and a dangerous action

Distinct from lesson 3 but related: this project's public Workbench
deliberately runs a **deterministic, zero-API-cost catalogue match** first
for its bounded public demo path (agent/demo_catalogue.py) — the LLM is not
even called for that path, so there is no prompt-injection surface to
defend in the first place for the operations that are actually exposed
publicly. **Lesson: for a bounded, well-known set of safe operations, a
deterministic matcher that never calls the model at all is both cheaper and
strictly safer than an LLM-mediated gate — reserve the LLM for genuinely
open-ended requirements, behind the code-level authorization boundary from
lesson 3.**
