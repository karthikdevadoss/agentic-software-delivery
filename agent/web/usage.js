// Agentic Software Delivery — Sessions (Session Intelligence / Value Ledger) frontend.
// Fetches /api/sessions (agent/sessions_data.py) and renders it as-is.
// No score, duration, or token value is computed client-side.

const main = document.getElementById("sessions-main");

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function section(title, innerHtml) {
  return `<section class="panel"><h2>${esc(title)}</h2>${innerHtml}</section>`;
}

function fmtUsd(n) {
  if (n === null || n === undefined) return "—";
  return "$" + n.toFixed(n < 0.01 ? 4 : 2);
}

// AI DELIVERY EFFICIENCY (Priority 1, flagship-completion redesign): this
// page used to open directly on a plain session log with no headline
// efficiency framing anywhere on it. This leads the page instead with the
// real ratios a recruiter/engineer actually wants first (cost and tokens
// PER VERIFIED CHANGE, not just raw totals) — computed entirely from
// agent/event_ledger.py::get_usage_economics(), the SAME canonical
// ledger-backed source Dashboard's Economics/Consumption section already
// reads (see agent/sessions_data.py's economics key) — never a second,
// divergent computation. The detailed per-window consumption breakdown
// stays on Dashboard; this section's job is the efficiency headline plus
// a compact recent-window strip, then the full session-level drill-down
// below (unchanged) shows exactly how each number was produced.
function renderEfficiencySummary(d) {
  const e = d.economics;
  if (!e || e.status !== "REACHABLE") {
    return section("Workbench Delivery Efficiency", `<div class="econ-note">Event ledger ${e ? esc(e.status) : "UNAVAILABLE"} — real efficiency ratios require the remote event ledger; see the Event Ledger section below for detail.</div>`);
  }
  const lifetime = e.lifetime;
  const verified = lifetime.runs_completed_verified;
  const tokensPerVerified = verified > 0 ? Math.round((lifetime.input_tokens + lifetime.output_tokens) / verified) : null;
  const tiles = [
    ["Cost per verified change", e.cost_per_verified_change_usd != null ? fmtUsd(e.cost_per_verified_change_usd) : "INSUFFICIENT DATA", e.cost_per_verified_change_note],
    ["Verified changes (lifetime)", String(verified), `of ${lifetime.runs_total} total delivery run(s)`],
    ["Tokens per verified change", tokensPerVerified != null ? tokensPerVerified.toLocaleString() : "INSUFFICIENT DATA", "lifetime input+output tokens / verified changes"],
    ["Lifetime AI spend", fmtUsd(lifetime.cost_usd), lifetime.cost_known_for_all_captured_runs ? "known for every captured run" : "partial — some runs' cost unknown"],
  ];
  const tilesHtml = `<div class="exec-grid">` + tiles.map(([label, value, note]) =>
    `<div class="exec-stat"><div class="exec-value">${esc(value)}</div><div class="exec-label">${esc(label)}</div><div class="exec-note">${esc(note)}</div></div>`
  ).join("") + `</div>`;

  const windowCard = (label, w) => {
    if (!w || w.runs_total === 0) {
      return `<div class="econ-card"><div class="econ-label">${esc(label)}</div><div class="econ-value">no runs in this window</div></div>`;
    }
    return `<div class="econ-card">
      <div class="econ-label">${esc(label)}</div>
      <div class="econ-value">${fmtUsd(w.cost_usd)}${w.cost_known_for_all_captured_runs ? "" : " (partial)"}</div>
      <div class="kv-row"><span>${w.runs_total} run(s)</span><span>${w.runs_completed_verified} verified</span></div>
    </div>`;
  };
  const windowsHtml = `<div class="econ-grid">
    ${windowCard("Last run", e.last_run)}
    ${windowCard(`Today (${e.display_timezone})`, e.today)}
    ${windowCard(`This week (${e.display_timezone})`, e.this_week)}
    ${windowCard("Lifetime", lifetime)}
  </div>`;

  // Real gap found 2026-09-18 (the 40 EUR overnight-session incident): this
  // section's title/numbers cover WORKBENCH pipeline runs only, but nothing
  // said so -- a viewer could easily read "Lifetime AI spend: $1.49" as the
  // platform's total AI spend, when a real, much larger Claude Code
  // development cost lives entirely outside this section. Title and hint
  // now say the scope explicitly; renderDevSessionCostSummary() below is
  // the separate, equally-real sibling for that other domain.
  return section("Workbench Delivery Efficiency (pipeline runs only — see \"Claude Code Development Cost\" below for a separate total)", `
    <p class="hint" style="margin-top:0;">Real, ledger-backed ratios for Workbench pipeline runs — never estimated, never fabricated. A failed or no-change run's real cost is still counted (see ${esc(e.canonical_source)}). This does NOT include Claude Code development-session cost — that is tracked separately below.</p>
    ${tilesHtml}
    <p class="hint" style="margin-top:1.2rem;">Recent windows:</p>
    ${windowsHtml}
    ${renderEfficiencyChart(e)}
    <p class="hint" style="margin-top:0.9rem;">Full per-window consumption breakdown (this hour/last 24h/this month, tokens by category, pricing versions): see <a href="/dashboard">Dashboard</a>'s Economics / Consumption section.</p>
  `);
}

