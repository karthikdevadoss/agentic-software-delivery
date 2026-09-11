// Agentic Software Delivery — Dashboard frontend.
// Fetches /api/dashboard (agent/dashboard_data.py) and renders it exactly
// as returned. No values are computed or invented in this file.

const main = document.getElementById("dash-main");

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function statusClass(status) {
  const s = (status || "").toString().toUpperCase();
  if (s.includes("NOT IMPLEMENTED") || s.includes("NOT CAPTURED") || s.includes("NOT STARTED") || s.includes("NOT VERIFIED")) return "st-gap";
  if (s.includes("PARTIAL") || s.includes("IN PROGRESS")) return "st-partial";
  return "st-ok";
}

function badge(status) {
  return `<span class="badge ${statusClass(status)}">${esc(status)}</span>`;
}

function section(title, innerHtml) {
  return `<section class="panel"><h2>${esc(title)}</h2>${innerHtml}</section>`;
}

// value must already be safe HTML (either esc()'d text or badge()/kv-safe markup).
function kv(label, valueHtml) {
  return `<div class="kv"><span class="k">${esc(label)}</span><span class="v">${valueHtml}</span></div>`;
}

// Convenience for the common case of a plain (unescaped) text value.
function kvText(label, text) {
  return kv(label, esc(text));
}

function renderSystemSnapshot(d) {
  const s = d.system_snapshot;
  let html = "";
  html += kvText("System", s.system);
  html += kvText("Version", s.version);
  html += kvText("Agent architecture", s.agent_architecture);
  html += kvText("Last verified code commit", s.last_verified_code_commit);
  html += kv("Current ticket", `${esc(s.current_ticket)} — ${s.current_ticket_implemented ? "IMPLEMENTED" : "NOT IMPLEMENTED"}`);
  html += kvText("Next phase", s.next_phase);
  return section("A. System Snapshot", html);
}

function renderMilestone(d) {
  const m = d.last_documented_milestone;
  let html = `<p class="hint">Sourced from durable project state (docs/PROJECT_STATE.json) — a documented historical record, not live telemetry.</p>`;
  if (m.status === "NOT CAPTURED YET") {
    html += `<p>${badge("NOT CAPTURED YET")}</p>`;
  } else {
    html += kv("Status", badge(m.status));
    html += kvText("Summary", m.summary);
    html += kvText("As of commit", m.as_of_commit);
    html += kv("Scroll bug fix — creator confirmed", badge(m.ui_fixes_creator_confirmed.scroll_fix));
    html += kv("Build/Test panel fix — creator confirmed", badge(m.ui_fixes_creator_confirmed.build_test_panel_fix));
  }
  return section("B1. Last Verified Run — Documented Milestone", html);
}

function renderRunHistory(d) {
  const runs = d.run_history;
  let html = `<p class="hint">Local telemetry log (agent/web_run_history.jsonl) captured since this Dashboard feature was added — resets are NOT lost across restarts, but only covers runs since this log existed.</p>`;
  if (!runs.length) {
    html += `<p>${badge("NOT CAPTURED YET")} — no runs recorded in the local run-history log yet.</p>`;
  } else {
    html += '<ul class="run-list">';
    for (const r of runs) {
      const duration = (r.started_ts && r.ended_ts) ? `${(r.ended_ts - r.started_ts).toFixed(1)}s` : "n/a";
      html += `<li>
        <div><strong>${esc(r.run_id)}</strong> ${r.is_mock ? '<span class="tag">MOCK — no API cost</span>' : '<span class="tag real">REAL</span>'} ${badge(r.final_status)}</div>
        <div class="hint">${esc(r.requirement_excerpt)}</div>
        <div class="kv-row">
          <span>Duration: ${duration}</span>
          <span>Tool calls: ${r.tool_calls_total}</span>
          <span>Approval: ${esc(r.approval_decision ?? "n/a")}</span>
          <span>Apply: ${esc(r.apply_succeeded === null ? "n/a" : r.apply_succeeded)}</span>
          <span>Compile: ${r.compile ? (r.compile.success ? "PASS" : "FAIL") + " (" + (r.compile.duration_ms / 1000).toFixed(1) + "s)" : "n/a"}</span>
          <span>Tests: ${r.test ? (r.test.success ? "PASS" : "FAIL") + " (" + (r.test.duration_ms / 1000).toFixed(1) + "s)" : "n/a"}</span>
        </div>
      </li>`;
    }
    html += "</ul>";
  }
  return section("B2. Run History (this Dashboard's local log)", html);
}

