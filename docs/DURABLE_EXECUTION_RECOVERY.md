# Durable Execution / Recovery

Base Architecture V3 Section 12. Audits real side-effecting stages
against the directive's named failure cases, with one new real drill
exercised this session and honest references to already-existing
evidence for the rest — not a re-verification of everything from
scratch.

## Real drill exercised this session: dependency unavailable mid-action

**Scenario**: the durable event ledger (Postgres) is unreachable for the
*entire duration* of a Triage candidate promotion (the real business
action: admin login → approve → clone → write candidate → commit → push
→ trigger deploy → wait for deployment → re-run reproduction).

**Test**: `agent/test_triage_promotion.py::
test_recovery_drill_promotion_still_succeeds_when_the_durable_ledger_is_unreachable` —
mocks `event_ledger._insert` to raise for the whole promotion, using a
real disposable local git origin (not a mock of git itself).

**Real result**: the promotion **genuinely succeeds** — real commit, real
push to the dedicated branch, real deployment confirmation — completely
independent of the ledger's health. The `candidate_promoted` provenance
event (Section 11) is durably spooled to a local file rather than lost,
with the exact real `candidate_hash` intact, recoverable by a later
`event_ledger.sync_spool()` once the database returns. This proves
`event_ledger.record_event()`'s documented "never raises to the caller"
guarantee holds through this specific real call site, not just in
`event_ledger`'s own isolated unit tests.

## Other named cases — status per existing evidence

| Case | Real coverage | Source |
|---|---|---|
| Duplicate retry (same event written twice) | `ON CONFLICT DO NOTHING` on `event_id`, real Postgres constraint, proven via `test_c_duplicate_insert_of_the_same_event_id_does_not_duplicate` against the live database | `agent/test_event_ledger.py` (pre-existing, independently re-run this session as part of the 30/30 full suite check in Section 11's commit) |
| Network timeout while a deployment later actually succeeds | `agent/demo_execution.py::wait_for_new_deployment()` — real HTTP polling against the live production URL is the primary evidence, Railway CLI status only corroborates; a genuine `DEPLOYMENT_STATUS_UNKNOWN` outcome exists rather than silently folding an ambiguous result into `FAILED` | Pre-existing (`docs/EVIDENCE_AUTHORITY_MODEL.md` cites this same mechanism) |
| Process dies after Git commit, before push/deploy | The isolated-workspace pattern (`demo_execution.create_isolated_workspace`) means a crashed process's partial state lives only in a disposable temp directory — nothing durable is left half-committed to the real repository; recovery is "retry the whole operation fresh," not "resume a partial one" | Architectural property of the isolated-workspace design, not a dedicated crash-simulation test |
| Process dies during deployment | Recovery relies on `wait_for_new_deployment()`'s real, independent check of Railway's actual deployment state on the *next* attempt — since deployment identity is timestamp-verified (AEQ-009's fix) rather than assumed from the dead process's own state, a fresh check correctly discovers whatever Railway's real state actually is | Pre-existing (AEQ-009, `docs/ESCAPED_DEFECT_COMPILER.md`) |
| QA/evaluator unavailable | Not applicable to the Triage promotion path specifically (no QA-evaluator gate sits between approval and promotion in this pipeline) — the closest analogous real property is Section 11's drill above (a downstream dependency being unreachable doesn't block the real action) | This session (Section 11/12 drill) |

## Honest gap

No test simulates an actual process **crash mid-git-operation** (e.g.,
killed between `commit_change()` succeeding and `push_change()` starting)
against a real subprocess — the isolated-workspace design's architectural
property (see table above) is real and load-bearing, but has not been
verified by an actual kill-signal drill this session. A good candidate
for a dedicated future session, given the tooling (real local git origin,
already used throughout `agent/test_demo_execution.py` and
`agent/test_triage_promotion.py`) already exists to build it on.