// Real gap found 2026-09-18 (the 40 EUR overnight-session incident): no
// aggregate view of Claude Code's OWN development-session cost existed
// anywhere -- only a single session's own detail page could show it. This
// is the lifetime/today/this-week rollup, sourced from
// event_ledger.get_dev_session_cost_summary() (source='claude_code',
// event_type='model_usage') -- deliberately never merged with
// renderEfficiencySummary()'s Workbench-only numbers above.
function renderDevSessionCostSummary(d) {
  const dc = d.dev_session_economics;
  if (!dc || dc.status !== "REACHABLE") {
    return section("Claude Code Development Cost", `<div class="econ-note">Event ledger ${dc ? esc(dc.status) : "UNAVAILABLE"}.</div>`);
  }
  const windowCard = (label, w) => {
    if (!w || w.sessions_total === 0) {
      return `<div class="econ-card"><div class="econ-label">${esc(label)}</div><div class="econ-value">no sessions in this window</div></div>`;
    }
    return `<div class="econ-card">
      <div class="econ-label">${esc(label)}</div>
      <div class="econ-value">${fmtUsd(w.cost_usd)}${w.cost_known_for_all_captured_sessions ? "" : " (partial)"}</div>
      <div class="kv-row"><span>${w.sessions_total} session(s)</span><span>${(w.input_tokens + w.output_tokens).toLocaleString()} tokens</span></div>
    </div>`;
  };
  return section("Claude Code Development Cost (building this platform — separate from Workbench above)", `
    <p class="hint" style="margin-top:0;">Real cost of Claude Code development sessions (writing/debugging this platform's own code), computed from real captured tokens via the same versioned pricing table every other cost figure on this site uses. Entirely separate from Workbench pipeline-run cost above — the two are never combined into one number. See ${esc(dc.canonical_source)}.</p>
    <div class="econ-grid">
      ${windowCard(`Today (${dc.display_timezone})`, dc.today)}
      ${windowCard(`This week (${dc.display_timezone})`, dc.this_week)}
      ${windowCard("Lifetime", dc.lifetime)}
    </div>
  `);
}

// ---- Visual chart (hand-rolled inline SVG, no charting library -- same
// pattern as dashboard.js's svgBarChart, duplicated rather than shared
// since this frontend has no build step/module system; every real number
// here comes from the exact same economics object rendered as text just
// above it, never a second, independently-computed source) ------------
function svgBarChart(bars, { width = 640, barHeight = 22, gap = 10, valueFmt = (v) => String(v), maxValue = null } = {}) {
  if (!bars.length) return "";
  const labelWidth = 150;
  const trackWidth = width - labelWidth - 70;
  const max = maxValue != null ? maxValue : Math.max(...bars.map((b) => b.value), 0.0001);
  const rowHeight = barHeight + gap;
  const height = bars.length * rowHeight;
  let svg = `<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="chart">`;
  bars.forEach((b, i) => {
    const y = i * rowHeight;
    const w = Math.max((b.value / max) * trackWidth, b.value > 0 ? 2 : 0);
    svg += `<text x="0" y="${y + barHeight / 2 + 4}" class="chart-label">${esc(b.label)}</text>`;
    svg += `<rect x="${labelWidth}" y="${y}" width="${trackWidth}" height="${barHeight}" rx="4" class="chart-track"></rect>`;
    svg += `<rect x="${labelWidth}" y="${y}" width="${w}" height="${barHeight}" rx="4" class="chart-fill ${esc(b.cls || "")}"></rect>`;
    svg += `<text x="${labelWidth + trackWidth + 8}" y="${y + barHeight / 2 + 4}" class="chart-value">${esc(valueFmt(b.value))}</text>`;
  });
  svg += "</svg>";
  return svg;
}

// Verified-change rate per window, reusing the exact same real windows
// (last_run/today/this_week/lifetime) the text tiles above already show.
function renderEfficiencyChart(e) {
  const windows = [
    ["Last run", e.last_run], ["Today", e.today], ["This week", e.this_week], ["Lifetime", e.lifetime],
  ];
  const bars = windows
    .filter(([, w]) => w && w.runs_total > 0)
    .map(([label, w]) => ({
      label,
      value: w.runs_completed_verified / w.runs_total,
      cls: w.runs_completed_verified === w.runs_total ? "chart-good" : "chart-partial",
    }));
  if (!bars.length) return "";
  const chart = svgBarChart(bars, { valueFmt: (v) => Math.round(v * 100) + "%", maxValue: 1 });
  return `<div class="chart-block"><p class="chart-title">Verified-change rate by window</p>${chart}</div>`;
}

function scoreClass(score) {
  if (score == null) return "none";
  if (score >= 80) return "high";
  if (score >= 50) return "mid";
  return "low";
}

function fmtDuration(seconds) {
  if (seconds == null) return "n/a";
  if (seconds < 120) return `${seconds.toFixed(0)}s`;
  const mins = seconds / 60;
  if (mins < 120) return `${mins.toFixed(0)} min`;
  return `${(mins / 60).toFixed(1)} hr`;
}

function renderScoreBreakdown(dims) {
  const rows = Object.entries(dims).map(([k, v]) => {
    const label = k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    return `<li><span>${esc(label)}</span><span>${v == null ? '<span class="hint">NOT SCORED</span>' : esc(v)}</span></li>`;
  }).join("");
  return `<ul class="score-breakdown">${rows}</ul>`;
}

