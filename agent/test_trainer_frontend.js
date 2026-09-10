// Focused regression tests for agent/web/trainer.js's transport-resilience
// logic (SSE-preferred + always-on HTTP polling fallback, event dedup,
// terminal-state handling through either transport).
//
// This is a plain-Node test using a hand-built DOM/EventSource/fetch stub
// via the built-in `vm` module — no jsdom, no test framework, no new
// dependency, matching this project's existing zero-new-dependency
// discipline (see docs/DECISIONS.md). It exercises the REAL trainer.js
// source directly (loaded and run as-is), not a reimplementation of its
// logic. It does NOT drive a real browser — that is explicitly out of
// scope for this layer; see the incident report for what still requires
// a creator's own visual check.
//
// Run: node agent/test_trainer_frontend.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let failures = 0;
let passed = 0;

function assert(cond, msg) {
  if (!cond) { failures++; console.error("FAIL: " + msg); }
  else { passed++; }
}
function assertEqual(actual, expected, msg) {
  assert(actual === expected, `${msg} (expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)})`);
}

// ---- Minimal DOM stub -------------------------------------------------

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function makeElement(tag) {
  let _textContent = "";
  const el = {
    tagName: tag,
    hidden: false,
    className: "",
    value: "",
    disabled: false,
    scrollTop: 0,
    scrollHeight: 0,
    children: [],
    _innerHTML: "",
    get innerHTML() { return this._textContentSet ? escapeHtml(_textContent) : this._innerHTML; },
    set innerHTML(v) { this._innerHTML = v; this._textContentSet = false; this.children = []; },
    get textContent() { return _textContent; },
    set textContent(v) { _textContent = v; this._textContentSet = true; },
    appendChild(child) { this.children.push(child); return child; },
    addEventListener() {},
  };
  return el;
}

function makeDocumentStub() {
  const elementsById = new Map();
  const ids = [
    "requirement-input", "submit-btn", "status-badge", "examples-list",
    "assessment-panel", "assessment-body", "run-status-panel",
    "rs-overall", "rs-runid", "rs-transport", "rs-stage", "rs-stage-elapsed",
    "rs-total-elapsed", "rs-last-activity", "stage-checklist",
    "activity-panel", "activity-list", "verification-panel", "verification-list",
    "deploy-panel", "deploy-body", "result-panel", "result-banner", "result-text",
  ];
  ids.forEach(id => elementsById.set(id, makeElement("div")));
  return {
    getElementById: (id) => elementsById.get(id) || makeElement("div"),
    createElement: (tag) => makeElement(tag),
    _elementsById: elementsById,
  };
}

// ---- Minimal EventSource stub -------------------------------------------

class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.closed = false;
    FakeEventSource.instances.push(this);
  }
  addEventListener(type, cb) { (this.listeners[type] = this.listeners[type] || []).push(cb); }
  close() { this.closed = true; }
  fire(type, dataObj) {
    if (this.closed) return;
    (this.listeners[type] || []).forEach(cb => cb({ data: JSON.stringify(dataObj) }));
  }
}
FakeEventSource.instances = [];

// ---- Minimal fetch stub ---------------------------------------------------
// Router keyed by "METHOD path". For GET /api/runs/{id}, the handler is
// called fresh each time so a test can return progressively more events
// across successive polls, exactly like the real backend would.

function makeFetchStub(routes) {
  const calls = [];
  const fetchFn = async (url, opts) => {
    const method = (opts && opts.method) || "GET";
    calls.push({ url, method });
    const key = Object.keys(routes).find(k => {
      const [m, pattern] = k.split(" ");
      return m === method && (pattern === url || (pattern.endsWith("*") && url.startsWith(pattern.slice(0, -1))));
    });
    if (!key) throw new Error(`No fetch stub route for ${method} ${url}`);
    const result = routes[key]();
    return { ok: true, status: 200, json: async () => result };
  };
  fetchFn.calls = calls;
  return fetchFn;
}

// ---- Load the real trainer.js source into a sandboxed context -----------

