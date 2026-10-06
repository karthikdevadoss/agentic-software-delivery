// /triage/evidence -- renders agent/web/triage-evidence.json exactly as
// published by agent/publish_triage_results.py. Only sums of published
// counts are computed here; no score exists and none is shown.

const teMain = document.getElementById("te-main");

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function section(title, html, cls) {
  return `<section class="panel ${cls || ""}"><h2>${esc(title)}</h2>${html}</section>`;
}

function javaCell(t) {
  const r = t.result;
  if (!r) return `<span class="badge st-gap">NOT RUN</span>`;
  const passed = r.tests - r.failures - r.errors - r.skipped;
  if (r.failures || r.errors) return `<span class="badge st-fail">${passed}/${r.tests} PASS</span>`;
  if (r.skipped === r.tests) return `<span class="badge st-gap">${r.skipped} SKIPPED</span>`;
  return `<span class="badge st-ok">${passed}/${r.tests} PASS</span>${r.skipped ? ` <span class="badge st-gap">${r.skipped} skipped</span>` : ""}`;
}

function totals(d) {
  const t = { run: 0, passed: 0, failed: 0, skipped: 0, notRun: 0 };
  d.scenarios.forEach((s) => s.java_integration_tests.forEach((j) => {
    if (!j.result) { t.notRun += 1; return; }
    t.run += j.result.tests;
    t.failed += j.result.failures + j.result.errors;
    t.skipped += j.result.skipped;
    t.passed += j.result.tests - j.result.failures - j.result.errors - j.result.skipped;
  }));
  return t;
}

function renderGlance(d) {
  const t = totals(d);
  const inCat = d.scenarios.filter((s) => s.in_catalogue).length;
  const py = Object.values(d.python_tests || {}).filter(Boolean);
  const pyRun = py.reduce((a, r) => a + r.tests, 0);
  const pyPassed = py.reduce((a, r) => a + r.passed, 0);
  const env = d.environment || {};
  return section("At a glance", `
    <div class="metric-grid">
      <div class="metric-card"><div class="m-label">Scenarios</div><div class="m-score">${d.scenarios.length}</div><div class="m-threshold">${inCat} in the catalogue, ${d.scenarios.length - inCat} Java-only</div></div>
      <div class="metric-card ${t.failed ? "failed" : ""}"><div class="m-label">Java integration tests (real Spring context)</div><div class="m-score">${t.passed}/${t.run}</div><div class="m-threshold">passed${t.skipped ? `, ${t.skipped} skipped` : ""}${t.failed ? `, ${t.failed} failed` : ""}${t.notRun ? `, ${t.notRun} classes not run` : ""}</div></div>
      <div class="metric-card"><div class="m-label">Agent-side Python tests (offline)</div><div class="m-score">${pyPassed}/${pyRun}</div><div class="m-threshold">passed</div></div>
      <div class="metric-card"><div class="m-label">Diagnosis accuracy</div><div class="m-score">—</div><div class="m-threshold">not measured: no labelled set</div></div>
    </div>
    <p class="hint" style="margin-top:0.9rem">Published ${esc(d.generated_at)} at commit <code>${esc((d.commit_sha || "").slice(0, 7))}</code>${d.working_tree_dirty ? " (uncommitted changes present)" : ""}. Environment: ${esc(env.java || "no JDK")}; Docker ${env.docker_available ? "available" : "not available"}; model API key ${env.anthropic_key_configured ? "configured" : "not configured"}.</p>`);
}

function renderScenarios(d) {
  const rows = d.scenarios.map((s) => {
    const java = s.java_integration_tests.map((j) => `<div><code>${esc(j.class)}</code> ${javaCell(j)}</div>`).join("") || "—";
    const page = s.walkthrough_page ? `<a href="${esc(s.walkthrough_page)}">${esc(s.walkthrough_page)}</a>` : "none";
    const cat = s.in_catalogue ? `<span class="badge st-ok">IN CATALOGUE</span>` : `<span class="badge st-partial">JAVA ONLY</span>`;
    return `<tr><td><strong>${esc(s.letter)}</strong></td><td>${esc(s.title)}<div class="hint" style="margin-top:0.3rem">${esc(s.engineering_area || "")}</div></td><td>${cat}</td><td>${page}</td><td>${java}</td></tr>`;
  }).join("");
  return section("Scenarios and their evidence", `
    <table class="cap-table te-table"><thead><tr><th>Id</th><th>Scenario</th><th>Catalogue</th><th>Walkthrough</th><th>Java integration tests</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="hint" style="margin-top:0.8rem">Every scenario is a real defect from this codebase's history, replayed in isolation. Catalogue = <a href="${esc(d.sources.catalogue)}" target="_blank" rel="noopener">triage/scenarios.yaml</a>; tests = <a href="${esc(d.sources.java_tests)}" target="_blank" rel="noopener">Java triage tests</a>.</p>`, "te-scenarios");
}

function renderPython(d) {
  const rows = Object.entries(d.python_tests || {}).map(([m, r]) => r
    ? `<tr><td><code>${esc(m)}</code></td><td>${r.ok ? `<span class="badge st-ok">${r.passed}/${r.tests} PASS</span>` : `<span class="badge st-fail">${r.passed}/${r.tests} PASS</span>`}</td></tr>`
    : `<tr><td><code>${esc(m)}</code></td><td><span class="badge st-gap">NO RESULT</span></td></tr>`).join("");
  return section("Agent-side tests", `<p class="hint">The orchestration, diagnosis prompt handling, candidate-patch compile/verify and promotion pipeline, tested offline with HTTP and the model replaced by fakes.</p>
    <table class="cap-table te-table"><tbody>${rows}</tbody></table>`);
}

function renderNotRun(d) {
  const items = d.not_run.map((n) => `<li><strong>${esc(n.what)}</strong> — ${esc(n.why)}</li>`).join("");
  return section("Not run, and why", `<ul class="limits">${items}</ul>`);
}

function renderTriageEvidence(d) {
  teMain.innerHTML = renderGlance(d) + renderScenarios(d) + renderPython(d) + renderNotRun(d)
    + `<p class="hint">Sources: <a href="${esc(d.sources.engine)}" target="_blank" rel="noopener">triage engine</a> · <a href="${esc(d.sources.design)}" target="_blank" rel="noopener">design notes</a> · <a href="${esc(d.sources.publisher)}" target="_blank" rel="noopener">evidence publisher</a></p>`;
}

if (typeof document !== "undefined" && teMain) {
  fetch("/triage-evidence.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(renderTriageEvidence)
    .catch((err) => {
      teMain.innerHTML = section("Triage evidence unavailable", `<p>Could not load triage-evidence.json (${esc(err.message)}). Nothing is shown rather than invented numbers.</p>`);
    });
}