function renderSessionRow(s, index) {
  const cls = scoreClass(s.score.score);
  const scoreText = s.score.score == null ? "NOT SCORED" : `${s.score.score}/100`;
  const durationSeconds = s.wall_clock_commit_span_seconds != null ? s.wall_clock_commit_span_seconds
    : (typeof s.start_ts === "number" && typeof s.end_ts === "number" ? s.end_ts - s.start_ts : null);

  const commitsHtml = s.commits.length
    ? `<div><strong>Commits:</strong><ul>${s.commits.map(c => `<li><code>${esc(c.sha)}</code> ${esc(c.subject)}</li>`).join("")}</ul></div>`
    : "";
  const correctionsHtml = s.corrections.length
    ? `<div><strong>Real corrections during this session:</strong><ul>${s.corrections.map(c => `<li>${esc(c)}</li>`).join("")}</ul></div>`
    : "";
  // Real incident: this line hardcoded "Cost: NOT CALCULATED YET" even
  // after agent/pricing_config.py started computing and persisting a
  // real cost_usd alongside this exact token data (see
  // agent/web_server.py::_build_usage_summary) — the value existed and
  // was captured, it just was never displayed here. Never show a
  // contradictory "not calculated" next to real captured numbers again.
  const costText = (s.model_usage && s.model_usage.cost_usd != null)
    ? `$${s.model_usage.cost_usd.toFixed(s.model_usage.cost_usd < 0.01 ? 4 : 2)}`
    : "NOT AVAILABLE (no pricing entry for this model)";
  const usageHtml = s.model_usage
    ? `<div><strong>Model usage (from API response, not estimated):</strong> ${esc(s.model_usage.provider)}/${esc(s.model_usage.model)} — ${s.model_usage.input_tokens} input tokens, ${s.model_usage.output_tokens} output tokens across ${s.model_usage.api_calls} call(s). Cost: ${esc(costText)}.</div>`
    : `<div><strong>Model usage:</strong> NOT CAPTURED${s.session_type === "development" ? " for this session type yet" : ""}</div>`;

  return `<div class="session-row" data-idx="${index}">
    <div class="row-top">
      <div>
        <span class="tag-type ${esc(s.session_type)}">${esc(s.session_type)}</span>
        <strong>${esc(s.date)}</strong>
        ${s.reconstructed ? `<span class="hint">${esc(s.reconstruction_label)}</span>` : ""}
      </div>
      <div class="score ${cls}">${scoreText} <span class="hint">(coverage ${s.score.coverage_pct}%)</span></div>
    </div>
    <div class="goal">${esc(s.goal)}</div>
    <div class="meta">
      <span>Status: ${esc(s.status)}</span>
      <span>Duration: ${esc(s.wall_clock_label || fmtDuration(durationSeconds))}</span>
      <span>Human active time: ${esc(s.human_active_time)}</span>
    </div>
    <div class="session-detail">
      ${renderScoreBreakdown(s.score.breakdown)}
      ${usageHtml}
      ${commitsHtml}
      ${correctionsHtml}
    </div>
  </div>`;
}

function renderToday(d) {
  let html = `<p class="hint">Local date: ${esc(d.today_date)}</p>`;
  if (!d.today_sessions.length) {
    html += `<p class="hint">No sessions recorded today yet.</p>`;
  } else {
    html += d.today_sessions.map((s, i) => renderSessionRow(s, `today-${i}`)).join("");
  }
  return section("Today", html);
}

function renderCoverageExplainer() {
  return section("What Does \"Coverage\" Mean?", `
    <p class="hint" style="margin-top:0;">Coverage tells you how much of a session's score is backed by <strong>captured evidence</strong>, not how good the code is.</p>
    <ul class="limits">
      <li>It is <strong>not</strong> code coverage (no relation to tests).</li>
      <li>It is <strong>not</strong> a measure of model quality or output quality.</li>
      <li><strong>Lower coverage</strong> means more of the session had to be reconstructed from partial evidence (e.g. Git commit timestamps only).</li>
      <li><strong>Higher coverage</strong> means more dimensions were directly measured/captured (e.g. real verification status, real corrections found).</li>
    </ul>
  `);
}

function renderAllSessions(d) {
  const html = d.sessions.map((s, i) => renderSessionRow(s, i)).join("");
  return section("All Sessions", html || '<p class="hint">No sessions recorded yet.</p>');
}

function renderValueLedger(d) {
  const items = Object.entries(d.value_ledger).map(([k, v]) => {
    const label = k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    const levelClass = v.level.toLowerCase().replace(/\s+/g, "-");
    return `<div class="vl-item">
      <div>${esc(label)}</div>
      <div class="vl-level ${levelClass}">${esc(v.level)}</div>
      <div class="vl-reason">${esc(v.reason)}</div>
    </div>`;
  }).join("");
  return section("Value Ledger", `<div class="value-ledger">${items}</div>`);
}

function renderImprovement(d) {
  return section("Are We Improving?", `<p>${esc(d.relative_improvement)}</p>`);
}

function renderEventLedger(d) {
  const el = d.event_ledger;
  if (!el) return "";
  if (el.status !== "REACHABLE") {
    return section("Event Ledger", `<p class="hint">Evidence source: REMOTE EVENT LEDGER — status: ${esc(el.status)}${el.error ? " (" + esc(el.error) + ")" : ""}</p>`);
  }
  const rows = el.recent_events.map(e => {
    const parts = [];
    if (e.duration_ms != null) parts.push(`${(e.duration_ms / 1000).toFixed(1)}s`);
    if (e.model) parts.push(esc(e.model));
    if (e.input_tokens != null || e.output_tokens != null) parts.push(`${e.input_tokens ?? "?"} in / ${e.output_tokens ?? "?"} out tokens`);
    const detail = parts.length ? ` — ${parts.join(" · ")}` : "";
    const src = e.activity_class ? `${esc(e.source)}/${esc(e.activity_class)}` : esc(e.source || "unknown");
    return `<li><code>${esc(e.event_type)}</code> <span class="hint">[${src}]</span>${detail} <span class="hint">${esc(e.timestamp_utc)}</span></li>`;
  }).join("");
  return section("Event Ledger (live)", `
    <p class="hint" style="margin-top:0;">Evidence source: REMOTE EVENT LEDGER (Railway Postgres) &middot; Events captured: ${el.events_captured} &middot; distinguishes PRODUCT_DEVELOPMENT (building this platform) from PRODUCT_RUNTIME (Workbench runs)</p>
    <ul class="ledger-recent">${rows}</ul>
  `);
}

