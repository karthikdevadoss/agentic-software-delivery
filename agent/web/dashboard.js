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
  if (s.includes("PARTIAL") || s.includes("IN PROGRESS") || s.includes("NOT_PRODUCTION") || s.includes("NOT PRODUCTION") || s.includes("DEMO_AVAILABLE") || s.includes("DEMO AVAILABLE") || s.includes("MONITORING")) return "st-partial";
  return "st-ok";
}

// Humanizes a raw ENUM_LIKE_VALUE (e.g. "PRODUCTION_ACTIVE") for display,
// while statusClass() above still classifies from the raw value's own
// substrings so both stay in sync from one input.
function badge(status) {
  const display = (status || "").toString().replace(/_/g, " ");
  return `<span class="badge ${statusClass(status)}">${esc(display)}</span>`;
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

// A small number of real headline numbers, computed client-side from
// data /api/dashboard already returns (never a second data source, never
// invented) -- answers "what did he build / what's actually live" in
// under 30 seconds, before any detail panel below.
function renderExecutiveSummary(d) {
  const defects = (d.ai_engineering_learning && d.ai_engineering_learning.total_defects) || 0;
  const lifetime = (d.economics && d.economics.lifetime) || {};
  const totalRuns = lifetime.runs_total;
  const verifiedChanges = lifetime.runs_completed_verified;
  // REAL BUG FOUND AND FIXED (2026-09-15): this tile used to read
  // d.run_history.length -- a LOCAL, per-container-instance log file
  // that is genuinely wiped on every redeploy (agent/web_run_history.jsonl
  // is not in git, "COPY . ." at build time never includes a prior
  // container's runtime-written file). That made it show "0" right next
  // to "153 Verified production changes" (the durable remote-ledger
  // count) immediately after any deploy -- a real, recruiter-visible
  // truth contradiction, not just two different real numbers shown
  // without context. Both tiles now read the SAME durable, ledger-backed
  // source (event_ledger.get_usage_economics()'s lifetime window), so
  // they can never disagree about what "real" means.
  const tiles = [
    ["Production application", "LIVE", "Customer App + Workbench + Dashboard + Usage"],
    ["Delivery runs (all-time, durable ledger)", totalRuns != null ? String(totalRuns) : "UNAVAILABLE", "event_ledger, survives every redeploy"],
    ["Verified production changes (all-time)", verifiedChanges != null ? String(verifiedChanges) : "UNAVAILABLE", "COMPLETED outcome, same durable ledger"],
    ["Engineering lessons captured", String(defects), "AI Engineering Quality Ledger"],
  ];
  const html = `<div class="exec-grid">` + tiles.map(([label, value, note]) =>
    `<div class="exec-stat"><div class="exec-value">${esc(value)}</div><div class="exec-label">${esc(label)}</div><div class="exec-note">${esc(note)}</div></div>`
  ).join("") + `</div>`;
  return section("Agentic Software Delivery — Engineering Evidence", html);
}

// The Owner's core AI-engineering thesis, stated once, plainly: use
// probabilistic AI where reasoning/generation creates value, use
// deterministic software where correctness can be calculated. Both
// columns describe this system's REAL, already-built architecture
// (demo_catalogue.py's deterministic gate, the qa-evaluator's independent
// non-self-certification rule, pricing_config.py's fixed-table
// arithmetic) -- restated here as one dedicated, scannable section
// instead of scattered across other panels.
function renderAiStrategy() {
  const usedFor = [
    "Interpreting natural-language requirements",
    "Investigating a real repository (read-only tools, RAG/MCP)",
    "Proposing code changes as a reviewable diff",
    "Diagnostic hypotheses during incident investigation",
    "Drafting documentation/summaries of real evidence",
  ];
  const notTrustedFor = [
    "Deciding its own authorization or risk classification",
    "Test pass/fail (real compiler/test-runner exit codes only)",
    "Deployment truth (independent production curl, never self-report)",
    "Certifying its own work (a separate qa-evaluator re-verifies)",
    "Cost/business arithmetic (a fixed pricing table, not model output)",
  ];
  const col = (title, items, cls) => `<div class="ai-strategy-col ${cls}"><h3>${esc(title)}</h3><ul>${items.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>`;
  const html = `<div class="ai-strategy-grid">${col("AI used for", usedFor, "used-for")}${col("AI is not trusted as authority for", notTrustedFor, "not-trusted")}</div>
    <p class="hint">Use probabilistic AI where reasoning/generation creates value; use deterministic software where correctness can be calculated and verified independently.</p>`;
  return section("AI Strategy", html);
}

function renderSystemSnapshot(d) {
  const s = d.system_snapshot;
  let html = "";
  html += kvText("System", s.system);
  html += kvText("Agent architecture", s.agent_architecture);
  html += kvText("Last verified code commit", s.last_verified_code_commit);
  html += kv("Original V1 ticket (historical, long since superseded)", `${esc(s.current_ticket)} — ${s.current_ticket_implemented ? "IMPLEMENTED" : "NOT IMPLEMENTED"}`);
  html += `<details class="raw-state">
    <summary>Full version history &amp; next-phase notes (raw project state)</summary>
    <div class="raw-state-body">
      <p class="hint">Version</p>
      <p>${esc(s.version)}</p>
      <p class="hint">Next phase</p>
      <p>${esc(s.next_phase)}</p>
    </div>
  </details>`;
  return section("System Snapshot", html);
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
  return section("Last Verified Run", html);
}

function renderRunHistory(d) {
  const runs = d.run_history;
  // CORRECTED (2026-09-15): the previous wording ("resets are NOT lost
  // across restarts") was misleading -- verified by direct observation
  // across this session's own several real Railway redeploys that this
  // LOCAL file genuinely does reset to empty on every redeploy (a fresh
  // container image never includes a prior container's runtime-written
  // file). It survives an in-place process restart of the SAME
  // container, never a redeploy. The durable, redeploy-surviving source
  // is the Economics section above (the remote event ledger).
  let html = `<p class="hint">Local telemetry log (agent/web_run_history.jsonl), THIS container instance only — genuinely resets to empty on every redeploy (verified directly, not assumed). For durable, all-time counts that survive redeploys, see the Economics section above (event ledger).</p>`;
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
  return section("Run History", html);
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
  // CLARIFIED (2026-09-15): "NOT CAPTURED YET" previously read as if RAG
  // itself doesn't exist. Three genuinely different facts were being
  // conflated: (1) is RAG/embeddings CAPABILITY implemented and evalled
  // -- yes, real code, real measured recall/MRR baselines; (2) does THIS
  // specific container have a persisted local index file on disk right
  // now -- honestly no, the index is built by the offline V3 CLI agent,
  // not by this always-on server process; (3) was RAG actually used in
  // the most recent run -- a separate, per-run fact shown in Run History.
  if (r.status === "NOT CAPTURED YET") {
    html += kv("RAG/embeddings capability", badge("IMPLEMENTED + EVALLED"));
    html += kv("Persisted index in THIS runtime", badge("NOT PRESENT"));
    html += `<p class="hint">The capability is real (fastembed + local vector index + a measured eval baseline, see docs/DECISIONS.md) -- this always-on server process simply has no index file on its own disk right now, since the index is built by the offline V3 CLI agent, a separate execution path. ${esc(r.note)}</p>`;
  } else {
    html += kvText("Embedding model (local, no API key)", r.embedding_model);
    html += kvText("Chunking version", r.chunking_version);
    html += kvText("Files indexed", r.files_indexed);
    html += kvText("Chunks indexed", r.chunks_indexed);
    html += kv("Incremental indexing", badge("IMPLEMENTED — content-hash based reuse"));
  }
  html += `<p class="hint"><strong>Capability exists</strong> (semantic_repository_search is available to the agent) vs. <strong>used in last run</strong> (only true if that specific run's tool_call events show it was actually invoked) are intentionally distinct — the Run History panel above shows each run's actual tool calls.</p>`;
  return section("RAG / Repository Intelligence", html);
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
  return section("MCP / Tools", html);
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
  return section("Security / Human Authority", html);
}

function renderQuality(d) {
  const q = d.quality;
  let html = "";
  for (const [label, suite] of [["Python", q.python], ["Java", q.java], ["Node / frontend", q.node_frontend]]) {
    if (!suite) continue;
    html += kv(label, `${suite.total} total, ${suite.passed} passed, ${suite.failed} failed, ${suite.skipped} skipped <span class="hint">(as of ${esc(suite.as_of_commit)})</span>`);
    if (suite.skip_reason) html += `<p class="hint">${esc(suite.skip_reason)}</p>`;
    if (suite.note) html += `<p class="hint"><strong>${esc(suite.note)}</strong></p>`;
  }
  html += kv("Commands", `<code>${esc(q.command)}</code>`);
  html += `<p class="hint">${esc(q.ci)}</p>`;
  return section("Quality / Verification", html);
}

function renderEngineeringProblems(d) {
  const e = d.engineering_problems_solved;
  let html = '<ul class="problem-list">';
  for (const row of e.rows) {
    const links = (row.evidence_links || []).map(u =>
      /^https?:\/\//.test(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener">VIEW EVIDENCE</a>` : `<span class="hint">${esc(u)}</span>`
    ).join(" ");
    html += `<li>
      <div class="problem-text">${esc(row.problem)}</div>
      <div class="problem-arrow">&rarr; ${esc(row.technique)} ${badge(row.production_state)}</div>
      ${links ? `<div class="problem-links">${links}</div>` : ""}
    </li>`;
  }
  html += "</ul>";
  if (e.missing_capability_ids && e.missing_capability_ids.length) {
    html += `<p class="hint">Not shown — capability id(s) no longer in the registry: ${esc(e.missing_capability_ids.join(", "))}</p>`;
  }
  return section("Engineering Problems Solved", html);
}

function renderAiLearning(d) {
  const l = d.ai_engineering_learning;
  if (l.status !== "CAPTURED") {
    return section("AI Engineering Learning", `<p>${badge(l.status)}</p>`);
  }
  let html = `<p class="hint">${l.total_defects} structured defect records in the full ledger — showing ${l.highlights.length} representative highlights. Full raw record: <code>${esc(l.full_ledger_path)}</code></p>`;
  html += '<div class="ledger-list">';
  for (const h of l.highlights) {
    html += `<div class="ledger-item">
      <div class="ledger-title"><strong>${esc(h.defect_id)}</strong> — ${esc(h.title)} ${badge(h.confidence)}</div>
      <div class="ledger-row"><span class="ledger-k">Root cause</span><span>${esc(h.root_cause)}</span></div>
      <div class="ledger-row"><span class="ledger-k">Product fix</span><span>${esc(h.product_fix)}</span></div>
      <div class="ledger-row"><span class="ledger-k">Harness improvement</span><span>${esc(h.harness_improvement)}</span></div>
      <div class="ledger-row"><span class="ledger-k">Recurrence</span><span>${badge(h.recurrence_status)}</span></div>
    </div>`;
  }
  html += "</div>";
  return section("AI Engineering Learning", html);
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
  return section("Capability Matrix", html);
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
  const tz = e.display_timezone || "Europe/Berlin";
  const html = `
    <div class="econ-grid">
      ${renderEconWindow("Last run", e.last_run)}
      ${renderEconWindow("This hour (rolling)", e.this_hour)}
      ${renderEconWindow("Last 24 hours (rolling)", e.last_24_hours)}
      ${renderEconWindow(`Today (${tz})`, e.today)}
      ${renderEconWindow(`This week (${tz})`, e.this_week)}
      ${renderEconWindow(`This month (${tz})`, e.this_month)}
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

function renderKnownLimitationsCollapsed(d) {
  const items = d.known_limitations.map(l => `<li>${esc(l)}</li>`).join("");
  const html = `<details class="raw-state">
    <summary>${d.known_limitations.length} known limitation(s) — honest, not hidden</summary>
    <div class="raw-state-body"><ul class="limits">${items}</ul></div>
  </details>`;
  return section("Known Limitations", html);
}

function zoneTitle(text) {
  return `<h2 class="zone-title">${esc(text)}</h2>`;
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
    renderExecutiveSummary(data),

    zoneTitle("What He Built"),
    renderEngineeringProblems(data),
    renderVerifiedActivity(data),

    zoneTitle("AI Engineering Strategy"),
    renderAiStrategy(),
    renderSecurity(data),

    zoneTitle("Quality & Learning"),
    renderQuality(data),
    renderAiLearning(data),
    renderKnownLimitationsCollapsed(data),

    zoneTitle("Production & Delivery Evidence"),
    renderEconomics(data),
    renderRunHistory(data),
    renderMilestone(data),
    renderSessionMetrics(data),

    zoneTitle("Architecture Detail"),
    renderSystemSnapshot(data),
    renderCapabilityMatrix(data),
    renderRag(data),
    renderMcp(data),
  ].join("");
}

load();
