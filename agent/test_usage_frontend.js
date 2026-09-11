// Focused tests for agent/web/usage.js — Session History panel + Session
// Detail rendering (P0-B) and the UI-hardening additions (provenance/
// value-confidence color coding, top summary card, long-ID truncation).
// Plain-Node vm-based harness (no jsdom, no new dependency), matching
// this project's existing convention (test_trainer_frontend.js,
// test_learn_frontend.js). Calls the REAL exported render helpers
// directly (they are top-level `function` declarations in usage.js, so
// they exist as properties of the vm context's global object) rather
// than driving the full async fetch/router pipeline, which this
// lightweight harness's DOM stub cannot fully simulate (no real HTML
// parsing) — see learn.js's richer harness for that pattern where it
// mattered more.
//
// Run: node agent/test_usage_frontend.js

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

function makeElement() {
  return { _innerHTML: "", get innerHTML() { return this._innerHTML; }, set innerHTML(v) { this._innerHTML = v; }, addEventListener() {}, querySelectorAll: () => [] };
}

function buildSandbox() {
  const elements = { "sessions-main": makeElement() };
  const documentStub = {
    getElementById: (id) => elements[id] || null,
    addEventListener: () => {},
    createElement: () => ({ set textContent(v) { this._t = v; }, get innerHTML() { return String(this._t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); } }),
  };
  const fetchStub = async () => ({ ok: true, status: 200, json: async () => ({ status: "REACHABLE", sessions: [], next_cursor: null, has_more: false }) });
  const sandbox = {
    document: documentStub,
    window: { location: { pathname: "/usage" }, addEventListener: () => {}, scrollTo: () => {} },
    location: { pathname: "/usage" },
    history: { pushState: () => {} },
    fetch: fetchStub,
    Intl, Date, URL: class { constructor(u, base) { this.searchParams = new Map(); this._u = u; } toString() { return this._u; } },
    console, setTimeout, clearTimeout,
  };
  vm.createContext(sandbox);
  return sandbox;
}

function loadUsageJs(sandbox) {
  const src = fs.readFileSync(path.join(__dirname, "web", "usage.js"), "utf8");
  const script = new vm.Script(src, { filename: "usage.js" });
  script.runInContext(sandbox);
}

const FIXTURE_SESSION = {
  session_id: "trainer-4733d1c0", kind: "workbench_run",
  start_utc: "2026-09-11T01:06:39.083094+00:00", end_utc: "2026-09-11T01:08:30.278493+00:00",
  wall_clock_ms: 111195.4, status: "COMPLETED", provenance: "LIVE_CAPTURED",
  goal: "Change the Create button label",
  tokens: { status: "EXACT", input_tokens: 37340, output_tokens: 2821 },
  cost: { status: "ACTUAL", cost_usd: 0.10289, pricing_version: "v1" },
};

const FIXTURE_DETAIL = {
  ...FIXTURE_SESSION,
  ai_active_ms: 2134.1, ai_active_ms_note: "DERIVED from real tool_call_completed durations",
  ai_waiting_for_human_ms: null, ai_waiting_for_human_note: "UNKNOWN — no PermissionRequest-equivalent timing captured for this kind",
  human_active_note: "UNKNOWN — this project does not capture real human-interaction intervals",
  human_waiting_for_ai_ms: 2134.1, human_waiting_for_ai_note: "DERIVED (approximated as AI active time)",
  tool_call_count: 5,
  value: { technical_value: { verified_changes_completed: 1, failures: 0 }, learning_value: { knowledge_candidates_created: 0 } },
  quality: { scored_dimensions: { goal_completion: true }, evidence_coverage_pct: 100, overall_confidence: "HIGH_CONFIDENCE" },
  comparison: { status: "COMPARABLE", cohort_size: 26, cohort_basis: "same kind, previous 7 days" },
  timeline: [], human_interventions: [],
};

(() => {
  const sandbox = buildSandbox();
  loadUsageJs(sandbox);

  // ---- Provenance badge color-coding ------------------------------
  assertIncludes(sandbox.provenanceBadge("LIVE_CAPTURED"), "provenance-live", "LIVE_CAPTURED gets the live-provenance style");
  assertIncludes(sandbox.provenanceBadge("PARTIAL_RECONSTRUCTION"), "provenance-partial", "PARTIAL_RECONSTRUCTION gets the partial-provenance style");

  // ---- Value-note color-coding (ACTUAL/DERIVED/UNKNOWN distinguishable) --
  assertIncludes(sandbox.noteSpan("DERIVED from real tool_call_completed durations"), "note-derived", "a DERIVED note is colored distinctly");
  assertIncludes(sandbox.noteSpan("UNKNOWN — not captured"), "note-unknown", "an UNKNOWN note is colored distinctly");
  assertIncludes(sandbox.noteSpan("some other real note"), "note-exact", "a non-derived, non-unknown note defaults to the exact/confident style");

  // ---- Long session id truncation ----------------------------------
  const longId = "a".repeat(50);
  assertIncludes(sandbox.shortId(longId), "&hellip;", "a long session id is visually truncated");
  assert(!sandbox.shortId("short-id").includes("hellip"), "a short session id is NOT truncated");

  // ---- Session card uses the provenance badge, not raw text -------
  const cardHtml = sandbox.renderSessionCard(FIXTURE_SESSION);
  assertIncludes(cardHtml, "provenance-badge", "session history card shows the color-coded provenance badge");
  assertIncludes(cardHtml, "workbench_run", "session card carries its kind for CSS tagging");

  // ---- Top summary card (Section C: most important info visible first) --
  const summaryHtml = sandbox.renderTopSummary(FIXTURE_DETAIL);
  assertIncludes(summaryHtml, "session-summary-panel", "session detail renders a dedicated top summary panel");
  assertIncludes(summaryHtml, "Change the Create button label", "top summary shows the goal prominently");
  assertIncludes(summaryHtml, "summary-grid", "top summary uses the at-a-glance stat grid");
  assertIncludes(summaryHtml, "Quality", "top summary includes quality at a glance");
  assertIncludes(summaryHtml, "Value", "top summary includes value at a glance");

  // ---- Quality block distinguishes real evidence-availability from
  // substantive session facts, and never implies fake 100% confidence
  // for a thin-evidence session (real incident, 2026-09-11) -----------
  const thinQuality = {
    scored_dimensions: { goal_completion: true, human_intervention_present: false },
    evidence_availability: { ai_active_time_known: false, tokens_captured: false, cost_known: false },
    evidence_coverage_pct: 0, overall_confidence: "LOW_COVERAGE",
  };
  const qualityHtml = sandbox.renderQualityBlock(thinQuality);
  assertIncludes(qualityHtml, "not captured", "thin-evidence quality block shows real 'not captured' signals");
  assertIncludes(qualityHtml, "note-unknown", "LOW_CONFIDENCE quality is visually flagged, not shown as a plain success");
  assert(!qualityHtml.includes("note-exact\">LOW_COVERAGE"), "LOW_COVERAGE must never be styled as the confident/exact color");

  console.log(`${passed} passed, ${failures} failed`);
  process.exit(failures ? 1 : 0);
})();