function renderConsumptionCategories(d) {
  const items = d.consumption_categories.map(c => `<li>${esc(c)}</li>`).join("");
  return section("Consumption Categories (schema)", `<p class="hint">Every session/run is tagged with exactly one of these — never mixed together for economics.</p><ul>${items}</ul>`);
}

function renderDevSessionControls() {
  return section("Development Session (start/stop)", `
    <p class="hint">Explicit start/stop wall-clock tracking for future Claude Code / ChatGPT development sessions. This records WALL-CLOCK time only — never inferred active/idle time.</p>
    <div class="dev-session-form">
      <input type="text" id="dev-goal" placeholder="Goal / current duty for this session" />
      <button id="dev-start-btn">START SESSION</button>
    </div>
    <div id="dev-active" class="hint"></div>
  `);
}

let activeDevSessionId = null;

function wireDevSessionControls() {
  const startBtn = document.getElementById("dev-start-btn");
  const goalInput = document.getElementById("dev-goal");
  const activeDiv = document.getElementById("dev-active");
  if (!startBtn) return;

  startBtn.addEventListener("click", async () => {
    const goal = goalInput.value.trim();
    if (!goal) return;
    const resp = await fetch("/api/dev-sessions/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal }),
    });
    const rec = await resp.json();
    activeDevSessionId = rec.id;
    activeDiv.innerHTML = `Session <code>${esc(rec.id)}</code> started. <button id="dev-stop-btn">END SESSION</button>`;
    startBtn.disabled = true;
    document.getElementById("dev-stop-btn").addEventListener("click", async () => {
      await fetch("/api/dev-sessions/stop", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: activeDevSessionId }),
      });
      activeDiv.textContent = "Session ended. Reload to see it in the list below.";
      startBtn.disabled = false;
    });
  });
}

// ---------------------------------------------------------------------
// Complete Historical Session System (P0-B): every real session ever
// captured (Claude Code dev sessions, Workbench runs, V2 trial
// benchmarks), grouped by Europe/Berlin calendar date, paginated back to
// the earliest known session — additive to everything above, which is
// unchanged. A dedicated route (/usage/session/{id}) renders a full
// detail page for one session; browser Back/Forward work via pushState.
// ---------------------------------------------------------------------

const KIND_LABELS = {
  claude_code_dev_session: "Claude Code Dev Session",
  workbench_run: "Workbench Run",
  v2_trial_benchmark: "V2 Trial Benchmark",
};

function fmtMs(ms) {
  if (ms == null) return null;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  const s = ms / 1000;
  if (s < 120) return `${s.toFixed(1)}s`;
  const m = s / 60;
  if (m < 120) return `${m.toFixed(1)} min`;
  return `${(m / 60).toFixed(1)} hr`;
}

function berlinDateKey(isoUtc) {
  if (!isoUtc) return "UNKNOWN DATE";
  const d = new Date(isoUtc);
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin", year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
}

function berlinTimeLabel(isoUtc) {
  if (!isoUtc) return "?";
  const d = new Date(isoUtc);
  return new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Berlin", hour: "2-digit", minute: "2-digit" }).format(d);
}

function tokenSummary(tokens) {
  if (!tokens) return "NOT CAPTURED";
  if (tokens.status === "EXACT") {
    const cacheParts = [];
    // Real gap found 2026-09-18: cache tokens can dominate total cost (a
    // real overnight session had 1.84 BILLION cache-read tokens driving
    // most of a real $439.87 bill) yet were entirely invisible here,
    // since only input/output were ever shown -- fixed to show them
    // whenever present, never silently dropped.
    if (tokens.cache_read_tokens) cacheParts.push(`${tokens.cache_read_tokens.toLocaleString()} cache-read`);
    if (tokens.cache_write_tokens) cacheParts.push(`${tokens.cache_write_tokens.toLocaleString()} cache-write`);
    const cacheText = cacheParts.length ? ` (+ ${cacheParts.join(", ")})` : "";
    return `${tokens.input_tokens.toLocaleString()} in / ${tokens.output_tokens.toLocaleString()} out${cacheText}`;
  }
  if (tokens.status === "AGGREGATE_ONLY") return `${tokens.aggregate_tokens} (aggregate only)`;
  return "NOT CAPTURED";
}

function costSummary(cost) {
  if (!cost) return "COST UNAVAILABLE";
  if (cost.status === "ACTUAL") return `$${cost.cost_usd < 0.01 ? cost.cost_usd.toFixed(6) : cost.cost_usd.toFixed(4)}`;
  return `COST UNAVAILABLE (${esc(cost.reason || "unknown reason")})`;
}

// Real gap found 2026-09-18: session cards/detail showed cost_display_label
// (a text label like "ACTUAL COST — CALCULATED FROM ACTUAL USAGE") in
// place of the actual dollar figure whenever a label existed, so the one
// number a viewer actually wants was never visible even when fully known
// server-side. Always show the real figure when the cost IS actual/known;
// the label is now supplementary context, never a substitute for the number.
function costText(cost, label) {
  const known = cost && cost.status === "ACTUAL" ? costSummary(cost) : null;
  if (known) return label ? `${known} — ${esc(label)}` : known;
  return esc(label || costSummary(cost));
}

