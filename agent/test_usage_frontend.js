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
  quality: {
    quality_score: null, quality_score_label: "NOT SCORED",
    scored_dimensions: { goal_completion: true }, evidence_availability: { cost_known: true },
    evidence_coverage_pct: 100, overall_confidence: "HIGH_CONFIDENCE",
  },
  comparison: { status: "COMPARABLE", cohort_size: 26, cohort_basis: "same kind, previous 7 days" },
  timeline: [], human_interventions: [],
  window_kind: "CAPTURED_SESSION_DURATION", window_note: null,
  cost_display_label: "ACTUAL COST — CALCULATED FROM ACTUAL USAGE",
  raw_capture: null,
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

  // ---- Quality vs. Evidence Coverage must be VISIBLY SEPARATE stats
  // (Owner-observed defect, 2026-09-11: top summary showed "QUALITY /
  // 100% coverage", conflating the two) -------------------------------
  assertIncludes(summaryHtml, "Evidence Coverage", "top summary shows Evidence Coverage as its own separate stat");
  assertIncludes(summaryHtml, "NOT SCORED", "Quality stat shows NOT SCORED, not a copy of the coverage percentage");
  assert(!/Quality[\s\S]{0,40}100%\s*coverage/.test(summaryHtml), "Quality stat must never read '100% coverage' -- that is Evidence Coverage's number, not a quality score");

  // ---- Reconstructed-window semantics never imply proven continuous
  // work (Owner-observed defect, 2026-09-11: '12.1 hr' with AI active
  // time UNKNOWN looked like 12.1h of continuous work) -----------------
  const observedWindowDetail = { ...FIXTURE_DETAIL, window_kind: "OBSERVED_EVENT_WINDOW", window_note: "reconstructed from first/last OBSERVED event only" };
  assertIncludes(sandbox.wallTimeLabel(observedWindowDetail), "observed window", "an OBSERVED_EVENT_WINDOW session is visually labeled, not shown as a plain confident duration");
  const unknownDurationDetail = { ...FIXTURE_DETAIL, wall_clock_ms: 0, window_kind: "UNKNOWN" };
  assert(sandbox.wallTimeLabel(unknownDurationDetail) === "DURATION NOT CAPTURED", "a same-timestamp session shows DURATION NOT CAPTURED, never a bare misleading 0ms");

  // ---- Cost display label: never a fabricated $0 for unknown cost ----
  assert(!sandbox.costSummary({ status: "COST_UNAVAILABLE", reason: "aggregate token count does not expose input/output/cache split" }).includes("$0"),
    "an aggregate-only session must never render as $0 cost");

  // ---- Real gap found 2026-09-18 (the 40 EUR overnight-session incident):
  // a session card/detail showed ONLY cost_display_label (a text label)
  // whenever one existed, silently hiding the actual dollar figure even
  // when it was fully known server-side -- costText() must always surface
  // the real number for an ACTUAL cost, with the label as context, not a
  // replacement. ----------------------------------------------------
  const actualCost = { status: "ACTUAL", cost_usd: 439.866923, pricing_version: "anthropic-2026-09-10-v1" };
  const actualLabel = "ACTUAL COST — CALCULATED FROM ACTUAL USAGE";
  assertIncludes(sandbox.costText(actualCost, actualLabel), "$439.8669", "costText must show the real dollar figure, not just the text label");
  assertIncludes(sandbox.costText(actualCost, actualLabel), actualLabel, "costText should still include the label as supporting context");
  assert(sandbox.costText({ status: "COST_UNAVAILABLE", reason: "no usage captured" }, null).includes("COST UNAVAILABLE"),
    "costText falls back to the unavailable reason when there is no real cost");

  // ---- Real gap found 2026-09-18: cache tokens (the dominant cost driver
  // in the real incident -- 1.84 BILLION cache-read tokens) were silently
  // dropped from tokenSummary(), showing only input/output. ----------
  const cacheHeavyTokens = { status: "EXACT", input_tokens: 7078, output_tokens: 3047211, cache_read_tokens: 1836409236, cache_write_tokens: 16839524 };
  const cacheSummary = sandbox.tokenSummary(cacheHeavyTokens);
  assertIncludes(cacheSummary, "cache-read", "tokenSummary must surface cache-read tokens when present, not silently drop the dominant cost driver");
  assert(cacheSummary.replace(/[^0-9]/g, "").includes("1836409236"), `the real cache-read token count must be shown in full, not truncated/rounded away — got: ${cacheSummary}`);

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

  // ---- HTML entity regression (Owner-observed defect, 2026-09-11): a
  // literal "&AMP;" appeared on the live page because a section title
  // already containing the HTML entity "&amp;" was passed through esc(),
  // double-encoding it into "&amp;amp;" -- every section() title must be
  // PLAIN text ("&", not "&amp;"), letting esc() encode it exactly once ---
  const sectionHtml = sandbox.section("Tokens & Cost", "<p>body</p>");
  assertIncludes(sectionHtml, "Tokens &amp; Cost", "a plain '&' in a section title is encoded exactly once");
  assert(!sectionHtml.includes("&amp;amp;"), "a section title must never be double-encoded into a literal &amp; on the page");

  const usageJsSource = fs.readFileSync(path.join(__dirname, "web", "usage.js"), "utf8");
  assert(
    !/section\(\s*[`"'][^`"']*&amp;/.test(usageJsSource),
    "no section(...) call in usage.js may hand-type the HTML entity '&amp;' in its title (it will be double-encoded)"
  );

  // ---- RECRUITER-FACING VERIFIED-RUN P0 (2026-09-13): the engineering-
  // outcome evidence section rendered above the generic Usage sections
  // on a workbench_run's detail page. Real defect this protects against:
  // a recruiter landing on a session detail page with no clear signal
  // that they're looking at a genuinely verified production run. -----
  const EVIDENCE_FIXTURE = {
    session_id: "trainer-0c5d59ab", status: "COMPLETED",
    engineering_evidence: {
      requirement: 'Change the footer text to "Built with DOSS KARTHIK care"',
      operation_id: "footer_text", human_name: "the footer text",
      requested_value: "Built with DOSS KARTHIK care",
      changed_file: "app/src/main/resources/static/index.html",
      diff_old_line: '<footer class="app-footer">Powered by Agentic Delivery</footer>',
      diff_new_line: '<footer class="app-footer">Built with DOSS KARTHIK care</footer>',
      testing_state: "TESTING — NOT APPLICABLE", testing_reason: "static resource, no Java test surface",
      local_commit_sha: "b511564", local_commit_branch: "demo/trainer-0c5d59ab",
      github_push_status: "NOT_CONFIGURED",
      railway_deployment_id: "fe9a097a-fca3-4fb3-b406-0a8bdafb1e32", railway_deployment_status: "SUCCESS",
      deployment_identity_confirmed: true,
      production_url: "https://agentic-delivery-customer-app-production.up.railway.app/",
      requested_effect_verified: true, observed_production_value: "Built with DOSS KARTHIK care",
      final_result_text: 'the footer text is now "Built with DOSS KARTHIK care" in production.',
    },
  };
  const evidenceHtml = sandbox.renderEngineeringEvidence(EVIDENCE_FIXTURE);
  assertIncludes(evidenceHtml, "VERIFIED PRODUCTION RUN", "a genuinely COMPLETED workbench run shows the clear verified-run heading");
  assertIncludes(evidenceHtml, "trainer-0c5d59ab", "the real Run ID is shown, not omitted");
  assertIncludes(evidenceHtml, "Built with DOSS KARTHIK care", "the real requirement/observed value is shown");
  assertIncludes(evidenceHtml, "fe9a097a-fca3-4fb3-b406-0a8bdafb1e32", "the real Railway deployment ID is shown");
  assertIncludes(evidenceHtml, "NOT_CONFIGURED", "GitHub push NOT_CONFIGURED is shown honestly, not hidden or shown as a green success");
  assertIncludes(evidenceHtml, "VIEW FULL USAGE DETAILS", "a clear link/anchor to the full Usage detail exists, distinguishing engineering result from resource usage");

  const evidenceHtmlNonCompleted = sandbox.renderEngineeringEvidence({ ...EVIDENCE_FIXTURE, status: "FAILED" });
  assert(!evidenceHtmlNonCompleted.includes("VERIFIED PRODUCTION RUN"), "a non-COMPLETED run must never claim the VERIFIED PRODUCTION RUN heading");
  assertIncludes(evidenceHtmlNonCompleted, "FAILED", "a non-COMPLETED run's real status is shown instead");

  assert(
    sandbox.renderEngineeringEvidence({ session_id: "x", status: "COMPLETED", engineering_evidence: null }) === "",
    "a session with no engineering_evidence (e.g. a Claude Code dev session) renders nothing here, never a fabricated evidence panel"
  );

  const unavailableHtml = sandbox.renderEngineeringEvidence({
    session_id: "trainer-4733d1c0", status: "COMPLETED",
    engineering_evidence: { ...EVIDENCE_FIXTURE.engineering_evidence, changed_file: "UNAVAILABLE", diff_old_line: "UNAVAILABLE", diff_new_line: "UNAVAILABLE" },
  });
  assertIncludes(unavailableHtml, "UNAVAILABLE", "a field with genuinely no captured evidence is shown honestly as UNAVAILABLE, never fabricated");

  // ---- AI Delivery Efficiency summary (Priority 1 redesign) --------
  const ECONOMICS_FIXTURE = {
    status: "REACHABLE",
    canonical_source: "event ledger (delivery_events, event_type=run_usage_summary)",
    display_timezone: "Europe/Berlin",
    last_run: { runs_total: 1, runs_completed_verified: 1, cost_usd: 0.0012, cost_known_for_all_captured_runs: true },
    today: { runs_total: 3, runs_completed_verified: 2, cost_usd: 0.05, cost_known_for_all_captured_runs: true },
    this_week: { runs_total: 20, runs_completed_verified: 15, cost_usd: 1.2, cost_known_for_all_captured_runs: true },
    lifetime: { runs_total: 200, runs_completed_verified: 150, input_tokens: 900000, output_tokens: 100000, cost_usd: 12.5, cost_known_for_all_captured_runs: true },
    cost_per_verified_change_usd: 0.0833,
    cost_per_verified_change_note: "lifetime COMPLETED runs with known cost only",
  };
  const efficiencyHtml = sandbox.renderEfficiencySummary({ economics: ECONOMICS_FIXTURE });
  // Real gap found 2026-09-18 (40 EUR overnight-session incident): this
  // heading used to just say "AI Delivery Efficiency" with no indication
  // it covers Workbench pipeline runs only -- confirmed confusing when a
  // much larger Claude Code development cost sat unlabeled on the same
  // page. Heading and body must now say the scope explicitly.
  assertIncludes(efficiencyHtml, "Workbench Delivery Efficiency", "the efficiency section's heading names its real scope (Workbench only), not a bare generic 'AI Delivery Efficiency'");
  assertIncludes(efficiencyHtml, "does NOT include Claude Code", "the section explicitly says what it excludes, so it can never be mistaken for a total AI spend figure");
  assertIncludes(efficiencyHtml, "$0.08", "cost per verified change is shown as a real computed ratio, not a placeholder");
  assertIncludes(efficiencyHtml, "6,667", "tokens per verified change is derived from real lifetime totals ((900000+100000)/150)");
  assertIncludes(efficiencyHtml, "150", "lifetime verified change count is shown");
  assertIncludes(efficiencyHtml, "/dashboard", "the section links to Dashboard for the full per-window breakdown instead of duplicating it");

  const efficiencyUnreachableHtml = sandbox.renderEfficiencySummary({ economics: { status: "UNREACHABLE", error: "connection refused" } });
  assertIncludes(efficiencyUnreachableHtml, "Workbench Delivery Efficiency", "an unreachable ledger still renders the section with its real heading");
  assert(!efficiencyUnreachableHtml.includes("INSUFFICIENT DATA") || efficiencyUnreachableHtml.includes("UNREACHABLE"), "an unreachable ledger is labeled honestly, never silently shown as zero/empty tiles");

  const efficiencyNoDataHtml = sandbox.renderEfficiencySummary({
    economics: { ...ECONOMICS_FIXTURE, cost_per_verified_change_usd: null, cost_per_verified_change_note: "INSUFFICIENT DATA", lifetime: { ...ECONOMICS_FIXTURE.lifetime, runs_completed_verified: 0 } },
  });
  assertIncludes(efficiencyNoDataHtml, "INSUFFICIENT DATA", "a genuinely absent ratio is labeled INSUFFICIENT DATA, never fabricated as $0.00 or similar");

  // ---- Visual chart (real production gap found via Owner screenshot
  // feedback 2026-09-18: Dashboard got real charts, Usage did not) ------
  assertIncludes(efficiencyHtml, "chart-block", "AI Delivery Efficiency renders a real visual chart, not just text tiles");
  assertIncludes(efficiencyHtml, "Verified-change rate by window", "the chart has its real, descriptive title");
  assertIncludes(efficiencyHtml, "<svg", "the chart is a real rendered SVG element");
  // Fixture windows: last_run 1/1=100%, today 2/3=67%, this_week 15/20=75%,
  // lifetime 150/200=75% -- every window has real runs, so every window
  // must produce a real bar (never silently dropped).
  const chartSvgMatches = efficiencyHtml.match(/<rect[^>]*class="chart-fill[^"]*"/g) || [];
  assert(chartSvgMatches.length === 4, `all 4 windows with real runs produce a real bar (found ${chartSvgMatches.length})`);

  const chartNoDataHtml = sandbox.renderEfficiencySummary({
    economics: {
      ...ECONOMICS_FIXTURE,
      last_run: { runs_total: 0, runs_completed_verified: 0 },
      today: { runs_total: 0, runs_completed_verified: 0 },
      this_week: { runs_total: 0, runs_completed_verified: 0 },
      lifetime: { ...ECONOMICS_FIXTURE.lifetime, runs_total: 0, runs_completed_verified: 0 },
    },
  });
  assert(!chartNoDataHtml.includes("<svg"), "a genuinely empty window set renders no chart at all, never a fake/empty one");

  const svgChartHtml = sandbox.svgBarChart([{ label: "X", value: 5 }, { label: "Y", value: 10 }]);
  assertIncludes(svgChartHtml, "<svg", "svgBarChart produces a real SVG element");
  assert((svgChartHtml.match(/<rect/g) || []).length === 4, "svgBarChart renders 2 bars as 4 rects (track+fill per bar)");

  // ---- Claude Code Development Cost (real gap found 2026-09-18: the 40
  // EUR overnight-session incident had no aggregate view anywhere, only a
  // single session's own detail page) ---------------------------------
  const DEV_COST_FIXTURE = {
    status: "REACHABLE",
    canonical_source: "event ledger (delivery_events, event_type=model_usage, source=claude_code)",
    display_timezone: "Europe/Berlin",
    today: { sessions_total: 1, input_tokens: 7078, output_tokens: 3047211, cost_usd: 439.866923, cost_known_for_all_captured_sessions: true },
    this_week: { sessions_total: 1, input_tokens: 7078, output_tokens: 3047211, cost_usd: 439.866923, cost_known_for_all_captured_sessions: true },
    lifetime: { sessions_total: 1, input_tokens: 7078, output_tokens: 3047211, cost_usd: 439.866923, cost_known_for_all_captured_sessions: true },
  };
  const devCostHtml = sandbox.renderDevSessionCostSummary({ dev_session_economics: DEV_COST_FIXTURE });
  assertIncludes(devCostHtml, "Claude Code Development Cost", "the dev-cost section has its own distinct heading");
  assertIncludes(devCostHtml, "$439.87", "the real lifetime dev-session cost is shown as an actual number, not just a label");
  assertIncludes(devCostHtml, "separate from Workbench", "the section explicitly says it is not combined with Workbench cost");

  const devCostUnreachableHtml = sandbox.renderDevSessionCostSummary({ dev_session_economics: { status: "UNREACHABLE" } });
  assertIncludes(devCostUnreachableHtml, "Claude Code Development Cost", "an unreachable ledger still renders the section with its real heading");
  assert(!devCostUnreachableHtml.includes("$0.00") && !devCostUnreachableHtml.includes("$0.0000"), "an unreachable ledger must never show a fabricated $0 cost");

  const devCostEmptyHtml = sandbox.renderDevSessionCostSummary({
    dev_session_economics: { ...DEV_COST_FIXTURE, today: { sessions_total: 0 }, this_week: { sessions_total: 0 }, lifetime: { sessions_total: 0, input_tokens: 0, output_tokens: 0, cost_usd: 0, cost_known_for_all_captured_sessions: true } },
  });
  assertIncludes(devCostEmptyHtml, "no sessions in this window", "a genuinely empty window says so honestly, never a fabricated $0.00");
  assert(sandbox.svgBarChart([]) === "", "svgBarChart with no bars renders nothing, not an empty/broken SVG shell");

  console.log(`${passed} passed, ${failures} failed`);
  process.exit(failures ? 1 : 0);
})();
