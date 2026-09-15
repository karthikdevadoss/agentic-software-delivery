# Incident Triage & Repair Lab — Architecture and Status

**STATUS UPDATE (2026-09-15): Scenario A is LIVE at `/triage`, not just
designed.** Everything below describing Scenario A's original read-only
"historical evidence replay" recommendation was superseded the same
night by an explicit Owner course-correction asking for genuine live
reproduction plus a real AI-generated candidate patch — both now exist:

- Real, isolated live reproduction of the actual historical defect
  (`app/src/main/java/com/example/customer/triage/TriageScenarioAService`).
- Real on-demand Claude diagnosis over real evidence (`agent/triage_execution.py::diagnose`).
- Real historical reference diff (relabeled "HISTORICAL REFERENCE PATCH",
  never shown as a live proposal) via `get_patch_diff()`.
- **Real AI-generated candidate patch** (`generate_candidate_patch()`): a
  second Claude call, never told the historical answer, writes an actual
  fix from the real defective file + real evidence.
- **Real isolated verification** (`apply_and_verify_candidate()`): the
  candidate is applied in a temp copy of `app/` (never the real repo) and
  compiled for real via `mvnw compile` — browser-verified live: the model
  produced a correct fix and it genuinely `COMPILE_VERIFIED`.
- Real admin-JWT-gated human approval (401 anonymous, 403 non-admin, 200
  real admin1/admin2 login) — the scenario's one HUMAN APPROVAL REQUIRED
  action, flipping only the isolated scenario's own state.

**Still genuinely not built** (deliberately parked, not a gap that was
missed): promoting an APPROVED candidate patch to an actual git commit,
push, and Customer App deployment — see `docs/ACTION_QUEUE.json`'s
`TRIAGE-CANDIDATE-PROMOTION-PIPELINE`. Autonomously committing
AI-generated code to the real repository and deploying it to real
production with no human present to review the diff first is exactly
the class of irreversible action this project reserves for genuine human
approval, not a capability this session lacked time for.

The original design content below (`triage/scenarios.yaml`'s 3-scenario
catalogue, Scenarios B/C) remains accurate for what it describes — only
Scenario A's own status line above is corrected.

## Why this exists (recap)

Workbench proves the platform can **build/change** software from a
requirement. Triage Lab proves it can **diagnose and repair** an existing
failure — a different, equally important recruiter-facing capability:
reproduce → investigate → AI diagnosis → proposed fix (real diff) →
verification (Test Impact Analysis + selective tests) → **human approval
required** → commit/deploy → rerun the exact same scenario → confirm
resolved.

## Grounding: three real defects, not fabricated ones