function renderSessionCard(s) {
  return `<a class="hist-session-card" data-link href="/usage/session/${encodeURIComponent(s.session_id)}">
    <div class="hist-row-top">
      <span class="tag-type ${esc(s.kind)}">${esc(KIND_LABELS[s.kind] || s.kind)}</span>
      <span class="hint">${berlinTimeLabel(s.start_utc)} Europe/Berlin</span>
      ${provenanceBadge(s.provenance)}
    </div>
    <div class="hist-goal">${esc((s.goal || "").slice(0, 140))}</div>
    <div class="hist-meta">
      <span>Status: ${esc(s.status)}</span>
      <span>${s.window_kind === "OBSERVED_EVENT_WINDOW" ? "Observed window" : "Wall time"}: ${wallTimeLabel(s)}</span>
      <span>Tokens: ${tokenSummary(s.tokens)}</span>
      <span>Cost: ${costText(s.cost, s.cost_display_label)}</span>
    </div>
  </a>`;
}

function groupByBerlinDate(sessions) {
  const groups = new Map();
  for (const s of sessions) {
    const key = berlinDateKey(s.start_utc);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(s);
  }
  return groups;
}

let historyState = { sessions: [], nextCursor: null, hasMore: true, loading: false };

function renderHistoryGroups() {
  const root = document.getElementById("session-history-list");
  if (!root) return;
  const groups = groupByBerlinDate(historyState.sessions);
  const todayKey = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" }).format(new Date());
  let html = "";
  for (const [dateKey, items] of groups.entries()) {
    const label = dateKey === todayKey ? `Today — ${dateKey}` : dateKey;
    html += `<div class="hist-date-group"><h4>${esc(label)} <span class="hint">(${items.length})</span></h4>${items.map(renderSessionCard).join("")}</div>`;
  }
  root.innerHTML = html || `<p class="hint">No sessions captured yet.</p>`;
}

async function loadMoreHistory() {
  if (historyState.loading || !historyState.hasMore) return;
  historyState.loading = true;
  const btn = document.getElementById("session-history-load-more");
  if (btn) btn.textContent = "Loading…";
  try {
    const url = new URL("/api/sessions/history", window.location.origin);
    url.searchParams.set("limit", "20");
    if (historyState.nextCursor) url.searchParams.set("before", historyState.nextCursor);
    const resp = await fetch(url);
    const data = await resp.json();
    if (data.status === "REACHABLE") {
      historyState.sessions = historyState.sessions.concat(data.sessions);
      historyState.nextCursor = data.next_cursor;
      historyState.hasMore = data.has_more;
      renderHistoryGroups();
      if (data.cost_coverage_summary) renderCostCoverageSummary(data.cost_coverage_summary);
    }
  } finally {
    historyState.loading = false;
    if (btn) btn.textContent = historyState.hasMore ? "LOAD MORE" : "No more sessions — earliest reached";
    if (btn && !historyState.hasMore) btn.disabled = true;
  }
}

function renderCostCoverageSummary(s) {
  const root = document.getElementById("cost-coverage-summary");
  if (!root) return;
  root.innerHTML = `
    <div class="summary-stat"><div class="summary-label">Known Cost Total</div><div class="summary-value">$${s.known_cost_total_usd.toFixed(4)}</div></div>
    <div class="summary-stat"><div class="summary-label">Sessions w/ Known Cost</div><div class="summary-value">${s.sessions_with_known_cost}</div></div>
    <div class="summary-stat"><div class="summary-label">Sessions w/ Unknown Cost</div><div class="summary-value">${s.sessions_with_unknown_cost}</div></div>
    <div class="summary-stat"><div class="summary-label">Cost Coverage</div><div class="summary-value">${s.cost_coverage_pct != null ? s.cost_coverage_pct + "%" : "N/A"}</div></div>
  `;
}

function renderSessionHistoryPanel() {
  return section("Session History", `
    <p class="hint" style="margin-top:0;">Every real session captured (Claude Code development sessions, Workbench runs, V2 trial benchmarks) — grouped by Europe/Berlin calendar date, oldest reachable via Load More. Click a session for full detail.</p>
    <div id="cost-coverage-summary" class="summary-grid cost-coverage-grid"></div>
    <div id="session-history-list" class="hist-scroll-area"></div>
    <button id="session-history-load-more" class="load-more-btn">LOAD MORE</button>
  `);
}

function wireSessionHistoryPanel() {
  historyState = { sessions: [], nextCursor: null, hasMore: true, loading: false };
  const btn = document.getElementById("session-history-load-more");
  if (btn) btn.addEventListener("click", loadMoreHistory);
  loadMoreHistory();
}

// ---- Session detail page ------------------------------------------------

// Consistent color-coding so ACTUAL/EXACT (green), DERIVED (amber), and
// UNKNOWN/NOT_CAPTURED (muted) are visually distinguishable at a glance,
// instead of all looking like identical plain hint text (UI audit finding).
function noteClass(note) {
  if (!note) return "note-unknown";
  if (/DERIVED/i.test(note)) return "note-derived";
  if (/UNKNOWN|NOT CAPTURED/i.test(note)) return "note-unknown";
  return "note-exact";
}
function noteSpan(note) {
  return `<span class="value-note ${noteClass(note)}">${esc(note)}</span>`;
}
function provenanceBadge(provenance) {
  const cls = provenance === "LIVE_CAPTURED" ? "provenance-live" : "provenance-partial";
  return `<span class="provenance-badge ${cls}">${esc((provenance || "UNKNOWN").replace(/_/g, " "))}</span>`;
}
function shortId(id, max = 28) {
  if (!id || id.length <= max) return esc(id || "");
  return `<span title="${esc(id)}">${esc(id.slice(0, max - 1))}&hellip;</span>`;
}

