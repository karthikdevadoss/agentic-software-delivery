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
const stageChecklist = document.getElementById("stage-checklist");
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

const EXAMPLES = [
  'Add a small "Agent Demo" status badge near the page title',
  "Change the wording of the Create Customer success message",
  'Add a small "Powered by Agentic Delivery" footer line to the page',
  "Change the page title text",
  "Change a button label to something clearer",
  "Add a short informational helper line under the page title",
];

// The real workflow stages a trainer run can pass through, in order.
// Must stay in sync with agent/web_server.py's TERMINAL_RUN_STATES and
// the stage strings it actually emits (STAGE_LABELS + trainer-specific
// COMMITTING/DEPLOYING/VERIFYING PRODUCTION) — this is a UI-side
// consumer of that state machine, see CLAUDE.md's state-drift rule.
const WORKFLOW_STAGES = [
  { key: "RECEIVED", label: "Requirement received" },
  { key: "RISK_ASSESSMENT", label: "Risk assessment" },
  { key: "REPOSITORY INVESTIGATION", label: "Repository investigation" },
  { key: "PROPOSING CHANGE", label: "Proposing change" },
  { key: "APPLYING CHANGE", label: "Applying change" },
  { key: "BUILDING", label: "Building (compile)" },
  { key: "TESTING", label: "Testing" },
  { key: "COMMITTING", label: "Committing" },
  { key: "DEPLOYING", label: "Deploying" },
  { key: "VERIFYING PRODUCTION", label: "Verifying production" },
];
const TERMINAL_STAGES = new Set(["COMPLETED", "FAILED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN"]);

// Stages where long silence is EXPECTED (waiting on an external system),
// not a sign anything is wrong — calibrated from real observed durations
// this session (a genuine Railway cold-build deploy took ~11.5-19 min).
// Anything else uses a much shorter default before flagging no-progress,
// since those steps normally finish in seconds.
const STAGE_MAX_QUIET_SECONDS = { DEPLOYING: 20 * 60, TESTING: 120, BUILDING: 90 };
const DEFAULT_MAX_QUIET_SECONDS = 30;

const POLL_INTERVAL_MS = 3000;
const SSE_LIVE_WINDOW_MS = 6000; // how recently an SSE message must have arrived to call the transport "live"

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

EXAMPLES.forEach(ex => {
  const btn = document.createElement("button");
  btn.className = "secondary example-btn";
  btn.textContent = ex;
  btn.addEventListener("click", () => { requirementInput.value = ex; });
  examplesList.appendChild(btn);
});

// ---- Target application (shown before any requirement is submitted) -----
// Fetched from the backend rather than hardcoded here, so this can never
// drift from the exact URL the backend itself deploys to and verifies
// against (see agent/web_server.py's TARGET_APPLICATION/PUBLIC_CUSTOMER_APP_URL).
let targetApp = null;

async function loadTargetApp() {
  try {
    const resp = await fetch("/api/target-app");
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    targetApp = await resp.json();
    targetAppBody.innerHTML =
      `<div class="kv"><span class="k">Application</span><span class="v">${esc(targetApp.name)}</span></div>` +
      `<div class="kv"><span class="k">Environment</span><span class="v">${esc(targetApp.environment)}</span></div>` +
      `<p class="hint">${esc(targetApp.description)}</p>` +
      `<a class="secondary open-app-link" href="${esc(targetApp.url)}" target="_blank" rel="noopener">OPEN CURRENT CUSTOMER APP ↗</a>`;
  } catch (_) {
    targetAppBody.innerHTML = `<p class="hint err">Could not load target application info. Try reloading the page.</p>`;
  }
}
loadTargetApp();

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
  stageChecklist.innerHTML = "";
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
  let html = "";
  if (blocked) {
    html += `<p class="owner-auth-notice">This change requires Owner Authorization. Larger authorized builds are not enabled in this preview yet.</p>`;
  }
  html += `<div class="kv"><span class="k">Complexity</span><span class="v">${esc(a.complexity)}</span></div>`;
  html += `<div class="kv"><span class="k">Risk</span><span class="v">${esc(a.risk)}</span></div>`;
  html += `<div class="kv"><span class="k">Decision</span><span class="v">${blocked ? '<strong style="color:var(--red)">REQUIRES OWNER AUTHORIZATION</strong>' : '<strong style="color:var(--green)">AUTO-EXECUTE</strong>'}</span></div>`;
  html += `<div class="kv"><span class="k">Reason</span><span class="v">${esc(a.reason)}</span></div>`;
  if (blocked) {
    html += `<p class="hint" style="margin-top:0.8rem;">Try one of these safe, bounded changes instead:</p><div id="alt-list"></div>`;
  } else if (a.estimate) {
    html += renderEstimateBlock(a.estimate);
  }
  assessmentBody.innerHTML = html;

  if (blocked) {
    const altList = document.getElementById("alt-list");
    const alternatives = (a.suggested_alternatives && a.suggested_alternatives.length)
      ? a.suggested_alternatives : EXAMPLES;
    alternatives.forEach(alt => {
      const btn = document.createElement("button");
      btn.className = "secondary example-btn";
      btn.textContent = "USE: " + alt;
      btn.addEventListener("click", () => { requirementInput.value = alt; submit(); });
      altList.appendChild(btn);
    });
  }
}

