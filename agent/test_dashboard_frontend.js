// Focused tests for agent/web/dashboard.js. Plain-Node vm-based harness,
// same pattern as test_usage_frontend.js/test_learn_frontend.js (no
// jsdom, no new dependency) — loads the REAL file into a sandboxed vm
// context and calls its top-level `function` declarations directly.
//
// This file did not previously exist, which is exactly why a real,
// long-standing defect on this page (renderSessionMetrics hardcoding
// "NOT CAPTURED YET" for token usage/cost, never wired to any real
// field, sitting right next to the real, working Economics section that
// was fixed for the identical bug on 2026-09-11) went uncaught. See
// docs/LESSONS.md for the general lesson this specific incident fed into.
//
// Run: node agent/test_dashboard_frontend.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let failures = 0;
let passed = 0;

function assert(cond, msg) {
  if (!cond) { failures++; console.error("FAIL: " + msg); }
  else { passed++; }
}
function assertIncludes(haystack, needle, msg) {
  assert(String(haystack).includes(needle), `${msg} — expected to find ${JSON.stringify(needle)}`);
}
function assertNotIncludes(haystack, needle, msg) {
  assert(!String(haystack).includes(needle), `${msg} — expected NOT to find ${JSON.stringify(needle)}`);
}

function makeElement() {
  return { _innerHTML: "", get innerHTML() { return this._innerHTML; }, set innerHTML(v) { this._innerHTML = v; }, addEventListener() {} };
}

function buildSandbox() {
  const elements = { "dash-main": makeElement() };
  const documentStub = {
    getElementById: (id) => elements[id] || null,
    createElement: () => ({ set textContent(v) { this._t = v; }, get innerHTML() { return String(this._t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); } }),
  };
  const fetchStub = async () => ({ ok: true, json: async () => ({}) });
  const sandbox = { document: documentStub, fetch: fetchStub, console, Math };
  vm.createContext(sandbox);
  return sandbox;
}

function loadDashboardJs(sandbox) {
  const src = fs.readFileSync(path.join(__dirname, "web", "dashboard.js"), "utf8");
  const script = new vm.Script(src, { filename: "dashboard.js" });
  script.runInContext(sandbox);
}

// ---- renderSessionMetrics: the exact regression this file exists for ----

(function testSessionMetricsNeverHardcodesTokenCost() {
  const sandbox = buildSandbox();
  loadDashboardJs(sandbox);
  const withData = sandbox.renderSessionMetrics({
    session_metrics: { status: "CAPTURED", tool_calls_total: 5, tool_calls_succeeded: 5, tool_calls_failed: 0, security_blocked: 0 },
  });
  assertNotIncludes(withData, "NOT CAPTURED YET",
    "renderSessionMetrics must never render a hardcoded NOT CAPTURED YET for token/cost data it doesn't actually hold");
  assertIncludes(withData, "Economics", "renderSessionMetrics should point readers at the real Economics section instead of faking a value");
  assertIncludes(withData, "5", "real tool-call counts still render correctly");

  const noData = sandbox.renderSessionMetrics({ session_metrics: { status: "NOT CAPTURED", note: "process just started" } });
  assertNotIncludes(noData, "<span class=\"k\">Token usage</span>",
    "the removed fake token/cost kv row (as opposed to the new prose pointer, which legitimately contains the same words) must not reappear in the no-data path either");
})();

// ---- svgBarChart: the shared chart primitive ----

(function testSvgBarChart() {
  const sandbox = buildSandbox();
  loadDashboardJs(sandbox);

  const empty = sandbox.svgBarChart([]);
  assert(empty === "", "svgBarChart with zero bars renders nothing (no empty/broken SVG shell)");

  const svg = sandbox.svgBarChart(
    [{ label: "Today", value: 0.75, cls: "chart-good" }, { label: "This week", value: 0.5, cls: "chart-partial" }],
    { valueFmt: (v) => Math.round(v * 100) + "%", maxValue: 1 }
  );
  assertIncludes(svg, "<svg", "svgBarChart renders a real <svg> element");
  assertIncludes(svg, "Today", "bar labels render");
  assertIncludes(svg, "75%", "formatted values render via the supplied valueFmt");
  assertIncludes(svg, "chart-good", "per-bar CSS class is applied");

  // A bar with value 0 must still be visible in the DOM (width>=0), never
  // silently omitted — an omitted row would misleadingly look like missing
  // data rather than a real, correctly-computed zero.
  const zeroBar = sandbox.svgBarChart([{ label: "X", value: 0 }], { maxValue: 1 });
  assertIncludes(zeroBar, "X", "a real zero-value bar still renders its label, not silently dropped");
})();

// ---- renderEconomicsChart: real economics windows -> a real chart ----

(function testRenderEconomicsChart() {
  const sandbox = buildSandbox();
  loadDashboardJs(sandbox);

  const e = {
    last_run: { runs_total: 1, runs_completed_verified: 1 },
    this_hour: { runs_total: 4, runs_completed_verified: 3 },
    last_24_hours: { runs_total: 0, runs_completed_verified: 0 },
    today: { runs_total: 4, runs_completed_verified: 3 },
    this_week: { runs_total: 10, runs_completed_verified: 8 },
    this_month: { runs_total: 20, runs_completed_verified: 15 },
  };
  const html = sandbox.renderEconomicsChart(e);
  assertIncludes(html, "<svg", "a real chart renders when at least one window has runs");
  assertIncludes(html, "75%", "This hour's 3/4 verified rate computes to 75%, from the same real fields the text cards use");
  assertNotIncludes(html, "Last 24h", "a window with zero runs is excluded from the chart rather than drawn as a misleading empty/zero bar");

  const noRuns = sandbox.renderEconomicsChart({
    last_run: { runs_total: 0, runs_completed_verified: 0 }, this_hour: { runs_total: 0, runs_completed_verified: 0 },
    last_24_hours: { runs_total: 0, runs_completed_verified: 0 }, today: { runs_total: 0, runs_completed_verified: 0 },
    this_week: { runs_total: 0, runs_completed_verified: 0 }, this_month: { runs_total: 0, runs_completed_verified: 0 },
  });
  assert(noRuns === "", "renderEconomicsChart renders nothing (not an empty chart shell) when every window has zero runs");
})();

// ---- renderRunDurationChart: real run_history rows -> a real chart ----

(function testRenderRunDurationChart() {
  const sandbox = buildSandbox();
  loadDashboardJs(sandbox);

  const runs = [
    { run_id: "trainer-aaaa1111", started_ts: 100, ended_ts: 142.5, final_status: "COMPLETED" },
    { run_id: "trainer-bbbb2222", started_ts: 200, ended_ts: 260.2, final_status: "FAILED" },
    { run_id: "trainer-no-duration", final_status: "COMPLETED" }, // no started_ts/ended_ts — must be skipped, not crash
  ];
  const html = sandbox.renderRunDurationChart(runs);
  assertIncludes(html, "<svg", "a real chart renders for runs with real start/end timestamps");
  assertIncludes(html, "42.5s", "duration is computed as the real ended_ts - started_ts delta, matching what renderRunHistory shows in its own text row");
  assertIncludes(html, "chart-partial", "a FAILED run's bar is styled distinctly from a COMPLETED one");

  const noDurations = sandbox.renderRunDurationChart([{ run_id: "x", final_status: "COMPLETED" }]);
  assert(noDurations === "", "renderRunDurationChart renders nothing when no run has real start/end timestamps, rather than an empty chart shell");
})();

console.log(`\n${passed} passed, ${failures} failed`);
process.exit(failures ? 1 : 0);