function wallTimeLabel(d) {
  if (d.wall_clock_ms == null) return "UNKNOWN";
  const label = fmtMs(d.wall_clock_ms) || "UNKNOWN";
  if (d.window_kind === "OBSERVED_EVENT_WINDOW") return `${label} <span class="value-note note-derived">observed window</span>`;
  if (d.window_kind === "UNKNOWN") return "DURATION NOT CAPTURED";
  return label;
}

// RECRUITER-FACING VERIFIED-RUN P0 (2026-09-13): a recruiter arriving via
// Workbench's "SEE A VERIFIED RUN" (or anyone opening a workbench_run
// session directly) must see the real engineering OUTCOME first —
// requirement -> source change -> verification -> Git -> deployment ->
// production effect — never generic Usage/cost telemetry as the first
// thing on the page. This section is additive: it never replaces the
// existing Usage-flavored sections below it, which remain the full
// resource/cost detail (see the "VIEW FULL USAGE DETAILS" anchor link
// at the end of this section). Every value is either a real captured
// fact (agent/session_history.py::_workbench_engineering_evidence,
// itself derived only from the real event ledger) or the literal string
// "UNAVAILABLE" — never fabricated.
function evRow(label, value, ok) {
  const cls = value === "UNAVAILABLE" ? "note-unknown" : (ok === false ? "note-unknown" : "note-exact");
  return `<li><span>${esc(label)}</span><span class="value-note ${cls}">${esc(value)}</span></li>`;
}

function renderEngineeringEvidence(d) {
  const ev = d.engineering_evidence;
  if (!ev) return "";
  const isCompleted = d.status === "COMPLETED";
  return `<section class="panel verified-run-panel">
    <h2>${isCompleted ? "VERIFIED PRODUCTION RUN" : "WORKBENCH RUN — " + esc(d.status || "UNKNOWN")}</h2>
    <p class="hint">Requirement: <strong>${esc(ev.requirement)}</strong></p>
    <ul class="score-breakdown">
      ${evRow("Run ID", d.session_id)}
      ${evRow("Normalized operation", ev.human_name)}
      ${evRow("Requested value", ev.requested_value)}
      ${evRow("Changed file", ev.changed_file)}
    </ul>
    ${ev.diff_old_line !== "UNAVAILABLE" ? `<pre class="verification-summary">- ${esc(ev.diff_old_line)}\n+ ${esc(ev.diff_new_line)}</pre>` : ""}
    <ul class="score-breakdown">
      ${evRow("Testing", ev.testing_state)}
      ${ev.testing_reason !== "UNAVAILABLE" ? `<li class="score-breakdown-note">${esc(ev.testing_reason)}</li>` : ""}
      ${evRow("Local commit (isolated workspace)", ev.local_commit_sha)}
      ${evRow("Branch", ev.local_commit_branch)}
      ${evRow("GitHub push", ev.github_push_status)}
      ${evRow("Railway deployment ID", ev.railway_deployment_id)}
      ${evRow("Railway deployment status", ev.railway_deployment_status)}
      ${evRow("Deployment identity confirmed", ev.deployment_identity_confirmed === true ? "yes" : ev.deployment_identity_confirmed === false ? "no" : "UNAVAILABLE", ev.deployment_identity_confirmed === true)}
      ${evRow("Requested effect verified in production", ev.requested_effect_verified === true ? "yes" : ev.requested_effect_verified === false ? "no" : "UNAVAILABLE", ev.requested_effect_verified === true)}
      ${evRow("Observed production value", ev.observed_production_value)}
    </ul>
    ${ev.production_url !== "UNAVAILABLE" ? `<a class="secondary open-app-link" href="${esc(ev.production_url)}" target="_blank" rel="noopener">OPEN LIVE CUSTOMER APP ↗</a>` : ""}
    ${ev.final_result_text !== "UNAVAILABLE" ? `<p class="hint" style="margin-top:0.75rem;">${esc(ev.final_result_text)}</p>` : ""}
    <p class="hint" style="margin-top:1rem;"><a href="#usage-detail">VIEW FULL USAGE DETAILS ↓</a> — model/tool usage, tokens, cost, and quality/comparison metrics for this same run.</p>
  </section>`;
}

function renderTopSummary(d) {
  const q = d.quality || {};
  const qualityDisplay = q.quality_score != null ? `${q.quality_score}` : (q.quality_score_label || "NOT SCORED");
  const coverageDisplay = q.evidence_coverage_pct != null ? `${q.evidence_coverage_pct}%` : "N/A";
  return `<section class="panel session-summary-panel">
    <div class="summary-head">
      <span class="tag-type ${esc(d.kind)}">${esc(KIND_LABELS[d.kind] || d.kind)}</span>
      ${provenanceBadge(d.provenance)}
      <span class="hint session-id-hint">${shortId(d.session_id)}</span>
    </div>
    <h2 class="session-goal">${esc(d.goal || "NOT CAPTURED")}</h2>
    <div class="summary-grid">
      <div class="summary-stat"><div class="summary-label">Status</div><div class="summary-value">${esc(d.status)}</div></div>
      <div class="summary-stat"><div class="summary-label">Start &rarr; End</div><div class="summary-value">${d.start_utc ? berlinTimeLabel(d.start_utc) : "?"} &rarr; ${d.end_utc ? berlinTimeLabel(d.end_utc) : "?"}</div></div>
      <div class="summary-stat"><div class="summary-label">Wall time</div><div class="summary-value">${wallTimeLabel(d)}</div></div>
      <div class="summary-stat"><div class="summary-label">Tokens</div><div class="summary-value">${tokenSummary(d.tokens)}</div></div>
      <div class="summary-stat"><div class="summary-label">Cost</div><div class="summary-value">${costText(d.cost, d.cost_display_label)}</div></div>
      <div class="summary-stat"><div class="summary-label">Quality</div><div class="summary-value">${esc(qualityDisplay)}</div></div>
      <div class="summary-stat"><div class="summary-label">Evidence Coverage</div><div class="summary-value">${coverageDisplay}</div></div>
      <div class="summary-stat"><div class="summary-label">Value</div><div class="summary-value">${d.value ? d.value.technical_value.verified_changes_completed + " verified" : "N/A"}</div></div>
    </div>
  </section>`;
}

