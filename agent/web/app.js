// Agentic Software Delivery — Control Plane frontend.
// Plain JS, no framework. Talks only to our own backend (agent/web_server.py).

const DEFAULT_REQUIREMENT = `This is an infrastructure verification task, not a business feature.

Create exactly one new file: a minimal placeholder JUnit test class at
app/src/test/java/com/example/customer/V41BoundaryDemoTest.java, in package
com.example.customer, containing an empty public class named
V41BoundaryDemoTest (no test methods needed - this only verifies the
propose/approve/apply/compile pipeline end to end).

Do not modify any existing file. Do not touch CustomerController,
CustomerService, CustomerRepository, or Customer. Do not implement email
update functionality. This is purely a safe, additive placeholder file to
prove the execution pipeline works.`;

const requirementInput = document.getElementById("requirement-input");
const startBtn = document.getElementById("start-btn");
const mockBtn = document.getElementById("mock-btn");
const statusBadge = document.getElementById("status-badge");
const activityPanel = document.getElementById("activity-panel");
const activityList = document.getElementById("activity-list");
const proposalPanel = document.getElementById("proposal-panel");
const proposalId = document.getElementById("proposal-id");
const proposalPath = document.getElementById("proposal-path");
const proposalDiff = document.getElementById("proposal-diff");
const approveBtn = document.getElementById("approve-btn");
const rejectBtn = document.getElementById("reject-btn");
const approvalResult = document.getElementById("approval-result");
const verificationPanel = document.getElementById("verification-panel");
const verificationList = document.getElementById("verification-list");
const resultPanel = document.getElementById("result-panel");
const resultBanner = document.getElementById("result-banner");
const resultText = document.getElementById("result-text");

requirementInput.value = DEFAULT_REQUIREMENT;

let currentRunId = null;
let currentEditId = null;
let eventSource = null;

// Real, structured run state — the final banner is derived from THIS, never
// from sniffing the agent's free-text summary. Only what actually happened.
let runState = {};

function resetRunState() {
  runState = {
    approvalDecision: null, // "approve" | "reject" | null
    applySucceeded: null,   // true | false | null (null = not attempted)
    compileResult: null,    // {success, duration_ms, summary} | null
    testResult: null,       // {success, duration_ms, summary} | null
    backendError: null,     // string | null (an exception in the run itself)
  };
}

function setStatus(stage) {
  statusBadge.textContent = stage;
  statusBadge.className = "status-badge " + statusClass(stage);
}

function statusClass(stage) {
  if (stage === "COMPLETED") return "status-completed";
  if (stage === "FAILED") return "status-failed";
  if (stage === "WAITING FOR HUMAN APPROVAL") return "status-waiting";
  if (stage === "IDLE") return "status-idle";
  return "status-running";
}

// Only auto-follow the live log if the user hasn't scrolled away to read
// something else — never fight a manual scroll (desired behavior: "if the
// human manually scrolls away, do not fight the human").
function isNearBottom(el, thresholdPx = 40) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= thresholdPx;
}

function addActivityLine(html) {
  const shouldFollow = isNearBottom(activityList);
  const li = document.createElement("li");
  li.innerHTML = html;
  activityList.appendChild(li);
  if (shouldFollow) {
    activityList.scrollTop = activityList.scrollHeight;
  }
}

function addVerificationLine(label, result) {
  verificationPanel.hidden = false;
  const li = document.createElement("li");
  const statusText = result.success ? "PASS" : "FAIL";
  const cls = result.success ? "ok" : "err";
  const mark = result.success ? "✓" : "✗";
  let html = `<div><strong>${label}</strong></div>`;
  html += `<div>${mark} <span class="${cls}">${statusText}</span> &middot; Duration: ${(result.duration_ms / 1000).toFixed(1)}s</div>`;
  if (result.summary) {
    html += `<pre class="verification-summary">${escapeHtml(result.summary)}</pre>`;
  }
  li.innerHTML = html;
  verificationList.appendChild(li);
}

function resetPanels() {
  activityList.innerHTML = "";
  verificationList.innerHTML = "";
  proposalPanel.hidden = true;
  verificationPanel.hidden = true;
  resultPanel.hidden = true;
  approvalResult.textContent = "";
  approveBtn.disabled = false;
  rejectBtn.disabled = false;
  resetRunState();
}

function closeEventSource() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

startBtn.addEventListener("click", async () => {
  const requirement = requirementInput.value.trim();
  if (!requirement) return;

  resetPanels();
  activityPanel.hidden = false;
  startBtn.disabled = true;
  mockBtn.disabled = true;
  setStatus("STARTING");

  const resp = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirement }),
  });
  if (!resp.ok) {
    setStatus("FAILED");
    startBtn.disabled = false;
    mockBtn.disabled = false;
    return;
  }
  const data = await resp.json();
  currentRunId = data.run_id;
  subscribeToRun(currentRunId);
});

mockBtn.addEventListener("click", async () => {
  resetPanels();
  activityPanel.hidden = false;
  startBtn.disabled = true;
  mockBtn.disabled = true;
  setStatus("STARTING");

  const resp = await fetch("/api/runs/mock", { method: "POST" });
  const data = await resp.json();
  currentRunId = data.run_id;
  subscribeToRun(currentRunId);
});