function fmtUsd(n) {
  if (n === null || n === undefined) return "—";
  return "$" + n.toFixed(n < 0.01 ? 4 : 2);
}

function renderEstimateBlock(estimate) {
  let html = `<div class="estimate-box"><p class="estimate-label">ESTIMATED EXECUTION</p>`;
  if (!estimate.available) {
    html += `<p class="hint">${esc(estimate.reason || "ESTIMATE NOT AVAILABLE.")}</p>`;
    html += `</div>`;
    return html;
  }
  const [tokLow, tokHigh] = estimate.estimated_total_tokens_range;
  html += `<div class="kv"><span class="k">Complexity</span><span class="v">${esc(estimate.complexity)}</span></div>`;
  html += `<div class="kv"><span class="k">Risk</span><span class="v">${esc(estimate.risk)}</span></div>`;
  html += `<div class="kv"><span class="k">Estimated AI token range</span><span class="v">${tokLow.toLocaleString()} – ${tokHigh.toLocaleString()} tokens (ESTIMATED)</span></div>`;
  if (estimate.estimated_cost_range_usd) {
    const [costLow, costHigh] = estimate.estimated_cost_range_usd;
    html += `<div class="kv"><span class="k">Estimated API cost range</span><span class="v">${fmtUsd(costLow)} – ${fmtUsd(costHigh)} (ESTIMATED)</span></div>`;
  } else {
    html += `<div class="kv"><span class="k">Estimated API cost range</span><span class="v">ESTIMATE NOT AVAILABLE (no pricing for ${esc(estimate.provider)}/${esc(estimate.model)})</span></div>`;
  }
  html += `<div class="kv"><span class="k">Estimate confidence</span><span class="v">${esc(estimate.confidence)}</span></div>`;
  html += `<p class="hint estimate-basis">Basis: ${esc(estimate.basis)} · method ${esc(estimate.method_version)}</p>`;
  html += `</div>`;
  return html;
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

function renderStageChecklist() {
  if (!run) return;
  const terminal = TERMINAL_STAGES.has(run.status);
  // Once terminal, any workflow stage never reached is genuinely never
  // going to run (e.g. TESTING when the model didn't call it, or
  // everything past BUILDING for a NO_CHANGE_NEEDED outcome) — show that
  // truthfully as skipped, not as a perpetual "not yet".
  const lastSeenIndex = WORKFLOW_STAGES.reduce(
    (acc, s, i) => (run.stagesSeen.has(s.key) ? i : acc), -1);

  stageChecklist.innerHTML = WORKFLOW_STAGES.map((s, i) => {
    const seen = run.stagesSeen.has(s.key);
    const isCurrent = s.key === run.currentStage && !terminal;
    let cls, mark, note = "";
    if (seen && !isCurrent) { cls = "done"; mark = "✓"; }
    else if (isCurrent) { cls = "active"; mark = "●"; }
    else if (terminal && i > lastSeenIndex) { cls = "skipped"; mark = "○"; note = '<span class="skip-note">SKIPPED / NOT REQUIRED</span>'; }
    else { cls = "pending"; mark = "○"; }
    return `<li class="${cls}"><span class="mark">${mark}</span><span>${esc(s.label)}</span>${note}</li>`;
  }).join("");
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
      run.lastEventTs = evt.ts;
      run.stageStartedTs = evt.ts;
      setStatus(evt.stage);
      addActivityLine(`<span class="stage-marker">— ${esc(evt.stage)} —</span>`);
      if (TERMINAL_STAGES.has(evt.stage)) {
        renderTerminalOutcome();
        finishRun();
      }
      break;
    case "no_change_needed":
      addActivityLine(`<span class="hint">${esc(evt.reason)}</span>`);
      run.lastEventTs = evt.ts;
      break;
    case "tool_call":
      addActivityLine(`<span class="tool-name">${esc(evt.tool)}</span>(${esc(evt.input_summary)})`);
      run.lastEventTs = evt.ts;
      break;
    case "tool_result": {
      const cls = evt.success ? "ok" : "err";
      const label = evt.success ? "OK" : "ERROR";
      addActivityLine(`&nbsp;&nbsp;→ <span class="${cls}">${label}</span> · ${evt.duration_ms}ms`);
      if (evt.tool === "apply_approved_source_change") verificationState.applySucceeded = evt.success;
      if (evt.tool === "run_controlled_compile") { verificationState.compileResult = evt; addVerificationLine("BUILD (mvn compile)", evt); }
      if (evt.tool === "run_controlled_tests") { verificationState.testResult = evt; addVerificationLine("TESTS (mvn test)", evt); }
      run.lastEventTs = evt.ts;
      break;
    }
    case "approval_decision":
      addActivityLine(`<span class="hint">Approval: ${esc(evt.decision)} — decided by: ${esc(evt.decided_by || "policy")}</span>`);
      run.lastEventTs = evt.ts;
      break;
    case "commit":
      deployPanel.hidden = false;
      run.commitInfo = evt;
      deployBody.innerHTML = `<div class="kv"><span class="k">Production commit</span><span class="v"><code>${esc(evt.sha)}</code></span></div><div class="kv"><span class="k">Changed file</span><span class="v"><code>${esc(evt.path)}</code></span></div>`;
      run.lastEventTs = evt.ts;
      break;
    case "deployment": {
      deployPanel.hidden = false;
      run.deploymentInfo = evt;
      const verifiedBadge = evt.verified ? '<span style="color:var(--green)">VERIFIED (HTTP 200)</span>' : '<span style="color:var(--red)">NOT VERIFIED</span>';
      deployBody.innerHTML += `<div class="kv"><span class="k">Public app</span><span class="v"><a href="${esc(evt.public_url)}" target="_blank" rel="noopener">${esc(evt.public_url)}</a></span></div>`;
      deployBody.innerHTML += `<div class="kv"><span class="k">HTTP status</span><span class="v">${esc(evt.http_status)}</span></div>`;
      deployBody.innerHTML += `<div class="kv"><span class="k">Content changed from baseline</span><span class="v">${evt.content_changed_from_baseline ? "yes" : "no"}</span></div>`;
      deployBody.innerHTML += `<div class="kv"><span class="k">Verification</span><span class="v">${verifiedBadge}</span></div>`;
      run.lastEventTs = evt.ts;
      break;
    }
    case "final_result":
      resultPanel.hidden = false;
      run.finalResultText = evt.text;
      // The terminal "stage" event (which triggers renderTerminalOutcome)
      // arrives BEFORE final_result on the COMPLETED/NO_CHANGE_NEEDED
      // paths — refresh just the text here so it isn't left blank.
      if (TERMINAL_STAGES.has(run.status)) resultText.textContent = run.finalResultText;
      run.lastEventTs = evt.ts;
      break;
    case "error":
      addActivityLine(`<span class="err">ERROR: ${esc(evt.message)}</span>`);
      resultPanel.hidden = false;
      run.lastErrorMessage = evt.message;
      if (TERMINAL_STAGES.has(run.status)) resultText.textContent = run.lastErrorMessage;
      run.lastEventTs = evt.ts;
      break;
    case "usage_summary":
      run.usageSummary = evt;
      renderUsageSummary(evt);
      run.lastEventTs = evt.ts;
      break;
  }
  renderStageChecklist();
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
  evidenceHtml += `<a class="open-production-btn" href="${esc(buttonUrl)}" target="_blank" rel="noopener">[ ${esc(outcome.buttonLabel)} ]</a>`;
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
   "approval_decision", "commit", "deployment", "final_result", "error", "usage_summary"]
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
  const nowS = Date.now() / 1000;
  const quietS = run.lastEventTs ? nowS - run.lastEventTs : 0;
  const maxQuiet = STAGE_MAX_QUIET_SECONDS[run.currentStage] || DEFAULT_MAX_QUIET_SECONDS;
  if (run.currentStage === "DEPLOYING" && quietS > 5) return "WAITING FOR EXTERNAL SYSTEM (Railway)";
  if (quietS > maxQuiet) return "STALLED / NO RECENT PROGRESS";
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
  const nowS = Date.now() / 1000;
  rsStageElapsed.textContent = run.stageStartedTs ? fmtDuration(nowS - run.stageStartedTs) : "—";
  rsTotalElapsed.textContent = runStartedAtMs ? fmtDuration((Date.now() - runStartedAtMs) / 1000) : "—";
  rsLastActivity.textContent = run.lastEventTs ? `${fmtDuration(nowS - run.lastEventTs)} ago` : "—";
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
  setStatus("STARTING");

  const resp = await fetch("/api/trainer/runs", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  });
  const data = await resp.json();
  if (data.blocked) {
    renderAssessment(data.assessment, true);
    setStatus("IDLE");
    submitBtn.disabled = false;
    runStatusPanel.hidden = true;
    return;
  }

  run = {
    id: data.run_id, seenEventKeys: new Set(), stagesSeen: new Set(["RECEIVED"]),
    currentStage: null, status: "STARTING", lastEventTs: null,
    stageStartedTs: null, finished: false,
    finalResultText: null, lastErrorMessage: null, usageSummary: null,
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
