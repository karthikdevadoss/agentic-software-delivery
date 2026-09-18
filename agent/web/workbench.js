// Agentic Software Delivery — Trainer live workbench frontend.
//
// RESILIENCE DESIGN (see knowledge/sessions/2026-09-10-trainer-idempotency-fix.md,
// incident trainer-988627bc): a Cloudflare Quick Tunnel was proven to
// silently drop an entire SSE stream — no error event, no close event,
// just zero bytes delivered — while the backend was genuinely working the
// whole time. A client cannot reliably detect that kind of silent
// failure from EventSource's own signals. So SSE is a latency
// optimization here, never the only source of truth: a plain HTTP poll
// of the existing GET /api/runs/{id} endpoint (already returns the full
// event log + status — no new backend endpoint needed) always runs
// alongside it, and both funnel into the SAME idempotent event-apply
// path so the UI is correct regardless of which transport actually
// delivers data.

const requirementInput = document.getElementById("requirement-input");
const submitBtn = document.getElementById("submit-btn");
const statusBadge = document.getElementById("status-badge");
const examplesList = document.getElementById("examples-list");
const assessmentPanel = document.getElementById("assessment-panel");
const assessmentBody = document.getElementById("assessment-body");
const runStatusPanel = document.getElementById("run-status-panel");
const rsOverall = document.getElementById("rs-overall");
const rsRunId = document.getElementById("rs-runid");
const rsTransport = document.getElementById("rs-transport");
const rsStage = document.getElementById("rs-stage");
const rsStageElapsed = document.getElementById("rs-stage-elapsed");
const rsTotalElapsed = document.getElementById("rs-total-elapsed");
const rsLastActivity = document.getElementById("rs-last-activity");
const milestoneBar = document.getElementById("milestone-bar");
const milestoneDetail = document.getElementById("milestone-detail");
const activityPanel = document.getElementById("activity-panel");
const activityList = document.getElementById("activity-list");
const verificationPanel = document.getElementById("verification-panel");
const verificationList = document.getElementById("verification-list");
const deployPanel = document.getElementById("deploy-panel");
const deployBody = document.getElementById("deploy-body");
const resultPanel = document.getElementById("result-panel");
const resultBanner = document.getElementById("result-banner");
const resultText = document.getElementById("result-text");
const usageSummaryBox = document.getElementById("usage-summary-box");
const targetAppBody = document.getElementById("target-app-body");

// RELIABILITY/CORRECTION PHASE (2026-09-13): a small hardcoded fallback
// matching the real deterministic catalogue (agent/demo_catalogue.py) —
// used only if the live /api/trainer/catalogue fetch fails; the real
// examples are loaded dynamically below so this can never silently drift
// from the actual supported operations.
let EXAMPLES = [
  'Change the heading text to "Customer Portal"',
  'Change the subtitle text to "A live demo application"',
  'Change the footer text to "Built with care"',
];

const TERMINAL_STAGES = new Set(["COMPLETED", "FAILED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN"]);

// The real, linear order of stage-keys this pipeline's backend
// (_run_trainer_thread in agent/web_server.py) actually emits for the
// non-testing part of the flow — used only to derive "reached vs. not
// yet reached" for the milestone bar below. TESTING is excluded here
// because its real stage strings vary (see testingChecklistState()).
const PIPELINE_STAGE_ORDER = ["APPLYING CHANGE", "COMMITTING", "PUSHING", "DEPLOYING", "VERIFYING PRODUCTION"];

// Stages where long silence is EXPECTED (waiting on an external system),
// not a sign anything is wrong — calibrated from real observed durations
// this session (a genuine Railway cold-build deploy took ~11.5-19 min).
// Anything else uses a much shorter default before flagging no-progress,
// since those steps normally finish in seconds.
//
// Real incident this fixes (WORKBENCH RELIABILITY, 2026-09-13): the
// backend's "VERIFYING PRODUCTION" stage legitimately polls silently —
// wait_for_new_deployment() alone allows up to 15 minutes, plus up to a
// further 90s content-verification retry window (see web_server.py's
// _verify_content_with_retry) — with no intermediate progress event
// emitted until it resolves. This key was previously MISSING from this
// map, so it silently fell through to DEFAULT_MAX_QUIET_SECONDS (30s),
// meaning any real verification run slower than 30s showed
// "STALLED / NO RECENT PROGRESS" while genuinely, correctly still
// working — exactly what the Owner observed and reported as confusing.
const STAGE_MAX_QUIET_SECONDS = { DEPLOYING: 20 * 60, "VERIFYING PRODUCTION": 20 * 60, TESTING: 120, BUILDING: 90 };
const DEFAULT_MAX_QUIET_SECONDS = 30;

// A stage genuinely waiting on an external system gets a calm, specific
// "waiting" label instead of a bare "RUNNING" once it's been quiet for a
// few seconds — and, critically, well before STAGE_MAX_QUIET_SECONDS
// would otherwise flag it STALLED. Never invents progress; only relabels
// a known-slow, still-healthy wait.
const STAGE_WAITING_LABEL = {
  DEPLOYING: "WAITING FOR NEW DEPLOYMENT (Railway)",
  "VERIFYING PRODUCTION": "VERIFYING LIVE PRODUCTION (waiting for traffic cutover)",
};
const WAITING_LABEL_QUIET_THRESHOLD_S = 5;

const POLL_INTERVAL_MS = 3000;
const SSE_LIVE_WINDOW_MS = 6000; // how recently an SSE message must have arrived to call the transport "live"

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

// One click, zero typing: an example button fills the field AND runs it
// immediately — the same real pipeline a typed requirement goes through
// (a real isolated-workspace clone, commit, push, deploy, and production
// verification), just without making a visitor type anything first.
// Previously these only filled the textarea and still needed a separate
// "Submit" click; the blocked-request alternatives below already
// auto-submitted, so this makes the primary path consistent with that.
// The visible "▶ " marker is pure CSS (.one-click-btn::before in
// workbench.css) rather than prepended here, so this button's textContent
// stays exactly equal to the real backend catalogue string — the
// invariant e2e/workbench-catalogue.spec.js's "supported examples are
// loaded from the real backend catalogue" test checks.
function renderExampleButtons() {
  examplesList.innerHTML = "";
  EXAMPLES.forEach(ex => {
    const btn = document.createElement("button");
    btn.className = "secondary example-btn one-click-btn";
    btn.textContent = ex;
    btn.title = "Runs this change through the real pipeline immediately (a real deploy, not a preview)";
    btn.addEventListener("click", () => { requirementInput.value = ex; submit(); });
    examplesList.appendChild(btn);
  });
}
renderExampleButtons();

