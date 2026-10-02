# DEEP CONSENSUS — SPRINT 2
# FINAL CONSOLIDATED EXECUTION PROMPT
# Owner: Karthik
# Reviewed by: ChatGPT + Grok + Claude
# Convergence before execution: 100%
#
# Sprint 1 is CLOSED.
# Do not reopen or broadly refactor Sprint 1.
#
# Owner explicitly authorizes:
#   maximum 30 REAL provider calls total during this sprint
#   maximum $2.00 KNOWN provider spend total during this sprint
#
# Work autonomously.
# NO PUSH.
# NO DEPLOY.
# NO tunnel / ChatGPT connection this sprint.

================================================================================
SPRINT OBJECTIVE
================================================================================

Sprint 2 turns the Sprint-1 Deep Consensus prototype into an honest
cross-family, parallel, status-correct review engine.

Priority order:

1. second provider FAMILY
2. parallel sealed answers + parallel reviews
3. exact deterministic status semantics
4. contradicted-claim protection + CREATE INDEX regression
5. tiny self-advocacy / conformity eval
6. truthful cost accounting

Do these only.

Do NOT expand the product.

================================================================================
BRANCH / SAFETY
================================================================================

Create:

    deep-consensus-sprint2

from the final Sprint-1 branch.

Local commits only.

DO NOT:
- push,
- merge,
- deploy,
- create public endpoints,
- create a tunnel,
- connect ChatGPT,
- build UI,
- automate browser logins,
- reuse consumer subscriptions as API credentials,
- modify the existing coding-agent / Workbench behavior,
- introduce LangGraph,
- add a database,
- add a third provider family.

Existing coding-agent regression tests must stay green.

API credentials come from environment variables only.

Never print/log/store key values.

================================================================================
SPEND AUTHORIZATION — LOCKED
================================================================================

Owner approves:

    MAX_REAL_PROVIDER_CALLS = 30

and:

    MAX_KNOWN_PROVIDER_SPEND_USD = 2.00

Use:

    agent/paid_test_guard.py

or the existing equivalent fail-closed mechanism.

Every live run must be protected.

If known accumulated provider spend would exceed $2.00:

STOP all further real-provider calls.

If provider cost is UNKNOWN:

the 30-call ceiling still applies.

Do not estimate unknown provider costs.

Mocks do not count as real-provider calls.

================================================================================
PHASE 0 — PRESERVE SPRINT-1 EVIDENCE
================================================================================

Do this first and keep it small.

Create/verify:

    docs/evidence/deep-consensus-sprint1/

Preserve the following if they actually exist:

- Sprint-1 APPROVED_PROMPT
- Sprint-1 final report
- relevant audit_log.jsonl excerpts for the real runs
- Inspector/raw HTTP probe output or failure evidence
- any lock/error evidence from Sprint 1

If something never existed:

record:

    ABSENT

Do NOT recreate history.

Create:

    docs/evidence/deep-consensus-sprint1/FINDINGS.md

Record this factual failure:

Sprint 1 produced an example answer concerning PostgreSQL CREATE INDEX that
stated or allowed the claim that plain CREATE INDEX takes ACCESS EXCLUSIVE and
blocks reads/writes.

Ground truth for the fixed regression:

    plain CREATE INDEX takes SHARE lock behavior:
    concurrent reads are allowed;
    writes are blocked while the index is created.

From the audit evidence only, determine:

- which Sprint-1 run produced the example,
- whether it was before/after any truncation fix,
- what exact claim the reviewer marked CONTRADICTED.

If evidence cannot establish a detail:

write:

    UNKNOWN

Do not infer.

Also record, from repo/environment evidence:

why Gemini was not used in Sprint 1:
- key absent?
- SDK absent?
- both?
- unknown?

No guessing.

================================================================================
SAVE THIS SPRINT-2 PROMPT
================================================================================

Create:

    docs/evidence/deep-consensus-sprint2/APPROVED_PROMPT.md

Store this prompt verbatim.

Also record:

- SHA-256 of prompt
- starting commit SHA
- branch
- timestamp

================================================================================
1. SECOND PROVIDER FAMILY
================================================================================

Slot A remains Anthropic.

Slot B must be ONE different provider family.

Selection:

1. OpenAI IF:
   - OPENAI_API_KEY exists,
   - SDK is already installed/immediately usable.

2. Otherwise Gemini IF:
   - GEMINI_API_KEY exists,
   - integration is immediately practical.

3. Otherwise:
   use a clearly labelled MOCK for deterministic work,
   and report:

       BLOCKED_REAL_PROVIDER_CREDENTIAL

Important:

A MOCK is NOT a second provider family.

Do NOT describe REAL+MOCK as cross-family success.

No third slot.

Do not use:
- ChatGPT Plus login
- Claude Max login
- SuperGrok login
- Gemini browser session