function subscribeToRun(runId) {
  closeEventSource();
  eventSource = new EventSource(`/api/runs/${runId}/events`);

  eventSource.addEventListener("stage", (e) => {
    const data = JSON.parse(e.data);
    setStatus(data.stage);
    addActivityLine(`<span class="stage-marker">— ${data.stage} —</span>`);
    if (data.stage === "COMPLETED" || data.stage === "FAILED") {
      startBtn.disabled = false;
      mockBtn.disabled = false;
      // Root fix for the scroll-jump bug: the backend's SSE stream ends
      // naturally here, and a plain EventSource auto-reconnects on any
      // dropped connection, replaying every event again from the start.
      // Closing it explicitly on the terminal stage is what actually
      // stops that — nothing after this point should move the viewport.
      closeEventSource();
    }
  });

  eventSource.addEventListener("tool_call", (e) => {
    const data = JSON.parse(e.data);
    addActivityLine(
      `<span class="tool-name">${escapeHtml(data.tool)}</span>(${escapeHtml(data.input_summary)})`
    );
  });

  eventSource.addEventListener("tool_result", (e) => {
    const data = JSON.parse(e.data);
    const cls = data.success ? "ok" : "err";
    const label = data.success ? "OK" : "ERROR";
    addActivityLine(
      `&nbsp;&nbsp;→ <span class="${cls}">${label}</span> · ${data.duration_ms}ms · ${data.result_size} chars`
    );

    if (data.tool === "apply_approved_source_change") {
      runState.applySucceeded = data.success;
    }
    if (data.tool === "run_controlled_compile") {
      runState.compileResult = data;
      addVerificationLine("BUILD (mvn compile)", data);
    }
    if (data.tool === "run_controlled_tests") {
      runState.testResult = data;
      addVerificationLine("TESTS (mvn test)", data);
    }
  });

  eventSource.addEventListener("proposal", (e) => {
    const data = JSON.parse(e.data);
    currentEditId = data.edit_id;
    proposalId.textContent = data.edit_id;
    proposalPath.textContent = data.path;
    proposalDiff.textContent = data.diff || "(new file, no prior content)";
    proposalPanel.hidden = false;
    approveBtn.disabled = false;
    rejectBtn.disabled = false;
    approvalResult.textContent = "";
    proposalPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  eventSource.addEventListener("approval_decision", (e) => {
    const data = JSON.parse(e.data);
    runState.approvalDecision = data.decision;
    approvalResult.textContent =
      data.decision === "approve"
        ? "Approved by human operator."
        : "Rejected by human operator.";
    approveBtn.disabled = true;
    rejectBtn.disabled = true;
  });

  eventSource.addEventListener("final_result", (e) => {
    const data = JSON.parse(e.data);
    resultPanel.hidden = false;
    renderFinalBanner(data.text);
  });

  eventSource.addEventListener("error", (e) => {
    try {
      const data = JSON.parse(e.data);
      runState.backendError = data.message;
      addActivityLine(`<span class="err">ERROR: ${escapeHtml(data.message)}</span>`);
    } catch (_) {
      /* connection-level SSE error, ignore */
    }
  });
}

// Derives the final banner from ACTUAL structured events (approval,
// apply, compile, test) — never from guessing at the agent's free-text
// wording. A "green" banner requires every step that actually ran to have
// actually succeeded.
function renderFinalBanner(finalText) {
  let succeeded;
  let label;

  if (runState.backendError) {
    succeeded = false;
    label = "FAILED";
  } else if (runState.approvalDecision === "reject") {
    succeeded = false;
    label = "REJECTED — NO CHANGE APPLIED";
  } else if (runState.approvalDecision === "approve" && runState.applySucceeded === false) {
    succeeded = false;
    label = "APPLY FAILED";
  } else if (runState.compileResult && runState.compileResult.success === false) {
    succeeded = false;
    label = "BUILD FAILED";
  } else if (runState.testResult && runState.testResult.success === false) {
    succeeded = false;
    label = "TESTS FAILED";
  } else if (runState.approvalDecision === "approve" && runState.applySucceeded === true) {
    succeeded = true;
    label = "VERIFIED SUCCESS";
  } else {
    // No proposal was ever approved+applied in this run (e.g. the agent
    // only planned/investigated, or never reached a proposal) — that's
    // not a failure, just not a verified change.
    succeeded = null;
    label = "COMPLETED — NO CHANGE APPLIED";
  }

  resultBanner.textContent = label;
  resultBanner.className = succeeded === false ? "failed" : succeeded === true ? "success" : "neutral";
  resultText.textContent = finalText;
}

approveBtn.addEventListener("click", () => sendDecision("approve"));
rejectBtn.addEventListener("click", () => sendDecision("reject"));

async function sendDecision(decision) {
  approveBtn.disabled = true;
  rejectBtn.disabled = true;
  await fetch(`/api/runs/${currentRunId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edit_id: currentEditId, decision }),
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}