// Load the REAL supported examples from the backend — never trust the
// hardcoded fallback above as anything but a last resort, since the
// actual deterministic catalogue (agent/demo_catalogue.py) is this
// list's only source of truth.
fetch("/api/trainer/catalogue")
  .then(resp => resp.ok ? resp.json() : Promise.reject())
  .then(data => {
    if (Array.isArray(data.examples) && data.examples.length) {
      EXAMPLES = data.examples;
      renderExampleButtons();
    }
  })
  .catch(() => { /* keep the hardcoded fallback — never leave the panel empty */ });

// ---- Target application (shown before any requirement is submitted) -----
// Fetched from the backend rather than hardcoded here, so this can never
// drift from the exact URL the backend itself deploys to and verifies
// against (see agent/web_server.py's TARGET_APPLICATION/PUBLIC_CUSTOMER_APP_URL).
let targetApp = null;
const TARGET_APP_TIMEOUT_MS = 8000;

// Real production incident: this card was observed stuck on "Loading
// target application..." indefinitely. fetch() has NO built-in timeout —
// a hung/slow response (or a stale cached script from before this
// endpoint existed) left the card with no bounded failure path at all.
// AbortController + a fallback with a manual retry button ensures this
// card can never stay on "Loading..." forever, and a truthful message +
// the known real URL are shown even when the live lookup genuinely fails.
async function loadTargetApp() {
  targetAppBody.innerHTML = `<p class="hint">Loading target application…</p>`;
  let timeoutId;
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => reject(new Error("target-app fetch timed out")), TARGET_APP_TIMEOUT_MS);
  });
  try {
    const resp = await Promise.race([fetch("/api/target-app"), timeout]);
    clearTimeout(timeoutId);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    targetApp = await resp.json();
    targetAppBody.innerHTML =
      `<div class="kv"><span class="k">Application</span><span class="v">${esc(targetApp.name)}</span></div>` +
      `<div class="kv"><span class="k">Environment</span><span class="v">${esc(targetApp.environment)}</span></div>` +
      `<p class="hint">${esc(targetApp.description)}</p>` +
      `<a class="secondary open-app-link" href="${esc(targetApp.url)}" target="_blank" rel="noopener">OPEN CURRENT CUSTOMER APP ↗</a>`;
  } catch (_) {
    clearTimeout(timeoutId);
    // Truthful, USABLE fallback — never left staring at "Loading…"
    // forever, and never silently omits the one thing a trainer actually
    // needs (a working link to the real target application).
    targetAppBody.innerHTML =
      `<p class="hint err">Could not load live target application info (request failed or timed out).</p>` +
      `<a class="secondary open-app-link" href="${esc(PUBLIC_CUSTOMER_APP_FALLBACK_URL)}" target="_blank" rel="noopener">OPEN CURRENT CUSTOMER APP ↗</a>` +
      `<button class="secondary" id="retry-target-app" style="margin-left:0.5rem;">RETRY</button>`;
    const retryBtn = document.getElementById("retry-target-app");
    if (retryBtn) retryBtn.addEventListener("click", loadTargetApp);
  }
}

// Static, known-correct fallback for the one case the live lookup itself
// cannot answer (the lookup failed) — kept in sync with
// agent/web_server.py's PUBLIC_CUSTOMER_APP_URL; used ONLY when
// /api/target-app is unreachable, never as the primary source of truth.
const PUBLIC_CUSTOMER_APP_FALLBACK_URL = "https://agentic-delivery-customer-app-production.up.railway.app/";

loadTargetApp();

// RECRUITER-FACING VERIFIED-RUN P0 (2026-09-13): real incident — this
// link used to be a bare hard-coded href to one specific run_id in
// workbench.html, which silently went stale the moment a newer real run
// completed (the Owner clicked it and landed on a two-day-old example
// with no explanation). The destination is now looked up live from
// agent/web_server.py's GET /api/workbench/verified-run, which runs a
// real, deterministic "most recent genuinely COMPLETED trainer run"
// query on every request — never a client-side guess, never cached
// past this page load.
const verifiedRunLink = document.getElementById("verified-run-link");
const verifiedRunUnavailable = document.getElementById("verified-run-unavailable");
const verifiedRunLoading = document.getElementById("verified-run-loading");
const VERIFIED_RUN_TIMEOUT_MS = 8000;

async function loadVerifiedRun() {
  let timeoutId;
  const timeout = new Promise((_, reject) => {
    timeoutId = setTimeout(() => reject(new Error("verified-run fetch timed out")), VERIFIED_RUN_TIMEOUT_MS);
  });
  try {
    const resp = await Promise.race([fetch("/api/workbench/verified-run"), timeout]);
    clearTimeout(timeoutId);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    verifiedRunLoading.hidden = true;
    if (data.available && data.run_id) {
      verifiedRunLink.href = `/usage/session/${encodeURIComponent(data.run_id)}`;
      verifiedRunLink.hidden = false;
      verifiedRunUnavailable.hidden = true;
    } else {
      // Honest empty state — never a broken link, never a stale fallback.
      verifiedRunLink.hidden = true;
      verifiedRunUnavailable.hidden = false;
    }
  } catch (_) {
    clearTimeout(timeoutId);
    verifiedRunLoading.hidden = true;
    verifiedRunLink.hidden = true;
    verifiedRunUnavailable.hidden = false;
    verifiedRunUnavailable.textContent = "Could not check for a verified run right now.";
  }
}

loadVerifiedRun();

function currentAppUrl() {
  return (targetApp && targetApp.url) || (run && run.deploymentInfo && run.deploymentInfo.public_url) || "#";
}

// ---- Single source of truth for the active run --------------------------

let run = null; // { id, seenEventKeys, stagesSeen: Set, currentStage, status, finished }
let eventSource = null;
let pollTimer = null;
let tickTimer = null;
let lastSSEActivityMs = 0;
let pollEverSucceeded = false;
let pollFailing = false;
let runStartedAtMs = 0;
let verificationState = { applySucceeded: null, compileResult: null, testResult: null };

function resetPanels() {
  assessmentPanel.hidden = true;
  runStatusPanel.hidden = true;
  activityPanel.hidden = true;
  verificationPanel.hidden = true;
  deployPanel.hidden = true;
  resultPanel.hidden = true;
  activityList.innerHTML = "";
  verificationList.innerHTML = "";
  milestoneBar.innerHTML = "";
  milestoneDetail.hidden = true;
  milestoneDetail.innerHTML = "";
  delete milestoneDetail.dataset.openKey;
  deployBody.innerHTML = "";
  usageSummaryBox.innerHTML = "";
  verificationState = { applySucceeded: null, compileResult: null, testResult: null };
  stopEverything();
  run = null;
}

function stopEverything() {
  if (eventSource) { eventSource.close(); eventSource = null; }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
}