as API credentials.

Every result/audit record must explicitly identify:

- provider
- model
- provider family
- real/mock

================================================================================
2. PARALLEL EXECUTION
================================================================================

Sprint 1 was sequential.

Sprint 2 must make the normal 4-call path parallel in two stages.

STAGE 1:

Run sealed first-answer calls concurrently:

    A sealed answer
    B sealed answer

Both MUST complete/store before review requests can be built.

STAGE 2:

Then run cross-reviews concurrently:

    A reviews B
    B reviews A

Happy path remains:

    4 calls

Do not add unnecessary calls.

================================================================================
SEALED-ANSWER INVARIANT
================================================================================

Existing sealed-answer guarantees remain mandatory.

Additionally test:

- Review A cannot be constructed before BOTH first answers exist.
- Review B cannot be constructed before BOTH first answers exist.
- A's first request contains no B response.
- B's first request contains no A response.

Parallelism must not weaken sealing.

================================================================================
BUDGET RESERVATION BEFORE PARALLEL DISPATCH
================================================================================

Because calls now run concurrently:

reserve call/token budget BEFORE dispatch.

Concurrency must never accidentally launch more calls than allowed.

Test this deterministically.

If only one call slot remains:

do not launch two calls and discover the limit afterward.

================================================================================
DETERMINISTIC AUDIT ORDER
================================================================================

Completion order may vary under concurrency.

Audit output must remain deterministic.

Record by logical slot/order:

A first
B first
A review
B review

—not by whichever network call happens to finish first.

Test this.

================================================================================
PERFORMANCE EVIDENCE
================================================================================

Using the same representative question/configuration:

measure:

    sequential baseline wall-clock

vs:

    parallel wall-clock

Record both.

Do not fabricate performance conclusions from one sample.

Report actual values only.

Also determine whether the optional second review round is realistically
reachable under the configured deadline after parallelization.

For every time ceiling, document where the number comes from.

Do not silently invent timeout constants.

================================================================================
3. STATUS SEMANTICS — LOCKED
================================================================================

Implement status determination as ONE deterministic mapping.

Invalid status/stop_reason combinations should be impossible by construction.

Statuses:

    CONVERGED
    UNRESOLVED
    PARTIAL
    LIMIT_REACHED
    PROVIDER_ERROR

================================================================================
CONVERGED — STRICT RULE
================================================================================

CONVERGED is allowed ONLY when the FINAL review round produces:

    ACCEPT + ACCEPT

for the EXACT SAME candidate answer.

Use a deterministic normalized text hash.

Both reviewers must accept the same final answer hash.

Examples:

Round 1:
    ACCEPT + REVISE
=> UNRESOLVED.

If round 2 occurs and both then see the revised candidate and return:

    ACCEPT + ACCEPT

on the same text hash:

=> may become CONVERGED.

Same-round:

    ACCEPT + REVISE

is NEVER CONVERGED.

================================================================================
CONTRADICTED CLAIM OVERRIDE — LOCKED
================================================================================

Even ACCEPT + ACCEPT is insufficient if an unresolved contradicted claim remains.

Rule:

CONVERGED is forbidden if ANY claim marked:

    CONTRADICTED

in ANY review round still appears materially in:

    governed_answer

unless that claim was explicitly corrected/removed.

If a contradicted claim remains:

    status = UNRESOLVED

and the contradicted claim must be surfaced in:

    dissent / flagged_claims

It must NEVER survive silently as ordinary factual prose.

Test this directly.

================================================================================
UNRESOLVED
================================================================================

Return UNRESOLVED when:

- any substantive REVISE remains unaccepted,
- any DISAGREE remains,
- candidate answers differ at final acceptance stage,
- contradicted claim remains,
- review completes but genuine disagreement remains.

Do NOT use PARTIAL just because models disagree.

================================================================================
PARTIAL
================================================================================

PARTIAL is only for situations where completion was prevented by:

- parse failure,
- provider failure,
- truncation,
- missing provider result,

but enough information exists to return something useful.

Disagreement itself is not PARTIAL.

================================================================================
LIMIT_REACHED
================================================================================

Use LIMIT_REACHED only when an ACTUAL configured ceiling caused stopping:

- time,
- token budget,
- provider-call budget,
- spend limit,
- max rounds.

Do not call ordinary bounded disagreement LIMIT_REACHED.

================================================================================
PROVIDER_ERROR
================================================================================

Use PROVIDER_ERROR only for genuine provider-level failure where an appropriate
partial result cannot be formed.

================================================================================
STOP REASON RULE
================================================================================

The stop reason:

    bounded_convergence

may accompany ONLY:

    CONVERGED

Never:

    UNRESOLVED
    PARTIAL
    LIMIT_REACHED
    PROVIDER_ERROR

