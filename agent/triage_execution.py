"""
Incident Triage & Repair Lab -- Scenario A execution.

Server-to-server orchestration only (never a direct browser->Java-app
call, so there is no CORS surface to manage): this module calls the real
Customer App's /internal/triage/scenario-a/* endpoints (see
app/src/main/java/com/example/customer/triage/), runs a real single-shot
Claude diagnosis call over real evidence, retrieves the real historical
fix diff via `git show`, and runs the real focused regression test.

Nothing here is scripted/fabricated: reset/reproduce/approve genuinely
mutate real database rows in the Customer App (scoped to a dedicated
synthetic customer -- see the Java service's own isolation contract);
diagnose() makes a real Anthropic API call when a key is configured, and
honestly reports when one isn't (mirrors agent/backend_planning.py's
analyze_with_llm doing the same for the ACT-008 pipeline); the patch diff
is the real `git show` output for the real commit that fixed this bug;
verify_fix() runs the real Maven test process.
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request

import tools
import environment_preflight

CUSTOMER_APP_BASE = "https://agentic-delivery-customer-app-production.up.railway.app"
APP_DIR = tools.REPO_ROOT / "app"
MVNW = APP_DIR / ("mvnw.cmd" if os.name == "nt" else "mvnw")
FIX_COMMIT = "2155a8a"
FIX_FILE = "app/src/main/java/com/example/customer/service/ContractPlanService.java"

DIAGNOSIS_SYSTEM_PROMPT = """You are assisting a senior backend engineer diagnosing a real production
defect in a Spring Boot application. You will be given: (1) the real
resulting database state from reproducing the defect, (2) a real excerpt
of the defective method's source, (3) the scenario's business context.