function setStatus(label) {
  statusBadge.textContent = label;
  const map = {
    IDLE: "status-idle", COMPLETED: "status-completed", FAILED: "status-failed",
    NO_CHANGE_NEEDED: "status-completed", DEPLOYMENT_STATUS_UNKNOWN: "status-waiting",
  };
  statusBadge.className = "status-badge " + (map[label] || "status-running");
}

function renderAssessment(a, blocked) {
  assessmentPanel.hidden = false;
  if (!blocked && run) run.expectedValue = a.new_value;
  let html = "";
  if (blocked) {
    html += `<p class="owner-auth-notice">${esc(a.message || "Authorization required. This request is outside the autonomous public-demo scope.")}</p>`;
    html += `<div class="kv"><span class="k">Reason</span><span class="v">${esc(a.reason)}</span></div>`;
    html += `<p class="hint" style="margin-top:0.8rem;">Try one of these verified demo changes instead:</p><div id="alt-list"></div>`;
  } else {
    html += `<div class="kv"><span class="k">Field</span><span class="v">${esc(a.human_name)}</span></div>`;
    html += `<div class="kv"><span class="k">New value</span><span class="v">"${esc(a.new_value)}"</span></div>`;
    html += `<div class="kv"><span class="k">Decision</span><span class="v"><strong style="color:var(--green)">AUTO-EXECUTE</strong></span></div>`;
    html += `<div class="kv"><span class="k">Verification method</span><span class="v">${esc(a.expected_verification_method)}</span></div>`;
    html += `<div class="kv"><span class="k">Production assertion</span><span class="v">${esc(a.expected_production_assertion)}</span></div>`;
    html += `<div class="kv"><span class="k">Actual cost</span><span class="v">$0.00 — deterministic operation, no AI model call</span></div>`;
  }
  assessmentBody.innerHTML = html;

  if (blocked) {
    const altList = document.getElementById("alt-list");
    const alternatives = (a.suggested_examples && a.suggested_examples.length) ? a.suggested_examples : EXAMPLES;
    alternatives.forEach(alt => {
      const btn = document.createElement("button");
      btn.className = "secondary example-btn";
      btn.textContent = "USE: " + alt;
      btn.addEventListener("click", () => { requirementInput.value = alt; submit(); });
      altList.appendChild(btn);
    });
  }
}

function addActivityLine(html) {
  const li = document.createElement("li");
  li.innerHTML = html;
  activityList.appendChild(li);
  activityList.scrollTop = activityList.scrollHeight;
}

function addVerificationLine(label, result) {
  verificationPanel.hidden = false;
  const li = document.createElement("li");
  const statusText = result.success ? "PASS" : "FAIL";
  const cls = result.success ? "ok" : "err";
  const mark = result.success ? "✓" : "✗";
  let html = `<div><strong>${label}</strong></div>`;
  html += `<div>${mark} <span class="${cls}">${statusText}</span> &middot; Duration: ${(result.duration_ms / 1000).toFixed(1)}s</div>`;
  if (result.summary) html += `<pre class="verification-summary">${esc(result.summary)}</pre>`;
  li.innerHTML = html;
  verificationList.appendChild(li);
}

// ---- Stage checklist ------------------------------------------------------

// Real production incident: the fixed checklist entry for "Testing"
// looked visually PENDING (a hollow ○) even after Committing/Deploying/
// Verifying all showed done — because the backend's real stage string is
// "TESTING — NOT APPLICABLE" (or plain "TESTING" when tests actually
// run), never the bare "TESTING" key this checklist matches against, so
// the generic seen/skipped logic below never recognized it as reached.
// A terminal run must never leave Testing looking like it hasn't
// happened yet — this returns one of the exact allowed explicit states.
// Real production incident: "no test files exist" was labeled TESTING —
// NOT APPLICABLE unconditionally, which is semantically wrong for a Java
// source change (NO TEST FILES != TESTING NOT APPLICABLE — see
// agent/web_server.py::_determine_testing_state). Each of these states is
// a distinct, real, checkable fact — never a default/guess:
//   NOT APPLICABLE  — the changed file genuinely has no test surface
//                      (e.g. a static HTML/JS resource).
//   NOT CONFIGURED  — testing would reasonably apply, but this project
//                      has no automated coverage for it yet.
//   SKIPPED         — real applicable tests exist but were not run for
//                      this change (blocks commit, unlike the two above).
const _EXPLICIT_TESTING_STAGES = {
  "TESTING — NOT APPLICABLE": { cls: "skipped", mark: "—", label: "TESTING — NOT APPLICABLE" },
  "TESTING — NOT CONFIGURED": { cls: "skipped", mark: "—", label: "TESTING — NOT CONFIGURED" },
  "TESTING — SKIPPED": { cls: "failed", mark: "✗", label: "TESTING — SKIPPED" },
};

function testingChecklistState() {
  for (const [stageKey, presentation] of Object.entries(_EXPLICIT_TESTING_STAGES)) {
    if (run.stagesSeen.has(stageKey)) {
      return {
        ...presentation,
        note: `<span class="skip-note">${esc(run.testingSkipReason || "see reason")}</span>`,
      };
    }
  }
  if (run.stagesSeen.has("TESTING")) {
    const passed = !verificationState.testResult || verificationState.testResult.success;
    return passed
      ? { cls: "done", mark: "✓", label: "TESTING — PASSED", note: "" }
      : { cls: "failed", mark: "✗", label: "TESTING — FAILED", note: "" };
  }
  if (TERMINAL_STAGES.has(run.status)) {
    // Terminal with no testing decision of any kind ever recorded — an
    // explicit, truthful gap flag, never a silent/ambiguous "pending".
    return { cls: "skipped", mark: "?", label: "TESTING", note: '<span class="skip-note">NO TESTING DECISION RECORDED</span>' };
  }
  return { cls: "pending", mark: "○", label: "Testing", note: "" };
}

// ---- Milestone bar (9-stage delivery lifecycle) ---------------------
//
// Maps this run's REAL event/state (stagesSeen, currentStage, status,
// plus the commit/push/deployment/diff evidence already captured by
// applyEvent below) onto the canonical
// Requirement -> Context -> Planning -> Implementation -> Testing ->
// AI QA -> Git -> Deployment -> Production Verify lifecycle. Every
// state shown here is derived from a real backend event — nothing is
// a fake timer or an assumed percentage. The public trainer pipeline
// (_run_trainer_thread) is fully deterministic and zero-LLM, so
// Context/Planning/AI QA are honestly NOT_APPLICABLE for every run of
// this tier, never hidden and never guessed as "done".
const STATE_META = {
  PENDING: { cls: "pending", mark: "○" },
  RUNNING: { cls: "running", mark: "●" },
  PASSED: { cls: "passed", mark: "✓" },
  FAILED: { cls: "failed", mark: "✗" },
  BLOCKED: { cls: "blocked", mark: "!" },
  SKIPPED: { cls: "skipped", mark: "—" },
  NOT_APPLICABLE: { cls: "na", mark: "—" },
};