Test the full status/stop_reason matrix.

================================================================================
DETERMINISTIC GOVERNED-ANSWER SELECTION
================================================================================

Do NOT leave answer selection implicit.

Rule:

A. FINAL ACCEPT + ACCEPT on same hash
   and no unresolved CONTRADICTED claim:

       governed_answer = accepted shared candidate
       status = CONVERGED

B. Round contains a revision, but that revision has NOT subsequently received
   ACCEPT + ACCEPT on the same hash:

       status = UNRESOLVED

If no later validated candidate exists:

       governed_answer = slot A current candidate
       attach dissent

C. DISAGREE remains:

       governed_answer = slot A current candidate
       status = UNRESOLVED
       attach dissent

D. Provider/parse failure:

       select the surviving best available candidate deterministically
       status = PARTIAL or PROVIDER_ERROR as appropriate
       explain missing evidence

E. Any contradicted claim still materially present:

       status = UNRESOLVED
       flag that exact claim

Never silently synthesize a new fifth answer using another model call.

================================================================================
SECOND REVIEW ROUND
================================================================================

Default happy path remains ONE review round / four calls.

A second cross-review round is allowed ONLY if ALL are true:

1. meaningful unresolved disagreement remains,
2. elapsed time < 25 seconds,
3. provider-call budget has room,
4. token budget has room,
5. known spend budget has room,
6. total time ceiling can still realistically be respected.

Second-round calls also run concurrently.

Never chase convergence merely to reach ACCEPT+ACCEPT.

If round 2 cannot run:

return UNRESOLVED honestly.

================================================================================
CREATE INDEX REGRESSION — REQUIRED
================================================================================

Create ONE fixed deterministic regression case.

Question must concern PostgreSQL plain CREATE INDEX locking.

Ground truth fixture:

    Plain CREATE INDEX permits concurrent reads but blocks writes against the
    target table while index creation proceeds.

Construct mock inputs where:

- one voter says ACCESS EXCLUSIVE / reads blocked,
- the other reviewer marks that claim CONTRADICTED.

Test must prove:

1. the contradicted claim is detected,
2. it cannot silently survive into a CONVERGED governed answer,
3. if it remains in governed_answer:
       status = UNRESOLVED
4. the exact claim is surfaced in dissent/flagged claims.

This is a regression test, NOT a benchmark.

================================================================================
OPTIONAL ONE LIVE INDEX CASE
================================================================================

One live cross-family run of this regression question is allowed IF:

- second real provider exists,
- spend/call budget allows it.

Record the result truthfully.

If the final answer is wrong:

say it is wrong.

Do not tune the test to produce a success.

================================================================================
4. SELF-ADVOCACY / CONFORMITY EVAL — SMALL ONLY
================================================================================

Build a tiny eval harness.

Case 1:
    reviewer has intentionally weak OWN answer
    and sees strong OTHER answer

Expected healthy behavior:
    concede/revise appropriately.

Case 2:
    swap provider/slot position.

Case 3 — inverse control:
    reviewer has strong OWN answer
    and sees weak OTHER answer.

Expected:
    it should not blindly concede.

Run MOCK first.

Report:

    concede_rate
    revise_rate
    inappropriate_self_defense_rate
    inappropriate_concession_rate
    n

Mocks test the HARNESS only.

The report must explicitly say:

    mock results do not measure real model behavior.

Run ONE live cross-family pair only if both real providers already exist and the
Owner-approved spend ceiling permits it.

Do not use philosophical labels.

Do not call the behavior "dharmic".

================================================================================
5. COST ACCOUNTING
================================================================================

Provider price is allowed only if derived from a CURRENT PUBLISHED rate.

If using a published provider price, record:

- provider
- model
- source URL
- access date
- unit price used

Then compute from actual reported token counts.

If:
- provider does not return usage,
- model identity is uncertain,
- published rate cannot be verified,

return:

    cost = UNKNOWN

Do not estimate.

Do not infer from a similarly named model.

================================================================================
PAID GUARD
================================================================================

All live test/eval paths must pass through:

    agent/paid_test_guard.py

or equivalent existing fail-closed protection.

Enforce:

    calls_used < 30

and:

    known_spend <= $2.00

If either ceiling would be exceeded:

stop BEFORE provider construction/invocation.

================================================================================
MCP / INSPECTOR
================================================================================

Do not change the public MCP surface.

Exactly ONE tool remains:

    deep_review

MCP Inspector or the already-established raw HTTP MCP probe must successfully
invoke it.

If the Inspector CLI itself crashes for environmental reasons exactly as seen
previously:

use the raw protocol probe,
capture the failure evidence,
and do not misreport Inspector PASS.

Report separately:

    MCP protocol PASS/FAIL
    Inspector CLI PASS/FAIL

