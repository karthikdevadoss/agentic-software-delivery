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
  const usageHtml = s.model_usage
    ? `<div><strong>Model usage (from API response, not estimated):</strong> ${esc(s.model_usage.provider)}/${esc(s.model_usage.model)} — ${s.model_usage.input_tokens} input tokens, ${s.model_usage.output_tokens} output tokens across ${s.model_usage.api_calls} call(s). Cost: NOT CALCULATED YET.</div>`
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
    renderDevSessionControls(),
    renderToday(data),
    renderCoverageExplainer(),
    renderValueLedger(data),
    renderImprovement(data),
    renderAllSessions(data),
    renderConsumptionCategories(data),
  ].join("");

  wireDevSessionControls();

  main.querySelectorAll(".session-row").forEach(row => {
    row.addEventListener("click", () => row.classList.toggle("expanded"));
  });
}

load();