function renderQualityBlock(q) {
  if (!q) return "";
  const factRows = Object.entries(q.scored_dimensions || {}).map(([k, v]) =>
    `<li><span>${esc(k.replace(/_/g, " "))}</span><span>${v ? "yes" : "no"}</span></li>`
  ).join("");
  const availRows = Object.entries(q.evidence_availability || {}).map(([k, v]) =>
    `<li><span>${esc(k.replace(/_/g, " "))}</span><span class="value-note ${v ? "note-exact" : "note-unknown"}">${v ? "captured" : "not captured"}</span></li>`
  ).join("");
  const confClass = q.overall_confidence === "HIGH_CONFIDENCE" ? "note-exact" : q.overall_confidence === "PARTIAL" ? "note-derived" : "note-unknown";
  const qualityDisplay = q.quality_score != null ? `${q.quality_score}/100` : (q.quality_score_label || "NOT SCORED");
  return `
    <p><strong>Quality score:</strong> <span class="value-note ${q.quality_score != null ? "note-exact" : "note-unknown"}">${esc(qualityDisplay)}</span>
      <span class="hint">— this project has no composite quality-scoring algorithm yet; this is intentionally NOT the same number as Evidence Coverage below.</span></p>
    <p class="hint" style="margin-top:0;">Session facts:</p>
    <ul class="score-breakdown">${factRows}</ul>
    <p class="hint">Evidence actually captured (drives Evidence Coverage below — this is NOT a quality score):</p>
    <ul class="score-breakdown">${availRows}</ul>
    <p><strong>Evidence coverage: ${q.evidence_coverage_pct}%</strong> — overall: <span class="value-note ${confClass}">${esc(q.overall_confidence)}</span></p>`;
}

function renderComparisonBlock(c) {
  if (!c) return "<p class=\"hint\">No comparison data.</p>";
  if (c.status === "INSUFFICIENT_COMPARABLE_HISTORY") {
    return `<p class="hint">INSUFFICIENT COMPARABLE HISTORY (only ${c.cohort_size} comparable session(s) in the last 7 days — need at least 3).</p>`;
  }
  const parts = [`<p class="hint">Compared against ${c.cohort_size} comparable session(s) — ${esc(c.cohort_basis)}.</p>`];
  if (c.tokens_vs_cohort_median) {
    const t = c.tokens_vs_cohort_median;
    parts.push(`<p>Tokens: ${t.this_session} vs. cohort median ${Math.round(t.cohort_median)} (${t.pct_diff > 0 ? "+" : ""}${t.pct_diff}%)</p>`);
  }
  if (c.cost_vs_cohort_median) {
    const cst = c.cost_vs_cohort_median;
    parts.push(`<p>Cost: $${cst.this_session.toFixed(4)} vs. cohort median $${cst.cohort_median.toFixed(4)} (${cst.pct_diff > 0 ? "+" : ""}${cst.pct_diff}%)</p>`);
  }
  if (c.wall_time_vs_cohort_median_ms) {
    const w = c.wall_time_vs_cohort_median_ms;
    parts.push(`<p>Wall time: ${fmtMs(w.this_session)} vs. cohort median ${fmtMs(w.cohort_median)} (${w.pct_diff > 0 ? "+" : ""}${w.pct_diff}%)</p>`);
  }
  if (c.human_intervention_vs_cohort) {
    const h = c.human_intervention_vs_cohort;
    parts.push(`<p>Human intervention: ${h.this_session ? "yes" : "no"} this session vs. ${h.cohort_intervention_rate_pct}% of the cohort</p>`);
  }
  if (parts.length === 1) {
    parts.push(`<p class="hint">No individual metric had enough comparable known values (needs &ge;3) — cohort size alone isn't a useful comparison.</p>`);
  }
  return parts.join("");
}

function renderTimelineBlock(timeline) {
  if (!timeline || !timeline.length) return `<p class="hint">No timeline events captured.</p>`;
  const rows = timeline.slice(0, 200).map(t =>
    `<li><span class="hint">${berlinTimeLabel(t.timestamp_utc)}</span> <code>${esc(t.event_type)}</code>${t.tool_name ? ` — ${esc(t.tool_name)}` : ""}${t.status ? ` <span class="hint">[${esc(t.status)}]</span>` : ""}</li>`
  ).join("");
  return `<ul class="ledger-recent">${rows}</ul>${timeline.length > 200 ? `<p class="hint">${timeline.length - 200} more event(s) not shown.</p>` : ""}`;
}