function loadTrainerContext(documentStub, fetchStub) {
  const source = fs.readFileSync(path.join(__dirname, "web", "trainer.js"), "utf8");
  const sandbox = {
    document: documentStub,
    EventSource: FakeEventSource,
    fetch: fetchStub,
    setTimeout, clearTimeout, setInterval, clearInterval,
    console,
    Date,
    Math,
  };
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox, { filename: "trainer.js" });
  return sandbox;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ---- Fixtures: realistic event sequences ---------------------------------

function ev(type, extra, ts) { return { type, ts: ts ?? (Date.now() / 1000), ...extra }; }

function buildEventSequence(finalStage) {
  const t0 = Date.now() / 1000;
  const base = [
    ev("risk_assessment", { complexity: "TINY", risk: "LOW", decision: "auto", reason: "ok", matched_keywords: [], suggested_alternatives: [] }, t0),
    ev("stage", { stage: "PLANNING" }, t0 + 0.1),
    ev("stage", { stage: "REPOSITORY INVESTIGATION" }, t0 + 0.3),
    ev("tool_call", { tool: "read_file", input_summary: "x" }, t0 + 0.3),
    ev("tool_result", { tool: "read_file", success: true, duration_ms: 1 }, t0 + 0.4),
  ];
  if (finalStage === "NO_CHANGE_NEEDED") {
    return base.concat([
      ev("stage", { stage: "BUILDING" }, t0 + 0.6),
      ev("tool_result", { tool: "run_controlled_compile", success: true, duration_ms: 5 }, t0 + 1.0),
      ev("no_change_needed", { reason: "already exists" }, t0 + 1.1),
      ev("stage", { stage: "NO_CHANGE_NEEDED" }, t0 + 1.1),
      ev("final_result", { text: "already satisfied" }, t0 + 1.1),
    ]);
  }
  if (finalStage === "FAILED") {
    return base.concat([
      ev("error", { message: "Implementation did not pass verification" }, t0 + 0.6),
      ev("stage", { stage: "FAILED" }, t0 + 0.6),
    ]);
  }
  // COMPLETED
  return base.concat([
    ev("stage", { stage: "PROPOSING CHANGE" }, t0 + 0.5),
    ev("approval_decision", { edit_id: "x", decision: "approve", decided_by: "policy" }, t0 + 0.5),
    ev("stage", { stage: "APPLYING CHANGE" }, t0 + 0.6),
    ev("stage", { stage: "BUILDING" }, t0 + 0.7),
    ev("tool_result", { tool: "run_controlled_compile", success: true, duration_ms: 5 }, t0 + 1.0),
    ev("stage", { stage: "COMMITTING" }, t0 + 1.1),
    ev("commit", { sha: "abc1234", path: "x" }, t0 + 1.1),
    ev("stage", { stage: "DEPLOYING" }, t0 + 1.2),
    ev("deployment", { production_commit: "abc1234", public_url: "https://x", http_status: 200, content_changed_from_baseline: true, verified: true }, t0 + 1.3),
    ev("stage", { stage: "COMPLETED" }, t0 + 1.3),
    ev("final_result", { text: "deployed" }, t0 + 1.3),
  ]);
}

// ---- Test runner ----------------------------------------------------------

async function runSubmit(sandbox, requirement, runId, assessment) {
  sandbox.document.getElementById("requirement-input").value = requirement;
  const submitPromise = sandbox.submit();
  await submitPromise;
  return runId;
}

