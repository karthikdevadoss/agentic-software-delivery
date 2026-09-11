---
name: production-verify
description: Independently verify that a deployed change's requested observable effect is genuinely live in real production — never HTTP 200 alone. Use after a change has been committed and deployed, before any terminal outcome is reported as COMPLETED.
---

# Verify the Requested Effect in Real Production

**Prescribed duty (single):** confirm the `AcceptanceContract`'s
`expected_observable_effect` is genuinely present in the real, live
production response — and refuse to let a run be called COMPLETED
otherwise. This Skill exists because this exact project's real public
Workbench once reported "Deployment: VERIFIED (HTTP 200)" for a change
that was NOT actually live yet (see docs/LESSONS.md, run
`trainer-7769757e`).

## Canonical sources (reference, do not restate)

- The real decision function (already fixed, do not reimplement):
  `agent/web_server.py::_decide_deployment_outcome` — COMPLETED requires
  BOTH `production_reachable` AND `content_verified`; reachable-with-
  wrong-content is a confirmed FAILED, never an ambiguous unknown.
- The real deploy-wait loop: `agent/web_server.py`'s `VERIFYING
  PRODUCTION` stage — polls the real production URL directly for the
  expected content (or a genuine timeout/explicit CLI failure), never
  exits early on a CLI text signal like "Online" (which can describe an
  OLD deployment still serving while a new one builds).
- The real workspace precondition:
  `agent/web_server.py::_check_repository_workspace_ready`.

## Lessons from real escaped production-truthfulness defects (all from
this project's own incidents — do not treat any of these as
hypothetical; each has a docs/LESSONS.md entry and a regression test)

1. **Target application infinite loading** — a card that fetches
   metadata with no timeout can stay on "Loading…" forever; always use a
   bounded timeout + truthful fallback.
2. **Missing Git workspace** — a cloud build context may genuinely lack
   `.git`; verify the repository workspace is real and usable BEFORE any
   source mutation, never discover this at commit time after cost is
   spent.
3. **Ambiguous Testing state** — a terminal run must never leave Testing
   looking pending; see the `test-change` Skill.
4. **HTTP-200 false production success** — HTTP 200 alone proves the
   server is reachable, nothing about the requested content.
5. **Deployment activation race** — a CLI status check can report the
   OLD deployment "Online" while a NEW one is still building; verifying
   too early sees stale content.
6. **Requested effect absent despite HTTP 200** — the exact failure mode
   this Skill exists to catch: reachable, wrong content, previously
   mislabeled VERIFIED.
7. **Terminal timing drift** — mixing a backend container's clock with a
   browser's clock can make a completed run's displayed duration grow
   forever or exceed its own total elapsed time; use one clock domain
   only.
8. **Failed-run token/cost visibility** — a FAILED run still spent real
   money; never hide its usage_summary just because the outcome was
   negative.
9. **No-op/idempotency misclassification** — an already-satisfied
   requirement must be labeled NO_CHANGE_NEEDED, never misreported as a
   FAILED (inconclusive) or a fabricated COMPLETED deploy.
10. **Generic failure without exact stage** — a FAILED/UNKNOWN result
    must always carry the specific stage and real error message, never a
    bare "something went wrong."
11. **Deployment polling timeout vs. actual later success** — a poll
    timeout is genuine uncertainty (DEPLOYMENT_STATUS_UNKNOWN), not
    automatically a confirmed failure; conversely, a later independent
    check finding the change live does not retroactively excuse an
    earlier false-positive claim — the claim at the time it was made
    must have been backed by real evidence, not just "it worked out."

## Inputs

- The `AcceptanceContract`.
- Deployment/commit evidence (commit sha, target service/environment).

## Outputs

- One of: `COMPLETED` (effect confirmed live), `FAILED` (reachable but
  effect confirmed absent, or explicit deploy failure), `NO_CHANGE_NEEDED`
  (investigation showed the effect was already true — no mutation
  attempted), `DEPLOYMENT_STATUS_UNKNOWN` (production genuinely
  unreachable, no confirmation either way).
- The real fetched evidence (response snippet/URL/timestamp), not a
  paraphrase.

## Must NOT

- Must NOT report COMPLETED from HTTP 200 alone.
- Must NOT report COMPLETED from a CLI "Online"/"success" text signal alone.
- Must NOT skip the independent fetch because "the deploy command
  succeeded."
- Must NOT retroactively excuse an early false-positive because a later
  check happened to find success — the evidence must have existed at
  decision time.