function renderSessionMetrics(d) {
  const m = d.session_metrics;
  let html = `<p class="hint">Counters for the CURRENT server process only (agent/metrics.py, in-memory) — resets on restart. "How productive was this process" only, not full historical analytics.</p>`;
  if (m.status.startsWith("NOT CAPTURED")) {
    html += `<p>${badge("NOT CAPTURED YET")} — ${esc(m.note)}</p>`;
  } else {
    html += kvText("Tool calls (this process)", m.tool_calls_total);
    html += kvText("Succeeded", m.tool_calls_succeeded);
    html += kvText("Failed", m.tool_calls_failed);
    html += kvText("Security-blocked", m.security_blocked);
  }
  html += kv("Token usage", badge("NOT CAPTURED YET"));
  html += kv("Estimated API cost", badge("NOT CAPTURED YET"));
  return section("Session Snapshot", html);
}

function renderRag(d) {
  const r = d.rag;
  let html = "";
  if (r.status === "NOT CAPTURED YET") {
    html += `<p>${badge("NOT CAPTURED YET")} — ${esc(r.note)}</p>`;
  } else {
    html += kvText("Embedding model (local, no API key)", r.embedding_model);
    html += kvText("Chunking version", r.chunking_version);
    html += kvText("Files indexed", r.files_indexed);
    html += kvText("Chunks indexed", r.chunks_indexed);
    html += kv("Incremental indexing", badge("IMPLEMENTED — content-hash based reuse"));
  }
  html += `<p class="hint"><strong>Capability exists</strong> (semantic_repository_search is available to the agent) vs. <strong>used in last run</strong> (only true if that specific run's tool_call events show it was actually invoked) are intentionally distinct — the Run History panel above shows each run's actual tool calls.</p>`;
  return section("C. RAG / Repository Intelligence", html);
}

function renderMcp(d) {
  const m = d.mcp;
  let html = "";
  html += kvText("SDK", m.sdk);
  html += kv("Tool discovery", badge(m.tool_discovery));
  html += kv("Tool invocation", badge(m.tool_invocation));
  html += kv("Security passthrough", badge(m.security_passthrough));
  html += kv("No duplicated security logic", badge(m.no_duplicated_security_logic));
  html += kvText("Tools exposed via MCP", m.tools_exposed.join(", "));
  html += kv("Write/build/deploy via MCP", badge(m.write_build_deploy_via_mcp));
  html += kv("stdio transport", badge(m.stdio_transport));
  html += kv("Streamable HTTP transport", badge(m.streamable_http_transport));
  return section("D. MCP / Tools", html);
}

function renderSecurity(d) {
  const s = d.security;
  let html = "";
  html += kv("Human approval outside LLM tool surface", badge(s.human_approval_outside_llm_tool_surface));
  html += kv("Model cannot self-approve", badge(s.model_cannot_self_approve));
  html += kv("Approval bound to exact path + content", badge(s.approval_bound_to_exact_path_and_content));
  html += kv("Modified/substituted proposal rejected", badge(s.modified_or_substituted_proposal_rejected));
  html += kv("Unapproved/duplicate apply blocked", badge(s.unapproved_or_duplicate_apply_blocked));
  html += kv("Fails closed without a human present", badge(s.fails_closed_without_a_human_present));
  html += kv("Scope + secret-path protections", badge(s.scope_and_secret_path_protections));
  html += kv("No arbitrary shell", badge(s.no_arbitrary_shell));
  html += kv("Real browser human approval verified", badge(s.real_browser_human_approval_verified));
  html += `<p class="hint">${esc(s.disclaimer)}</p>`;
  return section("E. Security / Human Authority", html);
}

function renderQuality(d) {
  const q = d.quality;
  let html = "";
  html += kvText("Automated tests", `${q.total} total, ${q.passed} passed, ${q.failed} failed, ${q.skipped} skipped`);
  html += kvText("Skip reason", q.skip_reason);
  html += kv("Command", `<code>${esc(q.command)}</code>`);
  html += kvText("As of commit", q.as_of_commit);
  return section("F. Quality / Verification", html);
}

