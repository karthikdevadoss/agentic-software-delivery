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
  if (tokens.status === "EXACT") return `${tokens.input_tokens} in / ${tokens.output_tokens} out`;
  if (tokens.status === "AGGREGATE_ONLY") return `${tokens.aggregate_tokens} (aggregate only)`;
  return "NOT CAPTURED";
}

function costSummary(cost) {
  if (!cost) return "COST UNAVAILABLE";
  if (cost.status === "ACTUAL") return `$${cost.cost_usd < 0.01 ? cost.cost_usd.toFixed(6) : cost.cost_usd.toFixed(4)}`;
  return `COST UNAVAILABLE (${esc(cost.reason || "unknown reason")})`;
}

function renderSessionCard(s) {
  return `<a class="hist-session-card" data-link href="/usage/session/${encodeURIComponent(s.session_id)}">
    <div class="hist-row-top">
      <span class="tag-type ${esc(s.kind)}">${esc(KIND_LABELS[s.kind] || s.kind)}</span>
      <span class="hint">${berlinTimeLabel(s.start_utc)} Europe/Berlin</span>
      <span class="hint">${esc(s.provenance)}</span>
    </div>
    <div class="hist-goal">${esc((s.goal || "").slice(0, 140))}</div>
    <div class="hist-meta">
      <span>Status: ${esc(s.status)}</span>
      <span>Wall time: ${fmtMs(s.wall_clock_ms) || "UNKNOWN"}</span>
      <span>Tokens: ${tokenSummary(s.tokens)}</span>
      <span>Cost: ${costSummary(s.cost)}</span>
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
    }
  } finally {
    historyState.loading = false;
    if (btn) btn.textContent = historyState.hasMore ? "LOAD MORE" : "No more sessions — earliest reached";
    if (btn && !historyState.hasMore) btn.disabled = true;
  }
}

function renderSessionHistoryPanel() {
  return section("Session History", `
    <p class="hint" style="margin-top:0;">Every real session captured (Claude Code development sessions, Workbench runs, V2 trial benchmarks) — grouped by Europe/Berlin calendar date, oldest reachable via Load More. Click a session for full detail.</p>
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

function renderQualityBlock(q) {
  if (!q) return "";
  const rows = Object.entries(q.scored_dimensions || {}).map(([k, v]) =>
    `<li><span>${esc(k.replace(/_/g, " "))}</span><span>${v ? "yes" : "no"}</span></li>`
  ).join("");
  return `<ul class="score-breakdown">${rows}</ul>
    <p class="hint">Evidence coverage: ${q.evidence_coverage_pct}% — overall: ${esc(q.overall_confidence)}</p>`;
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
    <section class="panel">
      <h2>${esc(KIND_LABELS[d.kind] || d.kind)} <span class="hint">${esc(d.session_id)}</span></h2>
      <p class="goal">${esc(d.goal || "NOT CAPTURED")}</p>
      <div class="meta">
        <span>Status: ${esc(d.status)}</span>
        <span>Provenance: ${esc(d.provenance)}</span>
      </div>
    </section>
    ${section("Start / End / Timing", `
      <ul class="score-breakdown">
        <li><span>Start (Europe/Berlin)</span><span>${d.start_utc ? berlinTimeLabel(d.start_utc) + " on " + berlinDateKey(d.start_utc) : "UNKNOWN"}</span></li>
        <li><span>End (Europe/Berlin)</span><span>${d.end_utc ? berlinTimeLabel(d.end_utc) + " on " + berlinDateKey(d.end_utc) : "UNKNOWN"}</span></li>
        <li><span>Wall-clock duration</span><span>${fmtMs(d.wall_clock_ms) || "UNKNOWN"}</span></li>
        <li><span>AI active time</span><span>${fmtMs(d.ai_active_ms) || "UNKNOWN"} <span class="hint">(${esc(d.ai_active_ms_note)})</span></span></li>
        <li><span>AI waiting for human</span><span>${fmtMs(d.ai_waiting_for_human_ms) || "UNKNOWN"} <span class="hint">(${esc(d.ai_waiting_for_human_note)})</span></span></li>
        <li><span>Human active time</span><span>UNKNOWN <span class="hint">(${esc(d.human_active_note)})</span></span></li>
        <li><span>Human waiting for AI</span><span>${fmtMs(d.human_waiting_for_ai_ms) || "UNKNOWN"} <span class="hint">(${esc(d.human_waiting_for_ai_note)})</span></span></li>
      </ul>
    `)}
    ${section("Token Usage", `<p>${tokenSummary(d.tokens)}</p>`)}
    ${section("Cost", `<p>${costSummary(d.cost)}</p>`)}
    ${section("Value", `
      <p><strong>Technical value:</strong> ${d.value.technical_value.verified_changes_completed} verified change(s), ${d.value.technical_value.failures} failure(s)</p>
      <p><strong>Learning value:</strong> ${d.value.learning_value.knowledge_candidates_created} knowledge candidate(s) linked to this session</p>
    `)}
    ${section("Quality", renderQualityBlock(d.quality))}
    ${section("Comparison to Other Sessions", renderComparisonBlock(d.comparison))}
    ${section(`Timeline (${d.tool_call_count} tool call(s))`, renderTimelineBlock(d.timeline))}
    ${section("Human Interventions", d.human_interventions && d.human_interventions.length
      ? `<ul class="ledger-recent">${d.human_interventions.map(h => `<li>${esc(h.event_type)} — ${esc(h.status)} <span class="hint">${berlinTimeLabel(h.timestamp_utc)}</span></li>`).join("")}</ul>`
      : `<p class="hint">None captured for this session.</p>`)}
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
