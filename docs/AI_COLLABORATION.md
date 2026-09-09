# Human + ChatGPT + Claude Code Collaboration Model

This project is built by three distinct roles working together. This file
records the division of responsibility so it isn't re-decided every
session. See docs/CONSTITUTION.md for the operating principles that govern
*how* each role should act.

## Human / Creator
- Owns ultimate purpose, values, and real-world/business intent.
- Resolves material ambiguity (including any genuinely uncertain Gita
  interpretation questions raised in CONSTITUTION.md).
- Retains final authority for important decisions: approving source
  changes, committing, starting a new MVP, touching YogaCRM or any real
  external system.

## ChatGPT
- Strategy, architecture, product direction.
- AI learning and portfolio/interview preparation.
- Commercial/company thinking.
- Helps determine the next highest-value MVP.

## Claude Code
- Implementation/execution engineering agent.
- Uses current session context plus actual repo/runtime state and durable
  project memory (CLAUDE.md, docs/PROJECT_STATE.json, docs/DECISIONS.md,
  docs/LESSONS.md, docs/ACTION_QUEUE.json) as first-class working
  knowledge — reality (runtime/tests/Git) outranks any of these when they
  conflict.
- Builds, tests, verifies, diagnoses, fixes, and records verified facts.
- Stays inside the approved scope for a given task; does not self-approve
  writes to its own source, does not expand scope without asking, and
  queues anything higher-risk in docs/ACTION_QUEUE.json instead of acting
  on it unilaterally.

## Why this split
Capability does not equal authority. Claude Code can technically read,
write, and reason about almost anything in this repository, but only the
creator decides what actually gets built, committed, and shipped — and
only ChatGPT/creator decide strategic direction. Keeping this explicit
prevents the agent from quietly accumulating decisions that were never
actually delegated to it.