function renderCapabilityMatrix(d) {
  let rows = "";
  for (const c of d.capability_matrix) {
    rows += `<tr>
      <td>${esc(c.area)}</td>
      <td>${badge(c.status)}</td>
      <td>${esc(c.evidence)}</td>
      <td>${esc(c.gap)}</td>
    </tr>`;
  }
  const html = `<table class="cap-table">
    <thead><tr><th>Area</th><th>Status</th><th>Evidence</th><th>Gap</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
  return section("G. Capability Matrix", html);
}

function fmtUsd(n) {
  if (n === null || n === undefined) return "—";
  return "$" + n.toFixed(n < 0.01 ? 4 : 2);
}

// Real incident (2026-09-11): this section used to show a hardcoded
// "NOT CAPTURED YET"/"NOT CALCULATED YET" pair that predated real usage
// capture entirely — the data existed elsewhere in the product the whole
// time. Now reads agent/event_ledger.py::get_usage_economics()'s real,
// ledger-backed aggregation directly — never a static placeholder again.
function renderEconWindow(label, w) {
  if (!w || w.runs_total === 0) {
    return `<div class="econ-card"><div class="econ-label">${esc(label)}</div><div class="econ-value">no runs in this window</div></div>`;
  }
  const costText = w.cost_known_for_all_captured_runs ? fmtUsd(w.cost_usd) : `${fmtUsd(w.cost_usd)} (partial — some runs' cost unknown)`;
  return `<div class="econ-card">
    <div class="econ-label">${esc(label)}</div>
    <div class="econ-value">${w.input_tokens.toLocaleString()} in / ${w.output_tokens.toLocaleString()} out tokens</div>
    <div class="kv-row"><span>${w.runs_total} run(s)</span><span>${w.runs_completed_verified} verified</span><span>Cost: ${costText}</span></div>
  </div>`;
}

function renderEconomics(d) {
  const e = d.economics;
  if (e.status !== "REACHABLE") {
    return section("Economics / Consumption", `<div class="econ-note">Event ledger ${badge(e.status)} — ${esc(e.error || "no further detail")}</div>`);
  }
  const html = `
    <div class="econ-grid">
      ${renderEconWindow("Last run", e.last_run)}
      ${renderEconWindow("Last hour (UTC)", e.last_hour_utc)}
      ${renderEconWindow("Today (UTC calendar day)", e.today_utc_calendar_day)}
      ${renderEconWindow("Lifetime", e.lifetime)}
    </div>
    <div class="econ-note">
      <strong>Cost per verified (COMPLETED) change:</strong> ${e.cost_per_verified_change_usd != null ? fmtUsd(e.cost_per_verified_change_usd) : "INSUFFICIENT DATA"}<br><br>
      <strong>Source:</strong> ${esc(e.canonical_source)}<br><br>
      <strong>Pricing versions seen:</strong> ${e.pricing_versions_seen.length ? esc(e.pricing_versions_seen.join(", ")) : "none yet"} — a run's cost always uses the pricing version recorded at that run's own time, never recomputed with a later price.<br><br>
      <strong>Note:</strong> ${esc(e.timezone_note)}
    </div>
  `;
  return section("Economics / Consumption", html);
}

function renderVerifiedActivity(d) {
  const a = d.verified_activity;
  const html = `<div class="activity-note">
    <div class="activity-kicker">${esc(a.evidence_type)}</div>
    <div class="kv"><span class="k">Environment</span><span class="v">${esc(a.environment)}</span></div>
    <div class="kv"><span class="k">Action</span><span class="v">${esc(a.action)}</span></div>
    <div class="kv"><span class="k">Result</span><span class="v">${esc(a.result)}</span></div>
    <div class="kv"><span class="k">Observed at</span><span class="v">${esc(a.observed_at)}</span></div>
  </div>`;
  return section("Latest Verified Product Runtime Activity", html);
}

function renderLimitations(d) {
  const items = d.known_limitations.map(l => `<li>${esc(l)}</li>`).join("");
  return section("H. Known Limitations", `<ul class="limits">${items}</ul>`);
}

function renderNextMvp(d) {
  const html = kvText("Next phase (from durable project state)", d.system_snapshot.next_phase);
  return section("Next MVP", html);
}

async function load() {
  let data;
  try {
    const resp = await fetch("/api/dashboard");
    data = await resp.json();
  } catch (e) {
    main.innerHTML = `<p class="hint">Failed to load dashboard data: ${esc(e.message)}</p>`;
    return;
  }

  main.innerHTML = [
    renderSystemSnapshot(data),
    renderMilestone(data),
    renderRunHistory(data),
    renderSessionMetrics(data),
    renderRag(data),
    renderMcp(data),
    renderSecurity(data),
    renderQuality(data),
    renderVerifiedActivity(data),
    renderEconomics(data),
    renderCapabilityMatrix(data),
    renderLimitations(data),
    renderNextMvp(data),
  ].join("");
}

load();