================================================================================
TEST REQUIREMENTS
================================================================================

Add deterministic tests for at least:

1. second-family provider metadata
2. REAL+MOCK never described as cross-family
3. sealed first calls run concurrently
4. reviews run concurrently
5. review requests cannot build before both first answers exist
6. budget reserved before concurrent dispatch
7. deterministic audit ordering despite completion-order differences
8. ACCEPT+ACCEPT same hash => CONVERGED
9. ACCEPT+ACCEPT different hash => UNRESOLVED
10. ACCEPT+REVISE => UNRESOLVED
11. DISAGREE => UNRESOLVED
12. parse failure => PARTIAL
13. actual time ceiling => LIMIT_REACHED
14. bounded_convergence only with CONVERGED
15. contradicted claim remaining forbids CONVERGED
16. contradicted claim is surfaced
17. CREATE INDEX regression
18. self-advocacy weak-own/strong-other
19. inverse strong-own/weak-other
20. paid guard respects 30-call ceiling
21. paid guard respects $2-known-spend ceiling
22. existing Sprint-1 tests remain green
23. existing coding-agent regression suite remains green

================================================================================
DO NOT BUILD THIS SPRINT
================================================================================

Do not build:

- general benchmark suite
- public benchmark report
- expert/domain weighting
- outcome feedback flywheel
- policy-profile UI
- ChatGPT tunnel
- ChatGPT plugin connection
- third provider
- consumer UI
- side panel
- database
- LangGraph
- OAuth
- SSO/RBAC
- billing
- production deployment
- public plugin submission
- Scrum-of-AI workflow
- philosophical docs
- new model-ranking framework

================================================================================
DONE CONDITION
================================================================================

Sprint 2 is complete when:

- Sprint-1 evidence package is preserved honestly,
- Anthropic + second real provider family succeeds,

OR:

- second-family credential is genuinely unavailable and result is explicitly:

      BLOCKED_REAL_PROVIDER_CREDENTIAL

  while all mock/deterministic work completes,

AND:

- parallel sealed calls are proven,
- parallel reviews are proven,
- audit ordering remains deterministic,
- status semantics are exhaustive,
- final ACCEPT+ACCEPT same-hash rule is enforced,
- contradicted claim can never silently converge,
- CREATE INDEX regression passes,
- self-advocacy harness passes deterministic tests,
- provider costing is real or UNKNOWN,
- MCP protocol invocation passes,
- Deep Consensus tests are green,
- existing coding-agent tests remain green.

A missing second-family API key does NOT block all other Sprint-2 work.

================================================================================
FINAL REPORT
================================================================================

Print:

SPRINT 2 STATUS
PASS / PARTIAL / BLOCKED

PROVIDER A
provider:
family:
model:
real/mock:

PROVIDER B
provider:
family:
model:
real/mock:

CROSS-FAMILY REAL RUN
YES / NO

BLOCKED_REAL_PROVIDER_CREDENTIAL
YES / NO

SEQUENTIAL BASELINE
<ms>

PARALLEL RESULT
<ms>

PARALLEL SPEEDUP
<actual ratio, no marketing conclusion>

ROUND 2 REACHABLE UNDER REAL TIMING
YES / NO
<show calculation>

PROVIDER CALLS
used / 30

KNOWN PROVIDER SPEND
$X / $2.00
or UNKNOWN

STATUS SEMANTICS TESTS
<result>

FINAL-HASH RULE
<result>

CONTRADICTED-CLAIM GUARD
<result>

CREATE INDEX MOCK REGRESSION
PASS / FAIL

CREATE INDEX LIVE RESULT
<answer / NOT RUN>

SELF-ADVOCACY MOCK EVAL
n:
concede_rate:
revise_rate:
inappropriate_self_defense_rate:
inappropriate_concession_rate:
NOTE: HARNESS ONLY

SELF-ADVOCACY LIVE EVAL
<results / NOT RUN>

MCP PROTOCOL
PASS / FAIL

MCP INSPECTOR CLI
PASS / FAIL / ENVIRONMENTAL FAILURE

DEEP CONSENSUS TESTS
<counts/results>

EXISTING AGENT TESTS
<counts/results>

SPRINT-1 EVIDENCE
<paths + findings>

MODEL MISTAKES FOUND DURING SPRINT
<list + how tests/evidence caught them>

KNOWN LIMITATIONS
<list>

NEXT BLOCKER
<single most important next item>

BRANCH
deep-consensus-sprint2

PUSHED
NO

DEPLOYED
NO

================================================================================
EXECUTE
================================================================================

Start now.

Do not ask routine questions.

Owner has already approved:

    30 real calls maximum
    $2.00 maximum known provider spend

If a second provider key is missing, record it honestly and continue all
deterministic/mock Sprint-2 work.

Do not push.
Do not deploy.
