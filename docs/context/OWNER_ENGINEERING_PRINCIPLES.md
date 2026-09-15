# Owner Engineering Principles (pointer)

Full detail and the actual governing text: `docs/CONSTITUTION.md` — read
that file whenever a duty/scope/priority/truthfulness question isn't
obviously answered by CLAUDE.md's own rules. Do not restate a conflicting
summary of the Constitution here; if this file and `docs/CONSTITUTION.md`
ever disagree, the Constitution wins and this file is stale.

## Headline principles (see the Constitution for the authoritative, complete versions)

- **Deterministic-first architecture law:** do not use an LLM where
  software can solve the problem more reliably. LLMs are for genuine
  semantic work (interpretation, true ambiguity, novel proposals,
  synthesis/explanation); deterministic/symbolic tools own computable
  truth. Model output is a proposal, never evidence; model confidence is
  never truth.
- **Evidence over claims:** no stage is green unless it actually
  occurred. `UNKNOWN != ZERO`, `UNKNOWN != PASS`, `git push != deployment`,
  `HTTP 200 != product correctness`, an LLM saying "it works" is not
  verification.
- **Root-cause discipline:** a defect is not closed because its visible
  symptom disappeared — see `docs/LESSONS.md` and CLAUDE.md's Stability /
  Execution Discipline and Feedback Discipline sections for the full
  defect-handling workflow.
- **Durable state over conversation memory:** repository files and Git are
  authoritative; conversation history is supplementary. See CLAUDE.md's
  Durable-state rules.
- **Capability boundaries over instructional prohibition:** a prompt
  telling an agent not to do something is not a security boundary —
  prefer actual technical capability restriction. (Recorded as a
  permanent lesson after a prior subagent deployed to production despite
  being told not to — see `docs/LESSONS.md`.)

This project's engineering principles and Karthik's professional/career
principles (first-principles learning, resume-truth rules, ask-vs-assume
collaboration style) are two different things — the latter lives in the
private `karthik-ai-context` repository, not here.