Per the master instruction ("do NOT implement fake failures... instead
design actual defective behavior... the defect itself must be a real
engineering mistake"), `triage/scenarios.yaml` catalogues three scenarios,
each backed by a real, inspectable artifact:

1. **Plan enrollment idempotency** — a real gap found by inspection this
   session (no test previously covered a repeated identical `enroll()`
   call) and fixed in commit `2155a8a`. See
   `docs/interview-scenarios/04-plan-enrollment-idempotency.md`.
2. **Appointment downstream resilience** — not currently a bug (the real
   Resilience4j retry/circuit-breaker path is already correct and
   WireMock-tested), but the **safe-simulation architecture already
   exists and is live**: `DemoAppointmentProviderController` exposes a
   real internal HTTP endpoint with `?scenario=timeout|error` query
   params that trigger a genuine client-side timeout / genuine 500 over
   a real loopback HTTP call — never a hardcoded `if (demo) return 500`
   inside the actual business path. This is the template every other
   scenario's live re-demo should copy for isolation.
3. **Admin search Postgres type-inference 500** — a real, already-fixed
   production incident (commit `9f35f27`): H2 passed, real Postgres
   500'd on `LOWER(bytea)` because a bind parameter's type couldn't be
   inferred through a JPQL `CONCAT`. Full before/after evidence already
   exists in `docs/interview-scenarios/02-postgres-search-pagination.md`.

## Architecture (designed, for when this is built)

```
Recruiter/interviewer picks a scenario
   |
   v
GET /triage                      (agent/web/triage.html — new, not yet built)
   |-- reads triage/scenarios.yaml (deterministic catalogue, never model-authored)
   v
STEP 1: REPRODUCE
   |-- real request against a demo-workspace-scoped resource
   |-- shows expected vs. actual (the real defective behavior, safely reproduced)
   v
STEP 2: INVESTIGATE
   |-- real evidence: HTTP result, relevant source excerpt, DB state where safe,
   |   correlation/trace id, WireMock/test evidence for Scenario B
   v
STEP 3: AI DIAGNOSIS
   |-- hypothesis + evidence used + root-cause conclusion + confidence
   |-- concise, inspectable rationale — never raw hidden chain-of-thought
   v
STEP 4: PROPOSED FIX
   |-- real diff (reusing agent/write_tools.py's propose/approve/apply boundary
   |   and agent/change_risk.py + agent/test_impact_analysis.py, NOT reinvented)
   v
STEP 5: VERIFICATION
   |-- Test Impact Analysis-selected tests actually run; pass/fail shown
   v
STEP 6: HUMAN APPROVAL REQUIRED  <-- explicit, non-bypassable gate
   |-- [APPROVE FIX]  [REJECT]
   |-- only a real Owner/admin-authenticated action reaches commit/deploy
   v
commit -> push -> deploy -> deployment-identity confirmation
   -> rerun the EXACT SAME reproduction from Step 1
   -> before/after comparison -> INCIDENT RESOLVED
```

**Reused, not reinvented:** the propose/approve/apply write boundary
(`agent/write_tools.py`), the deterministic risk/blast-radius classifier
(`agent/change_risk.py`), Test Impact Analysis
(`agent/test_impact_analysis.py`), the isolated-workspace git/deploy
machinery (`agent/demo_execution.py`), and deployment-identity
confirmation via real timestamps — all already exist from Workbench and
would be the actual execution substrate for Triage Lab, not a parallel
implementation.

## Isolation / safety design (per the master instruction)

- A public visitor may select a scenario, reproduce it, and inspect the
  proposed diff — never receive unrestricted Git/deploy authority.
- Any live re-demo of a scenario (e.g., re-triggering the pre-fix
  duplicate-enrollment behavior for Scenario A) must be gated to an
  isolated demo-workspace customer id, exactly like
  `DemoAppointmentProviderController` already does for Scenario B —
  never a global toggle reachable by a real customer's requests.
- Real commit/deploy approval requires actual Owner/admin authentication
  — a public visitor reaching Step 6 sees the gate and can request
  approval, but cannot self-approve. This mirrors the existing Workbench
  precedent where larger changes require Owner Authorization rather than
  auto-executing.

## What would be needed to actually wire this (not done tonight)

1. `agent/triage_catalogue.py` — loads and validates `triage/scenarios.yaml`
   (mirrors `agent/demo_catalogue.py`'s design).
2. A safe re-demo mechanism for Scenario A specifically: since the real
   bug is already fixed in mainline, a live "before" state needs either
   (a) a scenario-gated flag inside `ContractPlanService` that only an
   isolated demo-workspace customer id can trigger (adds a real,
   reviewable code path, needs its own tests proving it can never affect
   a real customer), or (b) presenting the already-real historical
   evidence (commit diff, before/after plan-history query) without a
   live "re-break" step — safer, and arguably more honest, since it
   doesn't require re-introducing a fixed bug anywhere, even gated.
   **Recommendation: option (b) for Scenario A and C** (both are
   real historical incidents — replay the evidence, don't re-break
   production-adjacent code for a demo); **option, effectively already
   done, for Scenario B** (it's a live simulation of environmental
   failure, not a code defect, so re-triggering it is safe by
   construction).
3. `agent/web/triage.{html,js,css}` — the 6-step UI described above.
4. `agent/web_server.py` routes: `GET /triage`, `GET /api/triage/scenarios`,
   `POST /api/triage/{scenario_id}/reproduce`, `.../diagnose`,
   `.../propose-fix`, `.../verify`, `.../approve` (admin-gated),
   `.../rerun`.
5. Structured evidence persistence (symptom/reproduction/hypothesis/
   root-cause/diff/tests/approval/commit/deploy/rerun/learning) — reusing
   the existing event ledger (`agent/event_ledger.py`), not a new store.

## Why option (b) is recommended over re-breaking fixed code

Re-introducing a real bug behind a flag, even carefully isolated, adds
permanent surface area to review and a standing risk that the flag leaks
scope (e.g., a future refactor of `ContractPlanService` accidentally
makes the flag reachable more broadly). Replaying **real, already-
captured evidence** of a historical incident — the actual pre-fix test
failure, the actual production log line, the actual before/after query
result — proves the same diagnostic story with zero standing risk to the
current, correct production code. This is the same judgment call this
project already made when a real historical `DEPLOYMENT_STATUS_UNKNOWN`
run (`trainer-e8ed222c`) was preserved as evidence rather than
re-triggered.

## Next action

Build Scenario A first (smallest, most self-contained, already has 100%
of its real evidence and fix committed) using option (b): a read-only
`/triage` walkthrough that shows the real before/after plan-history
query results and the real diff, with the human-approval-gate UI treatment
from `docs/UI_UX_DESIGN_SYSTEM.md`, before attempting any scenario that
needs live re-execution.