Respond with ONLY a JSON object (no markdown fences), with exactly these
keys: "hypothesis" (one sentence, what you think is wrong), "root_cause"
(2-3 sentences, the precise mechanical reason), "affected_component"
(the class/method name), "confidence" (one of: HIGH, MEDIUM, LOW).
Be concise and technically precise. Do not guess beyond the evidence
given."""


class TriageExecutionError(Exception):
    """Raised for any safely-reportable failure in this module. Never
    crashes the caller with a raw stack trace from a subprocess/network
    call."""


def _request(method: str, path: str, token: str | None = None, body: dict | None = None, timeout_s: float = 15.0) -> dict:
    url = CUSTOMER_APP_BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else (b"" if method == "POST" else None)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise TriageExecutionError(f"{method} {path} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e
    except urllib.error.URLError as e:
        raise TriageExecutionError(f"{method} {path} -> unreachable: {e.reason}") from e


def reset_scenario() -> dict:
    return _request("POST", "/internal/triage/scenario-a/reset")


def reproduce_scenario() -> dict:
    return _request("POST", "/internal/triage/scenario-a/reproduce")


def get_state() -> dict:
    return _request("GET", "/internal/triage/scenario-a/state")


class ApprovalAuthError(TriageExecutionError):
    """Raised specifically for a real 401/403 from the admin-login or
    approve step, so the web layer can show 'invalid admin credentials'
    rather than a generic error."""


def approve_scenario(admin_username: str, admin_password: str) -> dict:
    """Real login as the given ADMIN persona (server-to-server, against
    the Customer App's actual /auth/login -- genuine BCrypt/enabled-state
    verification, not a shortcut), then the real admin-gated approve
    call. Mirrors this app's own login UX (admin1/admin2, the public
    demo password) -- this is the scenario's one HUMAN APPROVAL REQUIRED
    action; the caller must supply real, valid admin credentials."""
    try:
        login = _request("POST", "/auth/login", body={"username": admin_username, "password": admin_password})
    except TriageExecutionError as e:
        raise ApprovalAuthError(f"admin login failed: {e}") from e
    token = login.get("accessToken")
    if not token:
        raise ApprovalAuthError("login succeeded but no accessToken was returned")
    try:
        return _request("POST", "/internal/triage/scenario-a/approve", token=token)
    except TriageExecutionError as e:
        raise ApprovalAuthError(f"approve rejected: {e}") from e


# The real pre-fix method body (see commit 2155a8a's parent), preserved
# here as a literal string purely as diagnosis EVIDENCE shown to the
# model and the UI -- never executed. The actual isolated replay of this
# logic lives in the Java app's own TriageScenarioAService.enrollBuggy().
DEFECTIVE_SOURCE_EXCERPT = """@Transactional
public ContractPlan enroll(Long customerId, ContractPlanEnrollRequest request) {
    customerService.getById(customerId);

    contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
            .ifPresent(existing -> {
                existing.cancel(request.effectiveStartDate());
                contractPlanRepository.saveAndFlush(existing);
            });

    ContractPlan newPlan = new ContractPlan(
            customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
    return contractPlanRepository.save(newPlan);
}
// NOTE: no check anywhere for whether `request` duplicates the terms of
// the plan already active -- every call unconditionally cancels+creates."""

# The REAL, complete pre-fix file (see commit 2155a8a's parent,
# `git show 2155a8a~1:<FIX_FILE>` -- a literal, byte-for-byte copy, not
# reconstructed) -- this is what a candidate-patch-generation call is
# given as "the current defective file" and asked to correct in full,
# never just told the one-line answer.
_BUGGY_FULL_FILE = """package com.example.customer.service;

import com.example.customer.dto.ContractPlanEnrollRequest;
import com.example.customer.model.ContractPlan;
import com.example.customer.model.ContractPlanStatus;
import com.example.customer.repository.ContractPlanRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.NoSuchElementException;

/**
 * BUSINESS REQUIREMENT: a customer has at most one ACTIVE energy plan at a
 * time. Enrolling in a new plan must not silently leave two plans marked
 * ACTIVE (a real data-integrity bug class this test suite specifically
 * checks for) — the prior active plan is cancelled, end-dated on the new
 * plan's start date, and kept (never deleted) so plan history is queryable.
 */
@Service
public class ContractPlanService {

    static final String NO_ACTIVE_PLAN_MESSAGE = "No active contract plan found for customer";

    private final ContractPlanRepository contractPlanRepository;
    private final CustomerService customerService;

    public ContractPlanService(ContractPlanRepository contractPlanRepository, CustomerService customerService) {
        this.contractPlanRepository = contractPlanRepository;
        this.customerService = customerService;
    }

    public ContractPlan getActivePlan(Long customerId) {
        return contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .orElseThrow(() -> new NoSuchElementException(NO_ACTIVE_PLAN_MESSAGE + ": " + customerId));
    }

    @Transactional
    public ContractPlan enroll(Long customerId, ContractPlanEnrollRequest request) {
        customerService.getById(customerId); // 404s if the customer itself does not exist

        // REAL BUG found only by a genuine Postgres integration test (H2's
        // ddl-auto schema has no equivalent constraint to violate, so this
        // was invisible there): Hibernate's default flush ORDER executes
        // all pending INSERTs before any pending UPDATEs in a single
        // transaction flush, regardless of the order save() was called in
        // Java code. Using plain save() here let the new plan's INSERT
        // reach Postgres before the old plan's cancellation UPDATE did --
        // for one instant, two ACTIVE rows existed for the same customer,
        // which uq_contract_plan_one_active_per_customer (a real,
        // immediate, non-deferred Postgres constraint) correctly rejected
        // with a 500. saveAndFlush() forces the cancellation to reach the
        // database BEFORE the new row is ever inserted, closing the gap.
        contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
                .ifPresent(existing -> {
                    existing.cancel(request.effectiveStartDate());
                    contractPlanRepository.saveAndFlush(existing);
                });

        ContractPlan newPlan = new ContractPlan(
                customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
        return contractPlanRepository.save(newPlan);
    }
}
"""

CANDIDATE_PATCH_SYSTEM_PROMPT = """You are a senior backend engineer fixing a real defect in a Spring Boot
service, given real evidence of the defect (not told the answer).

You will be given the CURRENT (defective) complete source of one Java
file, plus real database evidence showing the defect (duplicate rows
created for what should be a single business action).

Write the COMPLETE, corrected version of this ONE file that fixes the
defect while preserving existing behavior, comments, and style. Do not
change public method signatures. Do not add unrelated functionality.

Respond with ONLY the complete corrected file content -- no markdown
fences, no explanation before or after."""


def generate_candidate_patch(reproduction_result: dict, api_key: str | None = None, create_fn=None) -> dict:
    """A SECOND real, on-demand Claude call (distinct from diagnose()):
    asks the model to write the actual fix, given the real defective
    file and real evidence -- never the historical answer. Returns the
    model's proposed complete file content, to be applied and verified
    in an isolated workspace by apply_and_verify_candidate() below,
    never written to the real repository directly."""
    if create_fn is None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {"generated": False, "candidate_source": None,
                    "explanation": "ANTHROPIC_API_KEY not set -- cannot generate a live candidate patch"}
        from anthropic import Anthropic
        create_fn = Anthropic(api_key=api_key).messages.create

    user_message = (
        f"Real database evidence after submitting the identical enrollment request twice:\n"
        f"{json.dumps(reproduction_result, indent=2)}\n\n"
        f"Current (defective) file content ({FIX_FILE}):\n{_BUGGY_FULL_FILE}"
    )
    response = create_fn(
        model="claude-sonnet-5", max_tokens=2048,
        system=CANDIDATE_PATCH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    usage = getattr(response, "usage", None)
    if usage is not None:
        import metrics
        metrics.record_model_usage(
            provider="anthropic", model="claude-sonnet-5",
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", None),
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None),
        )
    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    candidate_source = stripped.strip() + "\n"
    return {"generated": True, "candidate_source": candidate_source, "target_file": FIX_FILE}


def apply_and_verify_candidate(candidate_source: str) -> dict:
    """Applies the AI-generated candidate file content in an ISOLATED
    temp copy of app/ -- never the real repository -- computes the real
    diff against the actual pre-fix baseline the model was shown (via
    Python's own difflib, not `git apply`, so this never depends on the
    running environment's git history -- see AEQ-020), and compiles it
    there. Always cleans up the temp workspace, success or failure."""
    import difflib
    import shutil
    import tempfile
    from pathlib import Path

    preflight = environment_preflight.check_java_toolchain()
    if preflight["status"] != "ENVIRONMENT_VALID":
        return {
            "applied": False, "status": "ENVIRONMENT_INVALID",
            "diff": "", "compile": None, "environment_preflight": preflight,
        }

    target_rel = "src/main/java/com/example/customer/service/ContractPlanService.java"
    diff = "".join(difflib.unified_diff(
        _BUGGY_FULL_FILE.splitlines(keepends=True), candidate_source.splitlines(keepends=True),
        fromfile=f"a/app/{target_rel}", tofile=f"b/app/{target_rel}",
    ))

    workspace = Path(tempfile.mkdtemp(prefix="triage-candidate-"))
    try:
        workspace_app = workspace / "app"
        shutil.copytree(
            APP_DIR, workspace_app,
            ignore=shutil.ignore_patterns("target", ".git"),
        )
        (workspace_app / target_rel).write_text(candidate_source, encoding="utf-8")
        workspace_mvnw = workspace_app / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        if os.name != "nt":
            workspace_mvnw.chmod(0o755)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                [str(workspace_mvnw), "-q", "compile"],
                cwd=str(workspace_app), capture_output=True, text=True, timeout=180, shell=False,
            )
            compile_success = proc.returncode == 0
            compile_output = (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            compile_success = False
            compile_output = "compile timed out after 180s"
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        return {
            "applied": True,
            "status": "COMPILE_VERIFIED" if compile_success else "COMPILE_FAILED",
            "diff": diff,
            "compile": {"success": compile_success, "duration_ms": duration_ms, "output_tail": compile_output[-2000:]},
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def diagnose(reproduction_result: dict, api_key: str | None = None, create_fn=None) -> dict:
    """One real, on-demand Claude call (never automatic/repeated) given
    real evidence. Mirrors agent/backend_planning.py::analyze_with_llm's
    injectable create_fn pattern so tests never make a real billed call."""
    if create_fn is None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return {
                "hypothesis": None, "root_cause": None, "affected_component": None,
                "confidence": None, "model_called": False,
                "explanation": "ANTHROPIC_API_KEY not set -- cannot run live AI diagnosis",
            }
        from anthropic import Anthropic
        create_fn = Anthropic(api_key=api_key).messages.create

    evidence = (
        f"Business context: a customer enrolls in an energy plan; a duplicate submission "
        f"(double-click, or a client retry after a timeout whose original call actually "
        f"succeeded) must not be treated as a second business event.\n\n"
        f"Reproduction result (real database state after submitting the identical enrollment "
        f"request twice):\n{json.dumps(reproduction_result, indent=2)}\n\n"
        f"Defective method source:\n{DEFECTIVE_SOURCE_EXCERPT}"
    )
    response = create_fn(
        model="claude-sonnet-5", max_tokens=512,
        system=DIAGNOSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": evidence}],
    )

    usage = getattr(response, "usage", None)
    if usage is not None:
        import metrics
        metrics.record_model_usage(
            provider="anthropic", model="claude-sonnet-5",
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", None),
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", None),
        )

    text = "".join(b.text for b in response.content if getattr(b, "type", None) == "text")
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    try:
        parsed = json.loads(stripped.strip())
        parsed["model_called"] = True
        return parsed
    except json.JSONDecodeError:
        return {
            "hypothesis": None, "root_cause": None, "affected_component": None, "confidence": None,
            "model_called": True, "explanation": f"model did not return valid JSON: {text[:300]!r}",
        }


# Fallback copy of the exact real diff for commit 2155a8a, captured once
# from real git history where it genuinely exists (a normal dev checkout).
# REAL PRODUCTION BUG found via this session's own live browser testing:
# `railway up` uploads only the working directory, not .git (the exact
# same root cause already documented for the Workbench's commit path --
# see docs/LESSONS.md's "no .git in the deployed image" incident) -- the
# platform-backend's deployed container gets a git repo freshly
# initialized at Docker build time with a single baseline commit, so
# `git show 2155a8a` genuinely has no such revision to find there, even
# though the identical command works in any real developer checkout.
# This is not a fabricated diff: it is a literal, byte-for-byte copy of
# `git show 2155a8a -- <FIX_FILE>`'s real output, used only when the
# live git command cannot find the commit.
_FALLBACK_DIFF = """diff --git a/app/src/main/java/com/example/customer/service/ContractPlanService.java b/app/src/main/java/com/example/customer/service/ContractPlanService.java
index 2fa8e94..8c035c0 100644
--- a/app/src/main/java/com/example/customer/service/ContractPlanService.java
+++ b/app/src/main/java/com/example/customer/service/ContractPlanService.java
@@ -8,6 +8,7 @@ import org.springframework.stereotype.Service;
 import org.springframework.transaction.annotation.Transactional;

 import java.util.NoSuchElementException;
+import java.util.Optional;

 /**
  * BUSINESS REQUIREMENT: a customer has at most one ACTIVE energy plan at a
@@ -38,6 +39,25 @@ public class ContractPlanService {
     public ContractPlan enroll(Long customerId, ContractPlanEnrollRequest request) {
         customerService.getById(customerId); // 404s if the customer itself does not exist

+        Optional<ContractPlan> currentlyActive =
+                contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE);
+
+        // IDEMPOTENCY: a duplicate submission of the exact same enrollment
+        // (a double-click, or a client retrying after a timeout whose
+        // original request actually succeeded server-side) must not be
+        // treated as a second business event. Before this check existed, a
+        // repeat call cancelled the plan the FIRST call had just activated
+        // and created another new plan identical to it -- two CANCELLED
+        // rows plus a second ACTIVE row in the customer's plan history for
+        // what was really one action, and any future side effect fired on
+        // ACTIVE-plan creation (billing, notifications, events) would have
+        // double-fired. If the currently active plan already has identical
+        // terms to what's being requested, this is a no-op: return it
+        // unchanged, touch nothing else.
+        if (currentlyActive.filter(existing -> isSameTerms(existing, request)).isPresent()) {
+            return currentlyActive.get();
+        }
+
         // REAL BUG found only by a genuine Postgres integration test (H2's
         // ddl-auto schema has no equivalent constraint to violate, so this
         // was invisible there): Hibernate's default flush ORDER executes
@@ -50,14 +70,19 @@ public class ContractPlanService {
         // immediate, non-deferred Postgres constraint) correctly rejected
         // with a 500. saveAndFlush() forces the cancellation to reach the
         // database BEFORE the new row is ever inserted, closing the gap.
-        contractPlanRepository.findByCustomerIdAndStatus(customerId, ContractPlanStatus.ACTIVE)
-                .ifPresent(existing -> {
-                    existing.cancel(request.effectiveStartDate());
-                    contractPlanRepository.saveAndFlush(existing);
-                });
+        currentlyActive.ifPresent(existing -> {
+            existing.cancel(request.effectiveStartDate());
+            contractPlanRepository.saveAndFlush(existing);
+        });

         ContractPlan newPlan = new ContractPlan(
                 customerId, request.planName(), request.ratePerKwh(), request.effectiveStartDate());
         return contractPlanRepository.save(newPlan);
     }
+
+    private static boolean isSameTerms(ContractPlan existing, ContractPlanEnrollRequest request) {
+        return existing.getPlanName().equals(request.planName())
+                && existing.getRatePerKwh().compareTo(request.ratePerKwh()) == 0
+                && existing.getEffectiveStartDate().equals(request.effectiveStartDate());
+    }
 }
"""


def get_patch_diff() -> dict:
    """The REAL diff that fixed this exact defect (commit 2155a8a) --
    not a synthetic/regenerated one. Tries `git show` first (a fixed
    argv list, no shell=True, no user-controlled input) against this
    repo's own real history; falls back to a literal, previously-captured
    copy of that exact same command's output when the running
    environment's git history doesn't contain the commit (see
    _FALLBACK_DIFF's docstring -- a real, known deployment-environment
    gap, not a code path being silently skipped)."""
    try:
        proc = subprocess.run(
            ["git", "show", FIX_COMMIT, "--", FIX_FILE],
            cwd=str(tools.REPO_ROOT), capture_output=True, text=True, timeout=15, shell=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return {"available": True, "commit": FIX_COMMIT, "file": FIX_FILE, "diff": proc.stdout[:8000], "source": "git"}
    except subprocess.TimeoutExpired:
        pass
    return {"available": True, "commit": FIX_COMMIT, "file": FIX_FILE, "diff": _FALLBACK_DIFF, "source": "embedded_fallback"}


def verify_fix() -> dict:
    """Runs the REAL, focused regression tests that prove this fix (and
    the Triage scenario's own isolation) -- a live Maven subprocess, not
    a cached/fabricated result. Scoped to exactly the two relevant test
    classes (Test Impact Analysis judgment: this change only touches
    ContractPlanService + the triage package, no reason to run the full
    suite for a live UI-triggered verification step).

    FAIL CLOSED (AEQ-021): checks environment_preflight.check_java_toolchain()
    FIRST -- a real mvnw test run with a JDK older than app/pom.xml's
    required release target fails with a Maven error indistinguishable
    from a real test failure unless this is checked and reported as its
    own distinct, machine-readable status before any subprocess runs."""
    preflight = environment_preflight.check_java_toolchain()
    if preflight["status"] != "ENVIRONMENT_VALID":
        return {
            "success": False,
            "status": "ENVIRONMENT_INVALID",
            "duration_ms": 0.0,
            "tests": ["ContractPlanServiceTest", "TriageScenarioAIntegrationTest"],
            "output_tail": (
                f"ENVIRONMENT_INVALID: required Java {preflight['expected_java_major_minimum']}+ "
                f"but detected {preflight['detected_java_major']!r} -- refusing to run real tests "
                f"that would fail for an environment reason, not a code reason."
            ),
            "environment_preflight": preflight,
        }
    if not MVNW.exists():
        return {"success": False, "reason": f"Maven wrapper not found at {MVNW}"}
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [str(MVNW), "-q", "-Dtest=ContractPlanServiceTest,TriageScenarioAIntegrationTest", "test"],
            cwd=str(APP_DIR), capture_output=True, text=True, timeout=180, shell=False,
        )
        success = proc.returncode == 0
        raw_output = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        success = False
        raw_output = "timed out after 180s"
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    return {
        "success": success,
        "duration_ms": duration_ms,
        "tests": ["ContractPlanServiceTest", "TriageScenarioAIntegrationTest"],
        "output_tail": raw_output[-2000:],
    }