function computeMilestoneStates(r) {
  const terminal = TERMINAL_STAGES.has(r.status);
  const seen = (k) => r.stagesSeen.has(k);
  const current = (k) => r.currentStage === k && !terminal;
  const failedTerminal = r.status === "FAILED";
  const noChange = r.status === "NO_CHANGE_NEEDED";
  const unknownTerminal = r.status === "DEPLOYMENT_STATUS_UNKNOWN";
  const m = [];

  m.push({ key: "REQUIREMENT", label: "Requirement", state: "PASSED",
    detail: "Accepted by the deterministic public-demo request contract before this run started." });

  m.push({ key: "CONTEXT", label: "Context", state: "NOT_APPLICABLE",
    detail: "This preview tier matches the requirement against a fixed, deterministic catalogue — no RAG/context retrieval call is made." });

  m.push({ key: "PLANNING", label: "Planning", state: "NOT_APPLICABLE",
    detail: "No LLM planning call — the exact source edit is derived deterministically from the matched catalogue operation, never generated." });

  let implState, implDetail;
  if (noChange) {
    implState = "SKIPPED"; implDetail = "Live production already had the requested value — nothing to implement.";
  } else if (current("APPLYING CHANGE")) {
    implState = "RUNNING"; implDetail = "Cloning an isolated workspace and applying the deterministic source edit…";
  } else if (r.diffInfo) {
    implState = "PASSED"; implDetail = `${r.diffInfo.file}, line ${r.diffInfo.line_changed}: "${r.diffInfo.old_line}" → "${r.diffInfo.new_line}"`;
  } else if (seen("APPLYING CHANGE") && (seen("COMMITTING") || terminal)) {
    implState = "SKIPPED"; implDetail = "Source already matched the requested value in this run's own isolated workspace; redeployed as-is.";
  } else if (failedTerminal) {
    implState = "FAILED"; implDetail = "Failed before a change could be applied — see the activity log below.";
  } else {
    implState = "PENDING"; implDetail = "";
  }
  m.push({ key: "IMPLEMENTATION", label: "Implementation", state: implState, detail: implDetail });

  const t = testingChecklistState();
  let testState;
  if (t.label.indexOf("NOT APPLICABLE") !== -1 || t.label.indexOf("NOT CONFIGURED") !== -1) testState = "NOT_APPLICABLE";
  else if (t.label.indexOf("SKIPPED") !== -1) testState = "SKIPPED";
  else if (t.label === "TESTING — PASSED") testState = "PASSED";
  else if (t.label === "TESTING — FAILED") testState = "FAILED";
  else if (t.mark === "?") testState = "BLOCKED";
  else testState = "PENDING";
  const testDetail = t.label + (r.testingSkipReason ? ": " + r.testingSkipReason : "");
  m.push({ key: "TESTING", label: "Testing", state: testState, detail: testDetail });

  m.push({ key: "AI_QA", label: "AI QA", state: "NOT_APPLICABLE",
    detail: "Independent QA evaluation (the qa-evaluator subagent) is used internally in this project's own development sessions — not wired into this public preview pipeline yet." });

  let gitState, gitDetail;
  if (noChange) {
    gitState = "SKIPPED"; gitDetail = "Nothing to commit — no change was applied.";
  } else if (current("COMMITTING") || current("PUSHING")) {
    gitState = "RUNNING"; gitDetail = "Committing to a dedicated demo/<run id> branch in the isolated workspace…";
  } else if (r.commitInfo) {
    gitState = "PASSED";
    gitDetail = `Commit ${r.commitInfo.sha} on ${r.commitInfo.branch}` + (r.pushInfo ? ` · Push: ${r.pushInfo.status}` : "");
  } else if (failedTerminal) {
    gitState = "FAILED"; gitDetail = "Failed before a commit was created — see the activity log below.";
  } else {
    gitState = "PENDING"; gitDetail = "";
  }
  m.push({ key: "GIT", label: "Git", state: gitState, detail: gitDetail });

  let deployState, deployDetail;
  if (noChange) {
    deployState = "SKIPPED"; deployDetail = "Nothing to deploy — production already matched the requirement.";
  } else if (current("DEPLOYING")) {
    deployState = "RUNNING"; deployDetail = "Triggering a real Railway deployment from the isolated workspace…";
  } else if (r.deploymentInfo) {
    deployState = r.deploymentInfo.deployment_identity_confirmed ? "PASSED" : (unknownTerminal ? "BLOCKED" : "FAILED");
    deployDetail = `Deployment ${r.deploymentInfo.new_deployment_id || "—"} (${r.deploymentInfo.deployment_status || "—"})`;
  } else if (failedTerminal) {
    deployState = "FAILED"; deployDetail = "Deploy trigger failed — see the activity log below.";
  } else {
    deployState = "PENDING"; deployDetail = "";
  }
  m.push({ key: "DEPLOYMENT", label: "Deployment", state: deployState, detail: deployDetail });

  let verifyState, verifyDetail;
  if (noChange) {
    verifyState = "PASSED";
    verifyDetail = "Live production was fetched and already showed the requested value before any change was attempted.";
  } else if (current("VERIFYING PRODUCTION")) {
    verifyState = "RUNNING"; verifyDetail = "Waiting for the new deployment's identity, then re-checking the live field…";
  } else if (r.deploymentInfo) {
    verifyState = r.deploymentInfo.content_verified ? "PASSED" : (unknownTerminal ? "BLOCKED" : "FAILED");
    verifyDetail = `Expected: "${r.expectedValue || ""}" · Observed: ${r.deploymentInfo.live_value !== undefined ? '"' + r.deploymentInfo.live_value + '"' : "—"}`;
  } else if (failedTerminal) {
    verifyState = "FAILED"; verifyDetail = "Never reached — a prior stage failed.";
  } else {
    verifyState = "PENDING"; verifyDetail = "";
  }
  m.push({ key: "PRODUCTION_VERIFY", label: "Production Verify", state: verifyState, detail: verifyDetail });

  return m;
}

function showMilestoneDetail(key) {
  const s = (run.milestoneStates || []).find(x => x.key === key);
  if (!s) return;
  const meta = STATE_META[s.state] || STATE_META.PENDING;
  milestoneDetail.hidden = false;
  milestoneDetail.dataset.openKey = key;
  milestoneDetail.innerHTML =
    `<div class="milestone-detail-head"><strong>${esc(s.label)}</strong> <span class="milestone-state-tag ${meta.cls}">${esc(s.state.replace("_", " "))}</span></div>` +
    `<div class="milestone-detail-body">${esc(s.detail || "No further detail yet.")}</div>`;
}