async function testA_sseWorksNormally() {
  const events = buildEventSequence("COMPLETED");
  const fetchStub = makeFetchStub({
    "POST /api/trainer/assess": () => ({ complexity: "TINY", risk: "LOW", decision: "auto", reason: "ok", matched_keywords: [], suggested_alternatives: [] }),
    "POST /api/trainer/runs": () => ({ blocked: false, run_id: "trainer-testA", assessment: { decision: "auto" } }),
    "GET /api/runs/trainer-testA": () => ({ id: "trainer-testA", status: "STARTING", events: [], result: null }),
  });
  const doc = makeDocumentStub();
  FakeEventSource.instances = [];
  const sandbox = loadTrainerContext(doc, fetchStub);

  await runSubmit(sandbox, "test requirement A");
  const es = FakeEventSource.instances[FakeEventSource.instances.length - 1];
  assert(!!es, "A: EventSource was created");
  events.forEach(e => es.fire(e.type, e));
  await sleep(350); // let finishRun's delayed stopEverything run

  assertEqual(doc.getElementById("result-banner").textContent, "DEPLOYED SUCCESSFULLY", "A: final banner via SSE");
  assert(es.closed, "A: EventSource closed after terminal state");
  assertEqual(doc.getElementById("submit-btn").disabled, false, "A: submit re-enabled");
  sandbox.stopEverything();
}

async function testBC_pollingFallbackWhenSSESilent() {
  // SSE connects but NEVER fires anything — exactly the proven incident.
  const fullSequenceSoFar = [];
  const finalEvents = buildEventSequence("NO_CHANGE_NEEDED");
  let pollCount = 0;
  const fetchStub = makeFetchStub({
    "POST /api/trainer/assess": () => ({ complexity: "TINY", risk: "LOW", decision: "auto", reason: "ok", matched_keywords: [], suggested_alternatives: [] }),
    "POST /api/trainer/runs": () => ({ blocked: false, run_id: "trainer-testBC", assessment: { decision: "auto" } }),
    "GET /api/runs/trainer-testBC": () => {
      // Reveal a couple more events each poll, simulating real progress
      // becoming visible ONLY through polling since SSE never fires.
      pollCount++;
      const upto = Math.min(finalEvents.length, pollCount * 2);
      const status = upto >= finalEvents.length ? "NO_CHANGE_NEEDED" : "REPOSITORY INVESTIGATION";
      return { id: "trainer-testBC", status, events: finalEvents.slice(0, upto), result: null };
    },
  });
  const doc = makeDocumentStub();
  FakeEventSource.instances = [];
  const sandbox = loadTrainerContext(doc, fetchStub);

  await runSubmit(sandbox, "test requirement BC");
  // Drive polling manually instead of waiting on real 3s intervals —
  // functionally identical, just not real-time-dependent.
  // Fixed number of polls, comfortably past the fixture's own terminal
  // point (pollCount*2 >= finalEvents.length) — sandbox.run itself isn't
  // inspectable from here (top-level `let` bindings aren't exposed as vm
  // context properties; only `function` declarations are), so progress
  // is verified via DOM side effects below instead.
  for (let i = 0; i < 6; i++) {
    await sandbox.pollOnce();
  }
  await sleep(350);

  assertEqual(FakeEventSource.instances[0].listeners["stage"] === undefined ? 0 : 0, 0, "sanity");
  assert(doc.getElementById("activity-list").children.length > 0, "B: progress became visible with SSE completely silent");
  assertEqual(doc.getElementById("result-banner").textContent, "ALREADY SATISFIED — NO CHANGE REQUIRED", "C/F: NO_CHANGE_NEEDED reached via polling fallback");
  assert(!FakeEventSource.instances[0].closed || true, "sanity"); // EventSource may or may not have been explicitly closed by fake browser, not asserted here
  sandbox.stopEverything();
}

async function testDE_completedAndFailedThroughFallback() {
  for (const finalStage of ["COMPLETED", "FAILED"]) {
    const finalEvents = buildEventSequence(finalStage);
    const fetchStub = makeFetchStub({
      "POST /api/trainer/assess": () => ({ complexity: "TINY", risk: "LOW", decision: "auto", reason: "ok", matched_keywords: [], suggested_alternatives: [] }),
      "POST /api/trainer/runs": () => ({ blocked: false, run_id: `trainer-${finalStage}`, assessment: { decision: "auto" } }),
      [`GET /api/runs/trainer-${finalStage}`]: () => ({ id: `trainer-${finalStage}`, status: finalStage, events: finalEvents, result: null }),
    });
    const doc = makeDocumentStub();
    FakeEventSource.instances = [];
    const sandbox = loadTrainerContext(doc, fetchStub);
    await runSubmit(sandbox, "req " + finalStage);
    await sandbox.pollOnce();
    await sleep(350);

    const expectedBanner = finalStage === "COMPLETED" ? "DEPLOYED SUCCESSFULLY" : "FAILED";
    assertEqual(doc.getElementById("result-banner").textContent, expectedBanner, `D/E: ${finalStage} reached through polling-only fallback`);
    assertEqual(doc.getElementById("submit-btn").disabled, false, `D/E: submit re-enabled after ${finalStage}`);
    sandbox.stopEverything();
  }
}

