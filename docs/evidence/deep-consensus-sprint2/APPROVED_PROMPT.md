# ================================================================
# DEEP CONSENSUS — SPRINT 2
# FINAL OWNER-APPROVED EXECUTION PROMPT
# ================================================================
#
# Owner: Karthik
# Final prompt author: ChatGPT
# Review inputs incorporated: Grok + Claude
#
# OWNER APPROVALS ALREADY GIVEN
# -----------------------------
# Maximum REAL provider calls this sprint: 30
# Maximum KNOWN provider spend this sprint: USD $2.00
#
# IMPORTANT:
# Sprint 2 is a SMALL CAPPED API/CROSS-FAMILY ENGINEERING PROOF.
# It is NOT the future operating/economic model of Deep Consensus.
#
# Future subscription-backed / CLI / zero-marginal-cost transport is
# intentionally deferred to the next sprint.
#
# NO PUSH.
# NO DEPLOY.
# NO TUNNEL.
# NO CHATGPT CONNECTION.
#
# Work autonomously within these constraints.
#
# ================================================================
# PHASE 0 — INSPECT WHAT ALREADY RAN
# ================================================================
#
# Sprint 2 may have been partially started before it was stopped.
#
# BEFORE changing anything:
#
# 1. inspect current branch
# 2. inspect git status
# 3. inspect git diff
# 4. inspect recent commits
# 5. inspect Sprint-2 files already created
# 6. inspect logs / audit files / evidence
# 7. determine whether any REAL provider calls already happened
# 8. determine any known cost already consumed
# 9. determine which tests already ran
#
# Produce a concise CURRENT STATE report before continuing:
#
# CURRENT_BRANCH
# CURRENT_HEAD
# FILES_CHANGED
# COMMITS_ALREADY_CREATED
# SPRINT2_WORK_ALREADY_COMPLETED
# SPRINT2_WORK_PARTIAL
# REAL_CALLS_ALREADY_USED
# KNOWN_COST_ALREADY_USED
# TEST_STATE
#
# Do not ask Owner to remember what happened.
# Derive it from repository/evidence where possible.
#
# Preserve valid completed work.
# Do not redo live calls unnecessarily.
#
# If no Sprint-2 branch exists, create:
#
#   deep-consensus-sprint2
#
# from the final Sprint-1 state.
#
# ================================================================
# PURPOSE OF SPRINT 2
# ================================================================
#
# Sprint 1 proved:
#
# - one MCP tool
# - sealed independent answers
# - cross-review
# - disagreement preservation
# - bounded execution
# - audit evidence
#
# Sprint 2 improves:
#
# 1. TRUE SECOND PROVIDER FAMILY
# 2. PARALLEL SEALED CALLS
# 3. PARALLEL REVIEWS
# 4. CORRECT STATUS SEMANTICS
# 5. CONTRADICTED-CLAIM PROTECTION
# 6. SMALL SELF-ADVOCACY TEST
# 7. TRUTHFUL COST / TIMING EVIDENCE
#
# Do not redesign the product.
#
# ================================================================
# SAFETY / REPOSITORY RULES
# ================================================================
#
# Local commits allowed.
#
# DO NOT:
#
# - push
# - merge
# - deploy
# - modify production
# - expose a public endpoint
# - create a tunnel
# - connect ChatGPT
# - automate consumer browser sessions
# - reuse cookies/tokens from consumer chats
# - use consumer passwords
# - alter existing coding-agent approval/write behavior
# - integrate into Workbench
#
# Deep Consensus remains a separate subsystem.
#
# Existing agent/coding workflow regression tests must stay green.
#
# ================================================================
# SPEND GUARD — OWNER APPROVED
# ================================================================
#
# TOTAL SPRINT ceilings:
#
#   MAX_REAL_PROVIDER_CALLS = 30
#   MAX_KNOWN_SPEND_USD = 2.00
#
# These totals INCLUDE any real calls already made before Phase 0.
#
# Use:
#
#   agent/paid_test_guard.py
#
# or the existing equivalent fail-closed mechanism.
#
# Every live run must go through the guard.
#
# Stop BEFORE launching a call that would violate an authorized ceiling.
#
# If cost is UNKNOWN:
#
# - do not fabricate it
# - call-count ceiling still applies
#
# ================================================================
# SAVE THIS APPROVED PROMPT
# ================================================================
#
# Save this prompt verbatim to:
#
#   docs/evidence/deep-consensus-sprint2/APPROVED_PROMPT.md
#
# Record:
#
# - SHA-256
# - starting commit SHA
# - branch
# - timestamp
#
# ================================================================
# PRESERVE SPRINT-1 EVIDENCE
# ================================================================
#
# Verify/create:
#
#   docs/evidence/deep-consensus-sprint1/
#
# Preserve IF THEY ACTUALLY EXIST:
#
# - approved Sprint-1 prompt
# - Sprint-1 final report
# - relevant audit excerpts
# - real-run evidence
# - MCP Inspector output/failure evidence
# - raw HTTP MCP probe evidence
# - relevant lock/error evidence
#
# If an artifact never existed:
#
#   mark ABSENT
#
# Never recreate historical evidence.
#
# Never invent missing evidence.
#
# ================================================================
# SPRINT-1 FINDINGS
# ================================================================
#
# Create/update:
#
#   docs/evidence/deep-consensus-sprint1/FINDINGS.md
#
# Record the known PostgreSQL CREATE INDEX failure.
#
# The prior governed answer allowed/stated a factual claim equivalent to:
#
#   plain CREATE INDEX prevents concurrent reads and writes
#
# Regression expectation:
#
#   plain PostgreSQL CREATE INDEX allows concurrent reads of the
#   target table while writes are blocked during index construction.
#
# If recording an exact PostgreSQL lock-mode name, only do so when it
# is supported by repository evidence or authoritative documentation.
#
# From existing audit evidence determine:
#
# - which run contained the claim
# - whether before/after truncation fix
# - which exact claim reviewer marked CONTRADICTED
# - whether that claim was the locking claim
#
# If evidence cannot establish a detail:
#
#   UNKNOWN
#
# ================================================================
# 1. SECOND PROVIDER FAMILY
# ================================================================
#
# Slot A remains Anthropic.
#
# Slot B priority is NOW LOCKED:
#
# 1. GEMINI FIRST
#
#    Use Gemini IF:
#    - GEMINI_API_KEY exists
#    - its existing/free-tier API path is immediately usable
#
# 2. OPENAI SECOND
#
#    Use OpenAI only if:
#    - Gemini is unavailable
#    - OPENAI_API_KEY already exists
#    - SDK is already usable
#
# 3. OTHERWISE
#
#    Record:
#
#       BLOCKED_REAL_PROVIDER_CREDENTIAL
#
#    and use a clearly-labelled MOCK for deterministic work.
#
# IMPORTANT:
#
# REAL + MOCK is NOT a successful cross-family real run.
#
# Do not describe it as one.
#
# No third provider family this sprint.
#
# ================================================================
# PROVIDER METADATA
# ================================================================
#
# Every result and audit record must identify:
#
# provider
# provider_family
# exact_model
# is_mock
#
# Also include:
#
# provider_mode:
#   real_real
#   real_mock
#   mock_mock
#
# and:
#
# cross_family_real:
#   true / false
#
# ================================================================
# 2. PARALLEL EXECUTION
# ================================================================
#
# Normal path remains FOUR provider calls.
#
# STAGE 1 — PARALLEL SEALED ANSWERS
#
#   A first answer
#   B first answer
#
# Run concurrently.
#
# Both must complete/store before either review request is constructed.
#
# STAGE 2 — PARALLEL REVIEWS
#
#   A reviews B
#   B reviews A
#
# Run concurrently.
#
# Do not add a fifth "judge" model call.
#
# Do not add a synthesis-model call.
#
# ================================================================
# SEALED-ANSWER INVARIANT
# ================================================================
#
# Prove mechanically:
#
# - A's initial request contains no B answer
# - B's initial request contains no A answer
# - A review cannot be constructed before both initial answers exist
# - B review cannot be constructed before both initial answers exist
#
# Concurrency must not weaken sealing.
#
# ================================================================
# BUDGET RESERVATION BEFORE PARALLEL DISPATCH
# ================================================================
#
# Reserve capacity BEFORE dispatching concurrent calls.
#
# Reserve:
#
# - call count
# - token budget where implemented
# - known spend where calculable
#
# Example:
#
# if only one call remains:
#
#   do NOT launch two concurrent calls.
#
# Add deterministic tests for this.
#
# ================================================================
# DETERMINISTIC AUDIT ORDER
# ================================================================
#
# Network completion order may vary.
#
# Audit ordering must remain logically deterministic:
#
#   A_FIRST
#   B_FIRST
#   A_REVIEW
#   B_REVIEW
#
# Record latency separately.
#
# Test using deliberately reversed completion timing.
#
# ================================================================
# PERFORMANCE MEASUREMENT
# ================================================================
#
# On the same representative question/configuration, measure:
#
#   sequential baseline
#
# versus:
#
#   parallel execution
#
# Report:
#
# sequential_ms
# parallel_ms
# observed_ratio
#
# Do not generalize performance from one sample.
#
# ================================================================
# SECOND REVIEW ROUND
# ================================================================
#
# Normal request should stop after one review round.
#
# Second round permitted ONLY if ALL are true:
#
# 1. material disagreement remains
# 2. elapsed time < 25 seconds
# 3. call budget has room
# 4. token budget has room
# 5. known spend budget has room
# 6. total configured deadline remains realistically achievable
#
# Second-round calls run in parallel.
#
# If conditions fail:
#
#   return UNRESOLVED
#
# Do not chase agreement merely to force convergence.
#
# ================================================================
# 3. STATUS SEMANTICS
# ================================================================
#
# Implement one deterministic mapping.
#
# Valid statuses:
#
#   CONVERGED
#   UNRESOLVED
#   PARTIAL
#   LIMIT_REACHED
#   PROVIDER_ERROR
#
# ================================================================
# CONVERGED — STRICT FINAL RULE
# ================================================================
#
# CONVERGED is allowed ONLY when the FINAL review round returns:
#
#   ACCEPT + ACCEPT
#
# on the EXACT SAME candidate answer.
#
# Use a deterministic normalized text hash.
#
# Both reviewers must have reviewed and accepted the SAME candidate hash.
#
# Example:
#
# Round 1:
#
#   A = ACCEPT
#   B = REVISE
#
# => UNRESOLVED
#
# Same-round ACCEPT + REVISE is NEVER convergence.
#
# A revised answer may become converged only if a later round gives:
#
#   ACCEPT + ACCEPT
#
# on that exact revised candidate hash.
#
# ================================================================
# CONTRADICTED-CLAIM RULE — MANDATORY
# ================================================================
#
# CONVERGED is forbidden if ANY claim marked:
#
#   CONTRADICTED
#
# in ANY review round still materially remains in:
#
#   governed_answer
#
# unless the claim has explicitly been corrected or removed.
#
# Therefore:
#
# if a CONTRADICTED claim remains:
#
#   status = UNRESOLVED
#
# and that claim must be surfaced in:
#
#   dissent
#
# and/or:
#
#   flagged_claims
#
# It must never silently remain inside a "converged" answer.
#
# ================================================================
# UNRESOLVED
# ================================================================
#
# Use UNRESOLVED when:
#
# - substantive REVISE remains
# - DISAGREE remains
# - final candidate hashes differ
# - ACCEPT + REVISE occurs
# - revision has not later received ACCEPT+ACCEPT
# - contradicted claim remains
#
# Disagreement itself is not a system failure.
#
# ================================================================
# PARTIAL
# ================================================================
#
# PARTIAL only when normal completion was prevented by:
#
# - provider failure
# - parse failure
# - truncation
# - missing provider result
#
# while enough useful information survives.
#
# Do NOT use PARTIAL simply because models disagree.
#
# ================================================================
# LIMIT_REACHED
# ================================================================
#
# LIMIT_REACHED only when an ACTUAL configured ceiling caused stopping:
#
# - time
# - token budget
# - provider-call budget
# - spend ceiling
# - max review rounds
#
# ================================================================
# PROVIDER_ERROR
# ================================================================
#
# PROVIDER_ERROR only when a genuine provider failure prevents even a
# useful partial result.
#
# ================================================================
# STOP REASON RULE
# ================================================================
#
# stop_reason:
#
#   bounded_convergence
#
# may ONLY accompany:
#
#   CONVERGED
#
# Never pair it with:
#
# - UNRESOLVED
# - PARTIAL
# - LIMIT_REACHED
# - PROVIDER_ERROR
#
# Invalid status/stop_reason combinations should be impossible by design.
#
# ================================================================
# GOVERNED-ANSWER SELECTION — DETERMINISTIC
# ================================================================
#
# RULE A — TRUE CONVERGENCE
#
# Final:
#
#   ACCEPT + ACCEPT
#
# same hash,
# no surviving CONTRADICTED claim:
#
#   governed_answer = shared accepted candidate
#   status = CONVERGED
#
# ------------------------------------------------
# RULE B — UNACCEPTED REVISION
# ------------------------------------------------
#
# A revision exists but has not later received:
#
#   ACCEPT + ACCEPT
#
# on the same hash:
#
#   governed_answer = slot A current candidate
#   status = UNRESOLVED
#
# preserve:
#
# - revision
# - dissent
# - trace
#
# ------------------------------------------------
# RULE C — DISAGREEMENT
# ------------------------------------------------
#
# DISAGREE remains:
#
#   governed_answer = slot A current candidate
#   status = UNRESOLVED
#
# attach explicit dissent.
#
# ------------------------------------------------
# RULE D — PARTIAL FAILURE
# ------------------------------------------------
#
# Select surviving best available candidate deterministically.
#
# Return:
#
#   PARTIAL
#
# or:
#
#   PROVIDER_ERROR
#
# as appropriate.
#
# ------------------------------------------------
# RULE E — CONTRADICTED CLAIM
# ------------------------------------------------
#
# If governed_answer materially retains a CONTRADICTED claim:
#
#   status = UNRESOLVED
#
# and flag the exact claim.
#
# ================================================================
# CREATE INDEX REGRESSION
# ================================================================
#
# Create ONE fixed deterministic regression case.
#
# Test scenario:
#
# voter A says approximately:
#
#   plain CREATE INDEX blocks reads and writes / ACCESS EXCLUSIVE
#
# voter B marks that locking claim:
#
#   CONTRADICTED
#
# Expected behavior:
#
# 1. contradiction captured
# 2. claim cannot silently survive into CONVERGED
# 3. if it remains in governed_answer:
#
#       status = UNRESOLVED
#
# 4. claim appears explicitly in dissent/flagged_claims
#
# This is ONE regression test, not a general benchmark suite.
#
# ================================================================
# OPTIONAL LIVE CREATE INDEX RUN
# ================================================================
#
# Run at most ONE live cross-family version IF:
#
# - Anthropic is real
# - Gemini/OpenAI second family is real
# - paid guard permits it
#
# Report the outcome truthfully.
#
# If the governed answer is wrong:
#
#   report WRONG
#
# Do not repeatedly tune prompts to manufacture success.
#
# ================================================================
# 4. SELF-ADVOCACY / CONFORMITY HARNESS
# ================================================================
#
# Keep this tiny.
#
# CASE A:
#
#   weak OWN answer
#   strong OTHER answer
#
# Healthy behavior:
#
#   concede/revise where warranted.
#
# CASE B:
#
#   swap slots/providers.
#
# CASE C — INVERSE CONTROL:
#
#   strong OWN answer
#   weak OTHER answer
#
# Healthy behavior:
#
#   should not blindly concede.
#
# Run deterministic mocks first.
#
# Report:
#
# concede_rate
# revise_rate
# inappropriate_self_defense_rate
# inappropriate_concession_rate
# n
#
# Explicitly state:
#
#   MOCK RESULTS TEST THE HARNESS ONLY.
#
# Run ONE small live cross-family pair only if both families are real and
# the spend guard permits.
#
# ================================================================
# 5. COST ACCOUNTING
# ================================================================
#
# Cost may only be reported when calculated from:
#
# - exact provider/model
# - actual provider-reported token usage
# - current published price
#
# Record:
#
# - provider
# - model
# - source URL
# - access date
# - input price
# - output price
#
# If any required element is unavailable:
#
#   cost = UNKNOWN
#
# Never estimate or fabricate.
#
# ================================================================
# MCP SURFACE
# ================================================================
#
# Public surface remains EXACTLY ONE tool:
#
#   deep_review
#
# Do not expose internal stages:
#
# - first answer
# - review
# - governor
# - candidate selection
# - convergence
#
# ================================================================
# MCP VERIFICATION
# ================================================================
#
# Prefer MCP Inspector.
#
# Verify:
#
# - initialization
# - exactly one public tool
# - schema
# - valid deep_review call
# - controlled invalid request
#
# If Inspector CLI itself fails for an environmental/tooling reason:
#
# - capture the failure honestly
# - use the established raw MCP protocol probe
# - do not claim Inspector PASS
#
# Report separately:
#
# MCP_PROTOCOL
#
# MCP_INSPECTOR_CLI
#
# ================================================================
# REQUIRED TESTS
# ================================================================
#
# At minimum test:
#
# 1. Phase-0 branch state detection
# 2. provider metadata
# 3. Gemini-first selection
# 4. OpenAI fallback
# 5. BLOCKED_REAL_PROVIDER_CREDENTIAL path
# 6. REAL+MOCK not cross-family real
# 7. sealed first-answer concurrency
# 8. review concurrency
# 9. reviews cannot build before both first answers
# 10. A initial request cannot see B
# 11. B initial request cannot see A
# 12. budget reservation before concurrent dispatch
# 13. deterministic audit order
# 14. ACCEPT+ACCEPT same hash eligible for CONVERGED
# 15. ACCEPT+ACCEPT different hash => UNRESOLVED
# 16. ACCEPT+REVISE => UNRESOLVED
# 17. DISAGREE => UNRESOLVED
# 18. revised answer accepted only once => UNRESOLVED
# 19. revised answer accepted by both later => CONVERGED candidate
# 20. parse failure => PARTIAL
# 21. provider failure handling
# 22. genuine time limit => LIMIT_REACHED
# 23. genuine call limit => LIMIT_REACHED
# 24. genuine spend limit => LIMIT_REACHED
# 25. bounded_convergence only with CONVERGED
# 26. remaining CONTRADICTED claim forbids CONVERGED
# 27. contradicted claim surfaced explicitly
# 28. CREATE INDEX regression
# 29. weak-own / strong-other harness
# 30. swapped-slot harness
# 31. strong-own / weak-other inverse control
# 32. 30-real-call guard
# 33. $2 known-spend guard
# 34. Sprint-1 Deep Consensus tests remain green
# 35. existing agent/coding-agent tests remain green
#
# ================================================================
# EXPLICITLY OUT OF SCOPE
# ================================================================
#
# DO NOT BUILD:
#
# - subscription-backed CLI transport
# - claude -p transport
# - codex exec transport
# - Sign in with ChatGPT
# - human relay
# - local Ollama/open model transport
# - third provider
# - benchmarks
# - model rankings
# - domain expert weighting
# - learned weights
# - outcome feedback flywheel
# - policy UI
# - ChatGPT tunnel
# - public plugin
# - product website
# - download flow
# - pricing
# - billing
# - sales funnel
# - database
# - LangGraph
# - OAuth
# - SSO/RBAC
# - mobile UI
# - production deployment
#
# These belong to later product sprints.
#
# ================================================================
# DONE CONDITION
# ================================================================
#
# Sprint 2 is done when:
#
# 1. Existing partial Sprint-2 state was inspected first.
#
# 2. Valid prior work was preserved.
#
# 3. Sprint-1 evidence is honestly preserved.
#
# 4. Anthropic + Gemini REAL cross-family succeeds,
#
#    OR, if Gemini unavailable:
#
#       Anthropic + OpenAI succeeds,
#
#    OR, if neither second credential exists:
#
#       BLOCKED_REAL_PROVIDER_CREDENTIAL
#
#       is recorded and deterministic work finishes.
#
# 5. Parallel sealed answers work.
#
# 6. Parallel reviews work.
#
# 7. Budget reservation works.
#
# 8. Audit order is deterministic.
#
# 9. Status semantics are exhaustive.
#
# 10. CONVERGED requires final ACCEPT+ACCEPT same hash.
#
# 11. Remaining CONTRADICTED claim forbids CONVERGED.
#
# 12. CREATE INDEX regression passes.
#
# 13. Self-advocacy harness works.
#
# 14. Cost is factual or UNKNOWN.
#
# 15. MCP protocol invocation works.
#
# 16. Existing agent tests remain green.
#
# 17. Real calls <= 30 total.
#
# 18. Known spend <= $2 total.
#
# 19. NO PUSH.
#
# 20. NO DEPLOY.
#
# ================================================================
# FINAL REPORT
# ================================================================
#
# Print exactly:
#
# SPRINT 2 STATUS
# PASS / PARTIAL / BLOCKED
#
# PHASE 0 — PREEXISTING STATE
# branch:
# starting head:
# existing sprint2 commits:
# existing changed files:
# work already completed:
# work already partial:
# real calls already consumed:
# known cost already consumed:
#
# PROVIDER A
# provider:
# family:
# model:
# real/mock:
#
# PROVIDER B
# provider:
# family:
# model:
# real/mock:
#
# SLOT-B SELECTION
# GEMINI / OPENAI / MOCK
#
# CROSS-FAMILY REAL RUN
# YES / NO
#
# BLOCKED_REAL_PROVIDER_CREDENTIAL
# YES / NO
#
# SEQUENTIAL BASELINE
# <ms>
#
# PARALLEL RESULT
# <ms>
#
# OBSERVED RATIO
# <ratio>
#
# ROUND 2 REACHABLE UNDER REAL TIMING
# YES / NO
# calculation:
#
# PROVIDER CALLS
# <total used including any pre-stop calls> / 30
#
# KNOWN PROVIDER SPEND
# <total including any pre-stop known spend> / $2.00
# or UNKNOWN
#
# STATUS SEMANTICS
# PASS / FAIL
#
# FINAL SAME-HASH ACCEPT RULE
# PASS / FAIL
#
# CONTRADICTED-CLAIM GUARD
# PASS / FAIL
#
# CREATE INDEX MOCK REGRESSION
# PASS / FAIL
#
# CREATE INDEX LIVE RESULT
# RESULT / NOT RUN
#
# SELF-ADVOCACY MOCK EVAL
# n:
# concede_rate:
# revise_rate:
# inappropriate_self_defense_rate:
# inappropriate_concession_rate:
# NOTE: HARNESS ONLY
#
# SELF-ADVOCACY LIVE EVAL
# RESULT / NOT RUN
#
# MCP PROTOCOL
# PASS / FAIL
#
# MCP INSPECTOR CLI
# PASS / FAIL / ENVIRONMENTAL_FAILURE
#
# DEEP CONSENSUS TESTS
# <command + result>
#
# EXISTING AGENT TESTS
# <command + result>
#
# SPRINT-1 EVIDENCE
# <paths>
#
# SPRINT-1 FINDINGS
# example run:
# truncation state:
# contradicted claim:
# exact locking finding:
# Gemini Sprint-1 reason:
#
# MODEL / SYSTEM FAILURES FOUND
# <failure>
# <how detected>
# <change made>
#
# KNOWN LIMITATIONS
# <list>
#
# NEXT TECHNICAL BLOCKER
# <one item only>
#
# BRANCH
# deep-consensus-sprint2
#
# PUSHED
# NO
#
# DEPLOYED
# NO
#
# ================================================================
# EXECUTE NOW
# ================================================================
#
# Start with Phase 0.
#
# Do not ask Owner routine questions.
#
# Owner has already approved:
#
#   30 REAL provider calls maximum
#   $2.00 KNOWN spend maximum
#
# Prefer:
#
#   Gemini free-tier key first for Slot B.
#
# Then:
#
#   existing OpenAI API key.
#
# Otherwise:
#
#   BLOCKED_REAL_PROVIDER_CREDENTIAL + labelled MOCK.
#
# Preserve work already performed.
#
# Do not push.
# Do not deploy.