function renderMilestoneBar() {
  if (!run) return;
  const states = computeMilestoneStates(run);
  run.milestoneStates = states;
  let html = "";
  states.forEach((s, i) => {
    if (i > 0) {
      const prevDecided = ["PASSED", "SKIPPED", "NOT_APPLICABLE"].indexOf(states[i - 1].state) !== -1;
      html += `<div class="milestone-connector ${prevDecided ? "filled" : ""}"></div>`;
    }
    const meta = STATE_META[s.state] || STATE_META.PENDING;
    const titleText = `${s.label} — ${s.state.replace("_", " ")}${s.detail ? ": " + s.detail : ""}`;
    html += `<button type="button" class="milestone-node ${meta.cls}" data-key="${s.key}" title="${esc(titleText)}">` +
      `<span class="milestone-circle">${meta.mark}</span><span class="milestone-label">${esc(s.label)}</span></button>`;
  });
  milestoneBar.innerHTML = html;
  milestoneBar.querySelectorAll(".milestone-node").forEach(btn => {
    btn.addEventListener("click", () => showMilestoneDetail(btn.dataset.key));
  });
  if (milestoneDetail.dataset.openKey) showMilestoneDetail(milestoneDetail.dataset.openKey);
}

// ---- Applying one backend event (shared by SSE and polling) --------------

function applyEvent(evt) {
  switch (evt.type) {
    case "risk_assessment":
      renderAssessment(evt, false);
      run.stagesSeen.add("RISK_ASSESSMENT");
      break;
    case "stage":
      run.currentStage = evt.stage;
      run.status = evt.stage;
      run.stagesSeen.add(evt.stage);
      // Client clock only — NEVER the backend's evt.ts here. Real
      // production incident: a run showed "Total elapsed: 37s" (correct)
      // alongside "Current stage elapsed: 6m 37s" (wrong) for the SAME
      // terminal run, because stage-elapsed mixed the backend's own
      // clock (evt.ts, Python time.time() inside the Railway container)
      // with this browser's Date.now() — any clock skew between the two
      // machines leaks straight into the displayed duration. Total
      // elapsed was correct only because it never touched evt.ts at all
      // (runStartedAtMs is captured from this same browser's clock).
      // Fix: every duration shown here is now a delta between two
      // timestamps captured on THIS browser, never a cross-machine
      // subtraction.
      run.stageStartedAtMs = Date.now();
      setStatus(evt.stage);
      addActivityLine(`<span class="stage-marker">— ${esc(evt.stage)} —</span>`);
      if (evt.reason) addActivityLine(`<span class="hint">${esc(evt.reason)}</span>`);
      if (evt.stage.startsWith("TESTING — ")) run.testingSkipReason = evt.reason;
      if (TERMINAL_STAGES.has(evt.stage)) {
        // Freeze total/stage elapsed at the real terminal duration —
        // "completed-stage duration must not continue increasing
        // forever" and "do not mix time since completion with duration
        // of completed stage." A terminal run has no more elapsing to
        // do; the "current stage" IS the whole run at this point.
        run.frozenElapsedText = runStartedAtMs ? fmtDuration((Date.now() - runStartedAtMs) / 1000) : "—";
        renderTerminalOutcome();
        finishRun();
      }
      break;
    case "no_change_needed":
      addActivityLine(`<span class="hint">${esc(evt.reason)}</span>`);
      break;
    case "tool_call":
      addActivityLine(`<span class="tool-name">${esc(evt.tool)}</span>(${esc(evt.input_summary)})`);
      break;
    case "tool_result": {
      const cls = evt.success ? "ok" : "err";
      const label = evt.success ? "OK" : "ERROR";
      addActivityLine(`&nbsp;&nbsp;→ <span class="${cls}">${label}</span> · ${evt.duration_ms}ms`);
      if (evt.tool === "apply_approved_source_change") verificationState.applySucceeded = evt.success;
      if (evt.tool === "run_controlled_compile") { verificationState.compileResult = evt; addVerificationLine("BUILD (mvn compile)", evt); }
      if (evt.tool === "run_controlled_tests") { verificationState.testResult = evt; addVerificationLine("TESTS (mvn test)", evt); }
      break;
    }
    case "approval_decision":
      addActivityLine(`<span class="hint">Approval: ${esc(evt.decision)} — decided by: ${esc(evt.decided_by || "policy")}</span>`);
      break;
    case "commit":
      deployPanel.hidden = false;
      run.commitInfo = evt;
      // Never call this a "GitHub commit" — it is a real local commit
      // inside this run's disposable isolated-workspace clone, on a
      // dedicated demo/<run_id> branch, and it may never reach GitHub at
      // all (see the "push" case below). Since it already passed the
      // diff-safety check (unexpected-file-changed guard) before this
      // event was ever emitted, that fact is surfaced here too — real,
      // derived evidence, not a fabricated claim.
      deployBody.innerHTML = `<div class="kv"><span class="k">Local commit (isolated workspace)</span><span class="v"><code>${esc(evt.sha)}</code> <span class="hint">CREATED</span></span></div><div class="kv"><span class="k">Branch</span><span class="v"><code>${esc(evt.branch)}</code></span></div><div class="kv"><span class="k">Changed file</span><span class="v"><code>${esc(evt.path)}</code></span></div>`;
      addVerificationLine("Diff Safety Verification (no unexpected files changed)", { success: true, duration_ms: 0 });
      break;
    case "push":
      deployPanel.hidden = false;
      run.pushInfo = evt;
      // Three distinct, truthful states — never a bare pass/fail. Only
      // FAILED (a real attempted push that genuinely failed) is alarming;
      // NOT_CONFIGURED is an honest, expected precondition (no
      // DEMO_GIT_PUSH_TOKEN provisioned, see ACT-007) and must render
      // calmly, not as if something broke. Real incident this fixes: the
      // Owner's "Built with DOSS care" run genuinely COMPLETED, but this
      // exact ordinary case previously showed an alarming red "no" here
      // AND a duplicate "ERROR: git push failed..." activity line.
      {
        const pushLabel = evt.status === "PUSHED"
          ? '<span style="color:var(--green)">PUSHED — origin/master</span>'
          : evt.status === "NOT_CONFIGURED"
            ? '<span style="color:var(--amber)">NOT_CONFIGURED — no push credential provisioned (deploy continues from the isolated workspace regardless)</span>'
            : '<span style="color:var(--red)">FAILED (deploy continues from the isolated workspace regardless)</span>';
        deployBody.innerHTML += `<div class="kv"><span class="k">GitHub Push</span><span class="v">${pushLabel}</span></div>`;
      }
      break;
    case "deployment": {
      deployPanel.hidden = false;
      run.deploymentInfo = evt;
      // "Verified" now means BOTH the server is reachable AND the exact
      // requested content was found live in production — HTTP 200 alone
      // is never sufficient (real incident: HTTP 200 + old content was
      // previously shown as "VERIFIED").
      const verifiedBadge = evt.verified
        ? '<span style="color:var(--green)">VERIFIED — requested content confirmed live (HTTP 200)</span>'
        : '<span style="color:var(--red)">NOT VERIFIED' + (evt.http_status === 200 && !evt.content_verified ? " — requested content not found in production" : "") + '</span>';
      deployBody.innerHTML += `<div class="kv"><span class="k">Deployed commit</span><span class="v"><code>${esc(evt.production_commit)}</code></span></div>`;
      deployBody.innerHTML += `<div class="kv"><span class="k">Public app</span><span class="v"><a href="${esc(evt.public_url)}" target="_blank" rel="noopener">${esc(evt.public_url)}</a></span></div>`;
      deployBody.innerHTML += `<div class="kv"><span class="k">HTTP status</span><span class="v">${esc(evt.http_status)}</span></div>`;
      if (evt.new_deployment_id) {
        deployBody.innerHTML += `<div class="kv"><span class="k">Railway Deployment</span><span class="v"><code>${esc(evt.new_deployment_id)}</code> (${esc(evt.deployment_status)})</span></div>`;
        deployBody.innerHTML += `<div class="kv"><span class="k">Deployment identity confirmed</span><span class="v">${evt.deployment_identity_confirmed ? "yes — real Railway deployment record, created after this run triggered it" : "no"}</span></div>`;
      }
      deployBody.innerHTML += `<div class="kv"><span class="k">Requested content live</span><span class="v">${evt.content_verified ? "yes" : `no${evt.live_value !== undefined ? ` (found "${esc(evt.live_value)}")` : ""}`}</span></div>`;
      deployBody.innerHTML += `<div class="kv"><span class="k">Production Serving</span><span class="v">${verifiedBadge}</span></div>`;
      // Real, derived evidence (never fabricated): a targeted DOM/text
      // assertion of the exact requested field against the live
      // production response — distinct from Java/Maven testing, which
      // this static-resource change genuinely has no surface for (see
      // the TESTING checklist entry).
      addVerificationLine("Production DOM/Text Assertion (targeted field extraction)", { success: !!evt.content_verified, duration_ms: (evt.waited_seconds || 0) * 1000 });
      break;
    }
    case "workspace":
      deployPanel.hidden = false;
      deployBody.innerHTML += `<div class="kv"><span class="k">Workspace</span><span class="v">${evt.ok ? "isolated clone created" : "isolated clone FAILED"}</span></div>`;
      break;
    case "diff":
      run.diffInfo = evt;
      verificationPanel.hidden = false;
      addVerificationLine("Change", { success: true, summary: `${evt.file}:${evt.line_changed}\n- ${evt.old_line}\n+ ${evt.new_line}` });
      break;
    case "final_result":
      resultPanel.hidden = false;
      run.finalResultText = evt.text;
      // The terminal "stage" event (which triggers renderTerminalOutcome)
      // arrives BEFORE final_result on the COMPLETED/NO_CHANGE_NEEDED
      // paths — refresh just the text here so it isn't left blank.
      if (TERMINAL_STAGES.has(run.status)) resultText.textContent = run.finalResultText;
      break;
    case "error":
      addActivityLine(`<span class="err">ERROR: ${esc(evt.message)}</span>`);
      resultPanel.hidden = false;
      run.lastErrorMessage = evt.message;
      if (TERMINAL_STAGES.has(run.status)) resultText.textContent = run.lastErrorMessage;
      break;
    case "usage_summary":
      run.usageSummary = evt;
      renderUsageSummary(evt);
      break;
  }
  // Client clock only, for every event type uniformly — see the "stage"
  // case above for why this must never be the backend's own evt.ts.
  run.lastEventAtMs = Date.now();
  renderMilestoneBar();
}

