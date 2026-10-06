# Security matrix: controls tested against attacks (BL-121, Sprint 27, SI audit BK-23)

Which implemented security controls are actually exercised by a real test,
against which real attack, with a link to that test — and which cells are
honestly empty. Compiled by reading real code and real tests in `agent/`
and `app/` (Explore agent, 2026-10-06); every row below was confirmed
against a real file, not assumed from a control's existence.

| # | Attack | Real control (file:function) | Real test(s) | What the test actually proves |
|---|---|---|---|---|
| 1 | Path traversal | `agent/tools.py::_resolve_safe_path` | `agent/test_tools.py::ResolveSafePathTestCase.test_path_traversal_is_rejected`, `.test_absolute_path_is_rejected`, `.test_blocked_directory_is_rejected`, `.test_blocked_extension_is_rejected`, `.test_foreign_drive_letter_path_gives_an_honest_drive_specific_error`; `ReadFileSecurityTestCase.test_read_file_rejects_traversal`; `ListRepositoryFilesTestCase.test_list_repository_files_rejects_traversal`; `SearchCodeTestCase.test_search_code_rejects_traversal_glob` | Rejects `../`, absolute paths, `.git/`, blocked extensions, and Windows drive-letter tricks, across every public caller (read, list, search) |
| 2 | Prompt injection | **None found.** `agent/ask_codebase.py` only *names* prompt injection as a risk in a comment; `agent/standing_interview.py`'s keyword regex is routing/leak detection, not adversarial-input defense | **None found** | No real test exists for prompt injection specifically. The closest tested defenses are the leak/voice gates (row 3), which constrain *output*, not adversarial *input* handling |
| 3 | Secret/credential leak | `agent/tools.py::redact_secrets`; `agent/secret_scan.py` (pre-push CLI scanner); `agent/standing_interview.py`'s leak gate | `agent/test_tools.py::ReadFileSecurityTestCase.test_read_file_redacts_an_obvious_secret_assignment`, `.test_read_file_redacts_a_real_secret_literal_in_actual_file_content`, `.test_secret_named_file_that_already_exists_is_rejected`, `.test_secret_named_file_that_does_not_exist_yet_is_still_rejected`; `SearchCodeTestCase.test_search_code_redacts_secrets_in_matched_snippet`; `agent/test_standing_interview.py::LeakGuardTestCase` (4 tests incl. `test_no_pantheon_name_can_reach_the_interviewer`) and `LeakRetryTestCase` (3 tests) | Secret-shaped strings and internal-document/filename/codename leaks are redacted/refused even in not-yet-existing files and model-generated answers, with a bounded one-retry policy |
| 4 | SQL injection | Python: `agent/event_ledger.py` uses parameterized queries (`%s` placeholders) exclusively. Java: an admin-listing sort-field allowlist rather than raw field interpolation | **Python: none.** Java: `AdminCustomerScaleIntegrationTest.listAll_rejectsAnUnknownSortField_fallingBackToIdRatherThanFailingOrInjecting` sends `sortBy=email); DROP TABLE customer;--` and asserts a safe fallback | The Java test is a real, explicit SQLi-shaped payload test. The Python side's parameterization is real but **untested against an adversarial payload** — safety by construction, not by proof |
| 5 | Auth/authz bypass | Python: `agent/owner_auth.py::is_owner`/`require_owner`. Java: Spring Security JWT resource-server config | `agent/test_owner_auth_and_triage_budget.py::OwnerTokenUnitTestCase` (3 tests incl. fail-closed on unset/blank token) and `OwnerOnlyRoutesTestCase` (3 tests). Java: `SecurityIntegrationTest` -- 401 on no/malformed/wrong-signature/expired/wrong-issuer/wrong-audience token, 403 on missing scope | Fail-closed on missing/blank/garbage tokens; rejects malformed/expired/wrong-signature/wrong-issuer/wrong-audience JWTs; enforces scope-based (RBAC) 403s even with a structurally valid token |
| 6 | Command injection | `agent/build_tools.py::run_maven` (argv-list `subprocess.run`, never `shell=True`); `agent/execution_tools.py`'s controlled-compile/test tools take zero free-form input | `agent/test_build_tools.py::test_shell_injection_attempt_rejected_as_unknown_goal`, `.test_subprocess_never_uses_shell_true`; `agent/test_execution_tools.py::test_no_tool_accepts_an_arbitrary_command_argument` | Shell-metacharacter payloads are rejected pre-execution; no model-facing tool schema accepts a free-form command string |
| 7 | SSRF | **None found.** Every outbound call in `agent/` targets a hardcoded/internal URL; no model-callable tool schema takes a `url` parameter | **None found** | There is no user/model-controlled URL-fetch surface to protect in the first place, so there is honestly nothing to test here yet |
| 8 | DoS / spend limits | Standing Interview's request-budget logic; `agent/owner_auth.py`'s exemption logic | `agent/test_si_budget.py` (6 tests incl. daily cap, cooldown throttle, 429-before-spend, hostile forwarded-header handling); `agent/test_owner_auth_and_triage_budget.py::TriageBudgetTestCase` (3 tests incl. the owner token cannot bypass a zero/disabled budget) | Per-visitor and global daily budget caps, cooldown throttling, refusal before any spend, and no owner-token bypass of a disabled budget |
| 9 | Privilege escalation | `agent/execution_tools.py` -- `approve_edit`/`reject_edit` deliberately absent from `EXECUTION_TOOL_SCHEMAS`/`_EXECUTION_DISPATCH` (AEQ-003) | `agent/test_execution_tools.py::test_approval_not_present_in_tool_schemas_by_exact_name`, `.test_approval_not_reachable_through_dispatch_by_any_name`, `.test_propose_schema_has_no_field_that_could_carry_an_approval_decision`, `.test_model_supplied_approval_field_is_ignored_not_honored` | Exact-name set-membership exclusion of approve/reject from model tool schemas and dispatch table; a spoofed `approved: True` field in tool input is never honored |
| 10 | XSS / output encoding | An `esc()` DOM-escape helper duplicated across `agent/web/*.js` (dashboard, ask-codebase, eval, learn, triage, usage, workbench) | **None found** -- no `.test.js` files exist in this repo | The helper is implemented consistently across every public page's JS but is **entirely unverified by any test** |

## What this matrix says, honestly

**Covered with a real test:** path traversal, secret/credential leak,
auth/authz bypass, command injection, DoS/spend limits, privilege
escalation (rows 1, 3, 5, 6, 8, 9) -- each has a real mechanism and a real
test exercising it with an adversarial-shaped input.

**Real mechanism, no real test:** Python SQL-injection safety (row 4,
Java side is tested) and XSS output encoding (row 10) -- both rely on
"safe by construction" (parameterized queries, a consistent escape
helper) with zero adversarial-input test proving it.

**No real mechanism and no real test:** prompt injection (row 2) and SSRF
(row 7). SSRF is arguably not yet applicable (no user/model-controlled
URL-fetch surface exists to attack); prompt injection is a genuine open
gap given this platform's core premise is LLM-driven tool use.

## Maintaining this matrix

Re-derive by reading the real code and tests again when a new control is
added or a new attack surface opens (e.g. if a model-callable tool ever
gains a `url` parameter, SSRF stops being "not yet applicable" and needs
a real row). This is a point-in-time read (2026-10-06), not a live-
generated artifact.
