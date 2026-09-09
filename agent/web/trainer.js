// Agentic Software Delivery — Trainer live workbench frontend.
// Talks only to our own backend (agent/web_server.py: /api/trainer/*,
// then the same generic /api/runs/{id}/events SSE stream used by the
// Control Plane, since a trainer run is stored in the same RUNS dict).

const requirementInput = document.getElementById("requirement-input");
const submitBtn = document.getElementById("submit-btn");
const statusBadge = document.getElementById("status-badge");
const examplesList = document.getElementById("examples-list");
const assessmentPanel = document.getElementById("assessment-panel");
const assessmentBody = document.getElementById("assessment-body");
const activityPanel = document.getElementById("activity-panel");
const activityList = document.getElementById("activity-list");
const verificationPanel = document.getElementById("verification-panel");
const verificationList = document.getElementById("verification-list");
const deployPanel = document.getElementById("deploy-panel");
const deployBody = document.getElementById("deploy-body");
const resultPanel = document.getElementById("result-panel");
const resultBanner = document.getElementById("result-banner");
const resultText = document.getElementById("result-text");

const EXAMPLES = [
  'Add a small "Agent Demo" status badge near the page title',
  "Add a read-only customer-count endpoint and show the count on the page",
  "Change the wording of the Create Customer success message",
  'Add a small "Powered by Agentic Delivery" footer line to the page',
];

let eventSource = null;
let runState = { approvalDecision: null, applySucceeded: null, compileResult: null, testResult: null };

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

function setStatus(stage) {
  statusBadge.textContent = stage;
  const map = {
    IDLE: "status-idle", COMPLETED: "status-completed", FAILED: "status-failed",
  };
  statusBadge.className = "status-badge " + (map[stage] || "status-running");
}

function resetPanels() {
  assessmentPanel.hidden = true;
  activityPanel.hidden = true;
  verificationPanel.hidden = true;
  deployPanel.hidden = true;
  resultPanel.hidden = true;
  activityList.innerHTML = "";
  verificationList.innerHTML = "";
  runState = { approvalDecision: null, applySucceeded: null, compileResult: null, testResult: null };
}

function renderAssessment(a, blocked) {
  assessmentPanel.hidden = false;
  let html = `<div class="kv"><span class="k">Complexity</span><span class="v">${esc(a.complexity)}</span></div>`;
  html += `<div class="kv"><span class="k">Risk</span><span class="v">${esc(a.risk)}</span></div>`;
  html += `<div class="kv"><span class="k">Decision</span><span class="v">${blocked ? '<strong style="color:var(--red)">REQUIRES OWNER REVIEW / TOO LARGE FOR DEMO</strong>' : '<strong style="color:var(--green)">AUTO-EXECUTE</strong>'}</span></div>`;
  html += `<div class="kv"><span class="k">Reason</span><span class="v">${esc(a.reason)}</span></div>`;
  if (blocked && a.suggested_alternatives && a.suggested_alternatives.length) {
    html += `<p class="hint" style="margin-top:0.8rem;">For a quick live demonstration, choose one:</p><div id="alt-list"></div>`;
  }
  assessmentBody.innerHTML = html;

  if (blocked && a.suggested_alternatives && a.suggested_alternatives.length) {
    const altList = document.getElementById("alt-list");
    a.suggested_alternatives.forEach(alt => {
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

function closeEventSource() {
  if (eventSource) { eventSource.close(); eventSource = null; }
}

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
    return;
  }
  subscribeToRun(data.run_id);
}

function subscribeToRun(runId) {
  closeEventSource();
  eventSource = new EventSource(`/api/runs/${runId}/events`);

  eventSource.addEventListener("risk_assessment", (e) => {
    const data = JSON.parse(e.data);
    renderAssessment(data, false);
  });

  eventSource.addEventListener("stage", (e) => {
    const data = JSON.parse(e.data);
    setStatus(data.stage);
    addActivityLine(`<span class="stage-marker">— ${esc(data.stage)} —</span>`);
    if (data.stage === "COMPLETED" || data.stage === "FAILED") {
      submitBtn.disabled = false;
      closeEventSource();
    }
  });

  eventSource.addEventListener("tool_call", (e) => {
    const data = JSON.parse(e.data);
    addActivityLine(`<span class="tool-name">${esc(data.tool)}</span>(${esc(data.input_summary)})`);
  });

  eventSource.addEventListener("tool_result", (e) => {
    const data = JSON.parse(e.data);
    const cls = data.success ? "ok" : "err";
    const label = data.success ? "OK" : "ERROR";
    addActivityLine(`&nbsp;&nbsp;→ <span class="${cls}">${label}</span> · ${data.duration_ms}ms`);
    if (data.tool === "apply_approved_source_change") runState.applySucceeded = data.success;
    if (data.tool === "run_controlled_compile") { runState.compileResult = data; addVerificationLine("BUILD (mvn compile)", data); }
    if (data.tool === "run_controlled_tests") { runState.testResult = data; addVerificationLine("TESTS (mvn test)", data); }
  });

  eventSource.addEventListener("approval_decision", (e) => {
    const data = JSON.parse(e.data);
    addActivityLine(`<span class="hint">Approval: ${esc(data.decision)} — decided by: ${esc(data.decided_by || "policy")}</span>`);
  });

  eventSource.addEventListener("commit", (e) => {
    const data = JSON.parse(e.data);
    deployPanel.hidden = false;
    deployBody.innerHTML = `<div class="kv"><span class="k">Production commit</span><span class="v"><code>${esc(data.sha)}</code></span></div><div class="kv"><span class="k">Changed file</span><span class="v"><code>${esc(data.path)}</code></span></div>`;
  });

  eventSource.addEventListener("deployment", (e) => {
    const data = JSON.parse(e.data);
    deployPanel.hidden = false;
    const verifiedBadge = data.verified ? '<span style="color:var(--green)">VERIFIED (HTTP 200)</span>' : '<span style="color:var(--red)">NOT VERIFIED</span>';
    deployBody.innerHTML += `<div class="kv"><span class="k">Public app</span><span class="v"><a href="${esc(data.public_url)}" target="_blank" rel="noopener">${esc(data.public_url)}</a></span></div>`;
    deployBody.innerHTML += `<div class="kv"><span class="k">HTTP status</span><span class="v">${esc(data.http_status)}</span></div>`;
    deployBody.innerHTML += `<div class="kv"><span class="k">Content changed from baseline</span><span class="v">${data.content_changed_from_baseline ? "yes" : "no"}</span></div>`;
    deployBody.innerHTML += `<div class="kv"><span class="k">Verification</span><span class="v">${verifiedBadge}</span></div>`;
  });

  eventSource.addEventListener("final_result", (e) => {
    const data = JSON.parse(e.data);
    resultPanel.hidden = false;
    const failed = runState.applySucceeded === false || (runState.compileResult && !runState.compileResult.success) || (runState.testResult && !runState.testResult.success);
    resultBanner.textContent = failed ? "FAILED" : "DEPLOYED SUCCESSFULLY";
    resultBanner.className = failed ? "failed" : "success";
    resultText.textContent = data.text;
  });

  eventSource.addEventListener("error", (e) => {
    try {
      const data = JSON.parse(e.data);
      addActivityLine(`<span class="err">ERROR: ${esc(data.message)}</span>`);
      resultPanel.hidden = false;
      resultBanner.textContent = "FAILED";
      resultBanner.className = "failed";
      resultText.textContent = data.message;
    } catch (_) { /* connection-level SSE error, ignore */ }
  });
}

submitBtn.addEventListener("click", submit);