// One authoritative place that decides the four possible terminal
// outcomes' banner text and "open the app" button — see Section 4 of the
// Workbench target-app/cost-transparency task. Must never imply a failed
// or unknown change reached production: only the COMPLETED branch is
// allowed to say so, and only after apply/compile/test/deploy all
// genuinely succeeded (enforced server-side by _decide_deployment_outcome
// before COMPLETED is ever reached).
const TERMINAL_OUTCOME = {
  COMPLETED: {
    banner: "PRODUCTION CHANGE VERIFIED", cls: "success",
    buttonLabel: "OPEN UPDATED CUSTOMER APP",
  },
  NO_CHANGE_NEEDED: {
    banner: "CURRENT APPLICATION ALREADY SATISFIES THIS REQUIREMENT", cls: "neutral",
    buttonLabel: "OPEN CURRENT CUSTOMER APP",
  },
  FAILED: {
    banner: "CHANGE WAS NOT VERIFIED AS DEPLOYED", cls: "failed",
    buttonLabel: "OPEN CURRENT CUSTOMER APP",
  },
  DEPLOYMENT_STATUS_UNKNOWN: {
    banner: "DEPLOYMENT STATUS COULD NOT BE CONFIRMED", cls: "neutral",
    buttonLabel: "OPEN CURRENT CUSTOMER APP",
  },
};

function renderTerminalOutcome() {
  resultPanel.hidden = false;
  const outcome = TERMINAL_OUTCOME[run.status] || TERMINAL_OUTCOME.FAILED;
  resultBanner.textContent = outcome.banner;
  resultBanner.className = outcome.cls;

  const buttonUrl = run.status === "COMPLETED"
    ? ((run.deploymentInfo && run.deploymentInfo.public_url) || currentAppUrl())
    : currentAppUrl();
  let evidenceHtml = `<div class="production-verified-box ${outcome.cls}-box">`;
  evidenceHtml += `<div class="terminal-cta-row">`;
  evidenceHtml += `<a class="open-production-btn" href="${esc(buttonUrl)}" target="_blank" rel="noopener">[ ${esc(outcome.buttonLabel)} ]</a>`;
  evidenceHtml += `<a class="secondary-cta-btn" href="/usage/session/${esc(run.id)}" target="_blank" rel="noopener">[ VIEW EVIDENCE ]</a>`;
  evidenceHtml += `<a class="secondary-cta-btn" href="/dashboard" target="_blank" rel="noopener">[ VIEW DASHBOARD ]</a>`;
  evidenceHtml += `<a class="secondary-cta-btn" href="/usage" target="_blank" rel="noopener">[ VIEW USAGE ]</a>`;
  evidenceHtml += `</div>`;
  evidenceHtml += `<div class="kv"><span class="k">Run ID</span><span class="v"><code>${esc(run.id)}</code></span></div>`;
  if (run.status === "COMPLETED") {
    if (run.commitInfo) {
      evidenceHtml += `<div class="kv"><span class="k">Commit SHA</span><span class="v"><code>${esc(run.commitInfo.sha)}</code></span></div>`;
      evidenceHtml += `<div class="kv"><span class="k">Files changed</span><span class="v"><code>${esc(run.commitInfo.path)}</code></span></div>`;
    }
    if (verificationState.compileResult) evidenceHtml += `<div class="kv"><span class="k">Build</span><span class="v">${verificationState.compileResult.success ? "PASS" : "FAIL"} · ${(verificationState.compileResult.duration_ms / 1000).toFixed(1)}s</span></div>`;
    if (verificationState.testResult) evidenceHtml += `<div class="kv"><span class="k">Tests</span><span class="v">${verificationState.testResult.success ? "PASS" : "FAIL"} · ${(verificationState.testResult.duration_ms / 1000).toFixed(1)}s</span></div>`;
    if (run.deploymentInfo) evidenceHtml += `<div class="kv"><span class="k">Deployment</span><span class="v">VERIFIED (HTTP ${esc(run.deploymentInfo.http_status)})</span></div>`;
  }
  if (runStartedAtMs) evidenceHtml += `<div class="kv"><span class="k">Duration</span><span class="v">${fmtDuration((Date.now() - runStartedAtMs) / 1000)}</span></div>`;
  evidenceHtml += `</div>`;

  document.getElementById("result-evidence").innerHTML = evidenceHtml;
  resultText.textContent = run.finalResultText || run.lastErrorMessage || "";
  if (run.usageSummary) renderUsageSummary(run.usageSummary);
}