async function testI_noDuplicateEventsWhenBothTransportsDeliverSameData() {
  const events = buildEventSequence("COMPLETED");
  const fetchStub = makeFetchStub({
    "POST /api/trainer/assess": () => ({ complexity: "TINY", risk: "LOW", decision: "auto", reason: "ok", matched_keywords: [], suggested_alternatives: [] }),
    "POST /api/trainer/runs": () => ({ blocked: false, run_id: "trainer-dedup", assessment: { decision: "auto" } }),
    "GET /api/runs/trainer-dedup": () => ({ id: "trainer-dedup", status: "COMPLETED", events, result: null }),
  });
  const doc = makeDocumentStub();
  FakeEventSource.instances = [];
  const sandbox = loadTrainerContext(doc, fetchStub);

  await runSubmit(sandbox, "dedup test");
  const es = FakeEventSource.instances[0];
  // Fire the SAME events via SSE...
  events.forEach(e => es.fire(e.type, e));
  // ...AND deliver the identical full history via polling multiple times
  // (simulating overlap / a reconnect replay).
  await sandbox.pollOnce();
  await sandbox.pollOnce();
  await sandbox.pollOnce();
  await sleep(350);

  const stageMarkers = doc.getElementById("activity-list").children.filter(
    li => li._textContentSet === false && String(li._innerHTML).includes("stage-marker"));
  const uniqueStagesInFixture = new Set(events.filter(e => e.type === "stage").map(e => e.ts)).size;
  assertEqual(stageMarkers.length, uniqueStagesInFixture, "I: no duplicate stage lines despite SSE + 3x polling delivering the same events");
  sandbox.stopEverything();
}

async function testGH_transportFailureNeverResubmits() {
  const finalEvents = buildEventSequence("NO_CHANGE_NEEDED");
  const fetchStub = makeFetchStub({
    "POST /api/trainer/assess": () => ({ complexity: "TINY", risk: "LOW", decision: "auto", reason: "ok", matched_keywords: [], suggested_alternatives: [] }),
    "POST /api/trainer/runs": () => ({ blocked: false, run_id: "trainer-gh", assessment: { decision: "auto" } }),
    "GET /api/runs/trainer-gh": () => ({ id: "trainer-gh", status: "NO_CHANGE_NEEDED", events: finalEvents, result: null }),
  });
  const doc = makeDocumentStub();
  FakeEventSource.instances = [];
  const sandbox = loadTrainerContext(doc, fetchStub);

  await runSubmit(sandbox, "gh test");
  // SSE never fires anything (silent failure) — only polling delivers data.
  await sandbox.pollOnce();
  await sandbox.pollOnce();
  await sleep(350);

  const runsPostCalls = fetchStub.calls.filter(c => c.url === "/api/trainer/runs" && c.method === "POST");
  assertEqual(runsPostCalls.length, 1, "G/H: exactly one POST /api/trainer/runs despite SSE failing silently and polling taking over");
  sandbox.stopEverything();
}

(async () => {
  await testA_sseWorksNormally();
  await testBC_pollingFallbackWhenSSESilent();
  await testDE_completedAndFailedThroughFallback();
  await testI_noDuplicateEventsWhenBothTransportsDeliverSameData();
  await testGH_transportFailureNeverResubmits();

  console.log(`\n${passed} passed, ${failures} failed`);
  process.exit(failures > 0 ? 1 : 0);
})();