async function renderSessionDetail(sessionId) {
  main.innerHTML = `<p class="hint">Loading session ${esc(sessionId)}…</p>`;
  let d;
  try {
    const resp = await fetch(`/api/sessions/history/${encodeURIComponent(sessionId)}`);
    if (resp.status === 404) {
      main.innerHTML = `<section class="panel"><h2>Not Found</h2><p>No session found with id <code>${esc(sessionId)}</code>.</p><a data-link href="/usage">&larr; Back to Usage</a></section>`;
      return;
    }
    d = await resp.json();
  } catch (e) {
    main.innerHTML = `<p class="hint">Failed to load session: ${esc(e.message)}</p>`;
    return;
  }

  main.innerHTML = `
    <a data-link href="/usage" class="back-link">&larr; Back to Usage</a>
    ${renderEngineeringEvidence(d)}
    <div id="usage-detail"></div>
    ${renderTopSummary(d)}
    ${section("Timing (AI Activity / Human Activity)", `
      <ul class="score-breakdown">
        <li><span>Start (Europe/Berlin)</span><span>${d.start_utc ? berlinTimeLabel(d.start_utc) + " on " + berlinDateKey(d.start_utc) : "UNKNOWN"}</span></li>
        <li><span>End (Europe/Berlin)</span><span>${d.end_utc ? berlinTimeLabel(d.end_utc) + " on " + berlinDateKey(d.end_utc) : "UNKNOWN"}</span></li>
        <li><span>${d.window_kind === "OBSERVED_EVENT_WINDOW" ? "Observed event window" : "Wall-clock duration"}</span><span>${wallTimeLabel(d)}</span></li>
        ${d.window_note ? `<li class="score-breakdown-note">${esc(d.window_note)}</li>` : ""}
        <li><span>AI active time</span><span>${fmtMs(d.ai_active_ms) || "UNKNOWN"} ${noteSpan(d.ai_active_ms_note)}</span></li>
        <li><span>AI waiting for human</span><span>${fmtMs(d.ai_waiting_for_human_ms) || "UNKNOWN"} ${noteSpan(d.ai_waiting_for_human_note)}</span></li>
        <li><span>Human active time</span><span>UNKNOWN ${noteSpan(d.human_active_note)}</span></li>
        <li><span>Human waiting for AI</span><span>${fmtMs(d.human_waiting_for_ai_ms) || "UNKNOWN"} ${noteSpan(d.human_waiting_for_ai_note)}</span></li>
      </ul>
    `)}
    ${section("Model Usage, Tokens & Cost", `
      <p><strong>Tokens:</strong> ${tokenSummary(d.tokens)} <span class="value-note ${d.tokens && d.tokens.status === "EXACT" ? "note-exact" : d.tokens && d.tokens.status === "AGGREGATE_ONLY" ? "note-derived" : "note-unknown"}">${esc((d.tokens && d.tokens.status) || "")}</span></p>
      <p><strong>Cost:</strong> ${costText(d.cost, d.cost_display_label)}</p>
      <p class="hint">Model: ${esc(d.model || "not recorded for this session kind")}</p>
    `)}
    ${section("Value", `
      <p><strong>Technical value:</strong> ${d.value.technical_value.verified_changes_completed} verified change(s), ${d.value.technical_value.failures} failure(s)</p>
      <p><strong>Learning value:</strong> ${d.value.learning_value.knowledge_candidates_created} knowledge candidate(s) linked to this session</p>
    `)}
    ${section("Quality (evidence-coverage-gated, never assumed 100%)", renderQualityBlock(d.quality))}
    ${section("Comparison to Other Sessions", renderComparisonBlock(d.comparison))}
    ${section(`Timeline & Runs/Tasks (${d.tool_call_count} tool call(s))`, renderTimelineBlock(d.timeline))}
    ${section("Human Interventions", d.human_interventions && d.human_interventions.length
      ? `<ul class="ledger-recent">${d.human_interventions.map(h => `<li>${esc(h.event_type)} — ${esc(h.status)} <span class="hint">${berlinTimeLabel(h.timestamp_utc)}</span></li>`).join("")}</ul>`
      : `<p class="hint">None captured for this session.</p>`)}
    ${d.raw_capture ? section("Original Instruction / Raw Capture", `
      <details class="raw-capture-details">
        <summary>Show the complete original text (${d.raw_capture.length.toLocaleString()} characters)</summary>
        <pre class="raw-capture-text">${esc(d.raw_capture)}</pre>
      </details>
    `) : ""}
    ${section("Full Session ID", `<p class="full-session-id">${esc(d.session_id)}</p>`)}
  `;
}

// ---- Router: /usage (main) vs. /usage/session/{id} (detail) ------------

function currentSessionIdFromPath() {
  const m = window.location.pathname.match(/^\/usage\/session\/(.+)$/);
  return m ? decodeURIComponent(m[1]) : null;
}

async function route() {
  const sessionId = currentSessionIdFromPath();
  if (sessionId) {
    await renderSessionDetail(sessionId);
    return;
  }
  await load();
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("a[data-link]");
  if (!link) return;
  e.preventDefault();
  const href = link.getAttribute("href");
  if (href !== window.location.pathname) history.pushState(null, "", href);
  route();
});
window.addEventListener("popstate", route);

async function load() {
  let data;
  try {
    const resp = await fetch("/api/sessions");
    data = await resp.json();
  } catch (e) {
    main.innerHTML = `<p class="hint">Failed to load session data: ${esc(e.message)}</p>`;
    return;
  }

  main.innerHTML = [
    renderEfficiencySummary(data),
    renderDevSessionCostSummary(data),
    renderEventLedger(data),
    renderDevSessionControls(),
    renderSessionHistoryPanel(),
    renderToday(data),
    renderCoverageExplainer(),
    renderValueLedger(data),
    renderImprovement(data),
    renderAllSessions(data),
    renderConsumptionCategories(data),
  ].join("");

  wireDevSessionControls();
  wireSessionHistoryPanel();

  main.querySelectorAll(".session-row").forEach(row => {
    row.addEventListener("click", () => row.classList.toggle("expanded"));
  });
}

route();