function renderUsageSummary(evt) {
  if (!evt.captured) {
    usageSummaryBox.innerHTML = `<div class="usage-box"><p class="estimate-label">ACTUAL AI USAGE</p><p class="hint">ACTUAL USAGE NOT CAPTURED</p></div>`;
    return;
  }
  let html = `<div class="usage-box"><p class="estimate-label">ACTUAL AI USAGE</p>`;
  html += `<div class="kv"><span class="k">Model</span><span class="v">${esc(evt.provider)}/${esc(evt.model)}</span></div>`;
  html += `<div class="kv"><span class="k">Input tokens</span><span class="v">${evt.input_tokens.toLocaleString()}</span></div>`;
  html += `<div class="kv"><span class="k">Output tokens</span><span class="v">${evt.output_tokens.toLocaleString()}</span></div>`;
  if (evt.cache_read_tokens) html += `<div class="kv"><span class="k">Cache-read tokens</span><span class="v">${evt.cache_read_tokens.toLocaleString()}</span></div>`;
  if (evt.cache_write_tokens) html += `<div class="kv"><span class="k">Cache-write tokens</span><span class="v">${evt.cache_write_tokens.toLocaleString()}</span></div>`;
  html += `<div class="kv"><span class="k">Actual API cost</span><span class="v">${evt.cost_available ? fmtUsd(evt.cost_usd) : "NOT AVAILABLE (" + esc(evt.cost_unavailable_reason || "unpriced model") + ")"}</span></div>`;
  if (evt.elapsed_seconds != null) html += `<div class="kv"><span class="k">Elapsed run time</span><span class="v">${fmtDuration(evt.elapsed_seconds)}</span></div>`;
  if (evt.tool_call_count != null) html += `<div class="kv"><span class="k">Tool-call count</span><span class="v">${evt.tool_call_count}</span></div>`;
  if (evt.estimate_error) {
    const ee = evt.estimate_error;
    html += `<p class="hint estimate-basis">Estimate vs. actual: predicted ${ee.estimated_total_tokens_range[0].toLocaleString()}–${ee.estimated_total_tokens_range[1].toLocaleString()} tokens, actual ${ee.actual_total_tokens.toLocaleString()} (${ee.within_estimated_range ? "within range" : "outside range"}).</p>`;
  }
  html += `</div>`;
  usageSummaryBox.innerHTML = html;
}

// Dedup key: (type, ts) is effectively unique per real backend event —
// timestamps come from time.time() at the moment each distinct thing
// actually happened. Deliberately NOT a position/count-based cursor:
// SSE's server-side generator always replays from the start on a NEW
// connection (see agent/web_server.py's _generate_run_events — sent=0
// per request), and this browser-observed tunnel is known to drop and
// silently reconnect SSE streams. A count that assumes "the Nth message
// I've seen is absolute position N" breaks the moment a stream restarts
// mid-run; a content-based key doesn't care how many times the same
// event arrives from however many sources, in whatever order.
function applyEventIfNew(evt) {
  const key = `${evt.type}|${evt.ts}`;
  if (run.seenEventKeys.has(key)) return;
  run.seenEventKeys.add(key);
  applyEvent(evt);
}

// Feeds every event in a full snapshot through the same dedup path as
// SSE — this is what makes polling and SSE safely combinable regardless
// of which one delivers a given event first, or how many times a
// reconnecting SSE stream replays its history.
function applyNewEvents(fullEvents) {
  fullEvents.forEach(applyEventIfNew);
}

function finishRun() {
  if (run.finished) return;
  run.finished = true;
  submitBtn.disabled = false;
  // Small delay before closing SSE: the server emits the reason (an
  // "error"/"no_change_needed" event) in the same batch just before the
  // terminal "stage" event; closing synchronously risks the browser
  // dropping an already-buffered sibling message. See knowledge/sessions.
  // Captures this run by reference so a resubmit within the delay window
  // can never have its fresh connections torn down by a stale timer from
  // the previous run.
  const finishedRun = run;
  setTimeout(() => { if (run === finishedRun) stopEverything(); }, 300);
}

// ---- Transport: SSE (fast path) ------------------------------------------

function subscribeToRun(runId) {
  eventSource = new EventSource(`/api/runs/${runId}/events`);
  const onMessage = (e) => {
    lastSSEActivityMs = Date.now();
    try { applyEventIfNew(JSON.parse(e.data)); } catch (_) { /* malformed frame, ignore */ }
  };
  ["risk_assessment", "stage", "no_change_needed", "tool_call", "tool_result",
   "approval_decision", "workspace", "diff", "commit", "push", "deployment",
   "final_result", "error", "usage_summary"]
    .forEach(type => eventSource.addEventListener(type, onMessage));
}

// ---- Transport: HTTP polling (always-on safety net) ----------------------
//
// Runs regardless of SSE health. This is deliberate: the incident that
// motivated this file involved SSE delivering ZERO bytes with no error
// or close event at all, so there was no reliable client-side signal to
// react to. Polling doesn't wait for a detected failure — it's just
// always there, so a silent SSE failure costs at most one poll interval
// of latency instead of leaving the UI blind indefinitely.

async function pollOnce() {
  if (!run || run.finished) return;
  try {
    const resp = await fetch(`/api/runs/${run.id}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    pollEverSucceeded = true;
    pollFailing = false;
    applyNewEvents(data.events);
    if (TERMINAL_STAGES.has(data.status)) finishRun();
  } catch (_) {
    pollFailing = true;
  }
}

function startPolling() {
  pollOnce();
  pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
}

// ---- Run-status panel: transport badge + timers --------------------------

function transportLabel() {
  if (Date.now() - lastSSEActivityMs < SSE_LIVE_WINDOW_MS) return { text: "LIVE — SSE", cls: "live-sse" };
  if (pollEverSucceeded && !pollFailing) return { text: "LIVE — POLLING FALLBACK", cls: "live-polling" };
  if (!pollEverSucceeded && pollFailing) return { text: "BACKEND STATUS UNKNOWN", cls: "unknown" };
  if (pollFailing) return { text: "CONNECTION LOST", cls: "lost" };
  return { text: "CONNECTING…", cls: "unknown" };
}

function overallStateLabel() {
  if (!run) return "—";
  if (TERMINAL_STAGES.has(run.status)) return run.status;
  const quietS = run.lastEventAtMs ? (Date.now() - run.lastEventAtMs) / 1000 : 0;
  const maxQuiet = STAGE_MAX_QUIET_SECONDS[run.currentStage] || DEFAULT_MAX_QUIET_SECONDS;
  // STALLED takes priority over a "waiting" label once the real threshold
  // for this stage is exceeded — a known-slow wait is not exempt from
  // ever being flagged, only from being flagged too early.
  if (quietS > maxQuiet) return "STALLED / NO RECENT PROGRESS";
  const waitingLabel = STAGE_WAITING_LABEL[run.currentStage];
  if (waitingLabel && quietS > WAITING_LABEL_QUIET_THRESHOLD_S) return waitingLabel;
  return "RUNNING";
}

function fmtDuration(seconds) {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function tick() {
  if (!run) return;
  const t = transportLabel();
  rsTransport.innerHTML = `<span class="transport-badge ${t.cls}">${esc(t.text)}</span>`;
  rsOverall.textContent = overallStateLabel();
  rsStage.textContent = run.currentStage || "—";
  const nowMs = Date.now();
  if (TERMINAL_STAGES.has(run.status)) {
    // Terminal: freeze both — a completed run has no "ongoing" stage
    // left to elapse, and total duration is a fixed historical fact,
    // never a growing number. Both come from the SAME frozen client-
    // clock computation taken the instant the terminal stage arrived.
    rsStageElapsed.textContent = run.frozenElapsedText || "—";
    rsTotalElapsed.textContent = run.frozenElapsedText || "—";
  } else {
    rsStageElapsed.textContent = run.stageStartedAtMs ? fmtDuration((nowMs - run.stageStartedAtMs) / 1000) : "—";
    rsTotalElapsed.textContent = runStartedAtMs ? fmtDuration((nowMs - runStartedAtMs) / 1000) : "—";
  }
  // "Last backend activity" is explicitly allowed to keep growing after
  // a run ends (it genuinely means "how long ago was the last event"),
  // clearly labeled as such in the UI — but it must use THIS browser's
  // own receipt time (lastEventAtMs), never the backend's clock, or a
  // clock-skewed container would silently distort it just like the
  // stage-elapsed bug above did.
  rsLastActivity.textContent = run.lastEventAtMs ? `${fmtDuration((nowMs - run.lastEventAtMs) / 1000)} ago` : "—";
}

// ---- Submit flow ----------------------------------------------------------

async function assess() {
  const requirement = requirementInput.value.trim();
  const resp = await fetch("/api/trainer/assess", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  });
  return resp.json();
}

async function submit() {
  const requirement = requirementInput.value.trim();
  if (!requirement) return;

  resetPanels();
  submitBtn.disabled = true;
  setStatus("ASSESSING RISK/SCOPE");

  const a = await assess();
  renderAssessment(a, a.decision !== "auto");

  if (a.decision !== "auto") {
    setStatus("IDLE");
    submitBtn.disabled = false;
    return;
  }

  activityPanel.hidden = false;
  runStatusPanel.hidden = false;
  // Real UI gap found during this task's live acceptance testing: the
  // panel became visible before the POST response set a real run ID,
  // leaving the stale "—" placeholder briefly visible with no indication
  // anything was actually happening yet.
  rsRunId.textContent = "starting…";
  setStatus("STARTING");

  const resp = await fetch("/api/trainer/runs", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  });
  const data = await resp.json();
  if (data.busy) {
    assessmentPanel.hidden = false;
    assessmentBody.innerHTML = `<div class="kv"><span class="k">Status</span><span class="v"><strong style="color:var(--amber)">BUSY</strong></span></div><p class="hint">${esc(data.message || "A demo deployment is currently running. Try again shortly.")}</p>`;
    setStatus("IDLE");
    submitBtn.disabled = false;
    runStatusPanel.hidden = true;
    return;
  }
  if (data.blocked) {
    renderAssessment(data.assessment, true);
    setStatus("IDLE");
    submitBtn.disabled = false;
    runStatusPanel.hidden = true;
    return;
  }

  run = {
    id: data.run_id, seenEventKeys: new Set(), stagesSeen: new Set(["RECEIVED"]),
    currentStage: null, status: "STARTING", lastEventAtMs: null,
    stageStartedAtMs: null, frozenElapsedText: null, finished: false,
    finalResultText: null, lastErrorMessage: null, usageSummary: null,
    testingSkipReason: null,
  };
  rsRunId.textContent = data.run_id;
  runStartedAtMs = Date.now();
  lastSSEActivityMs = 0;
  pollEverSucceeded = false;
  pollFailing = false;

  subscribeToRun(data.run_id); // fast path, best-effort
  startPolling();              // always-on safety net — never optional
  tickTimer = setInterval(tick, 1000);
  tick();
}

submitBtn.addEventListener("click", submit);

// ---- Demo lifecycle: Reset Demo -------------------------------------------

const resetDemoBtn = document.getElementById("reset-demo-btn");
const resetDemoStatus = document.getElementById("reset-demo-status");

async function pollResetStatus() {
  const resp = await fetch("/api/trainer/reset");
  const data = await resp.json();
  if (data.status === "running") {
    resetDemoStatus.textContent = data.message || "Restoring production baseline…";
    setTimeout(pollResetStatus, 3000);
  } else {
    resetDemoBtn.disabled = false;
    resetDemoStatus.textContent = data.message || "";
  }
}

resetDemoBtn.addEventListener("click", async () => {
  resetDemoBtn.disabled = true;
  resetDemoStatus.textContent = "Starting production baseline restore…";
  const resp = await fetch("/api/trainer/reset", { method: "POST" });
  const data = await resp.json();
  if (data.busy) {
    resetDemoBtn.disabled = false;
    resetDemoStatus.textContent = data.message || "Busy — try again shortly.";
    return;
  }
  setTimeout(pollResetStatus, 1500);
});
