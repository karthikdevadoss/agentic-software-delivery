// /eval page -- renders agent/web/eval-results.json exactly as published by
// agent/publish_eval_results.py. No score, threshold or verdict is computed
// or invented here; the only arithmetic is bar widths for display.

const evalMain = document.getElementById("eval-main");

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function fmt(n) {
  return typeof n === "number" ? n.toFixed(3) : "n/a";
}

function pct(n) {
  return typeof n === "number" ? Math.max(0, Math.min(100, n * 100)) : 0;
}

function passBadge(passed) {
  return passed
    ? '<span class="badge st-ok">PASS</span>'
    : '<span class="badge st-fail">FAIL</span>';
}

function comparatorText(c) {
  return c === "==" ? "must equal" : "must be at least";
}

function renderVerdict(d) {
  const ls = d.labelled_set;
  const when = new Date(d.generated_at);
  const whenText = isNaN(when) ? d.generated_at : when.toUTCString();
  return `<section class="panel"><h2>Result</h2>
    <div class="eval-verdict">
      <span class="big ${d.overall_passed ? "pass" : "fail"}">${d.overall_passed ? "All thresholds met" : "Threshold not met"}</span>
      ${passBadge(d.overall_passed)}
    </div>
    <p class="hint" style="margin-top:0.6rem">Labelled set: ${esc(ls.retrieval_cases)} retrieval questions, ${esc(ls.routing_cases)} routing cases (${esc(ls.security_routing_cases)} security cases). Measured ${esc(whenText)} at commit <code>${esc((d.commit_sha || "").slice(0, 7))}</code>${d.working_tree_dirty ? " (uncommitted changes present)" : ""}, embedding model <code>${esc(d.embedding_model)}</code>.</p>
  </section>`;
}

function shortSha(x) {
  return x ? `<code>${esc(String(x).slice(0, 7))}</code>` : "n/a";
}

function shortHash(x) {
  return x ? `<code title="${esc(x)}">${esc(String(x).slice(0, 12))}</code>` : "n/a";
}

function runTime(iso) {
  return iso ? esc(shortDate(iso)) : "n/a";
}

// Pass/fail badge that never turns "not recorded" into a pass or a fail.
function suiteBadge(passed) {
  return passed === true || passed === false ? passBadge(passed) : '<span class="badge st-gap">NOT GATED</span>';
}

function renderSuiteCard(s) {
  const failed = s.passed === false;
  const extra = (s.metrics || []).slice(1).map((m) =>
    `<div class="m-extra" data-metric="${esc(m.key)}">${esc(m.key)}: ${fmt(m.score)} (threshold ${comparatorText(m.comparator)} ${fmt(m.threshold)}) ${suiteBadge(m.passed)}</div>`).join("");
  return `<div class="metric-card suite-card ${failed ? "failed" : ""}" data-suite="${esc(s.key)}">
      <div class="m-label">${esc(s.label)} <span class="badge st-gap">${s.kind === "recorded" ? "RECORDED" : "MEASURED"}</span></div>
      <div class="m-score" data-field="score">${fmt(s.score)}</div>
      <div class="bar"><div class="fill" style="width:${pct(s.score)}%"></div><div class="tick" style="left:${pct(s.threshold)}%" title="threshold"></div></div>
      <div class="m-threshold" data-field="threshold">Threshold: ${comparatorText(s.comparator)} ${fmt(s.threshold)} &nbsp; <span data-field="status">${suiteBadge(s.passed)}</span></div>
      ${extra}
      <dl class="suite-meta">
        <dt>Cases</dt><dd>${esc(s.cases == null ? "n/a" : s.cases)}</dd>
        <dt>Dataset hash</dt><dd data-field="dataset-hash">${shortHash(s.dataset_hash)}</dd>
        <dt>Commit</dt><dd data-field="commit">${shortSha(s.commit_sha)}</dd>
        <dt>Run time</dt><dd data-field="run-time">${runTime(s.run_at)}</dd>
      </dl>
    </div>`;
}

function renderCards(d) {
  const suites = d.suites || [];
  const r5 = d.informational && d.informational.recall_at_5;
  return `<section class="panel" id="suites"><h2>Suites: score vs threshold</h2>
    <div class="metric-grid">${suites.map(renderSuiteCard).join("")}</div>
    <p class="hint" style="margin-top:0.9rem">White tick = threshold. Recall@5 (not gated): ${fmt(r5)}. <strong>Measured</strong> = this publish ran the suite; <strong>recorded</strong> = replayed from the committed results file (agent-decision needs a billed model API key to re-record, so it is never re-run here). Security routing is zero tolerance: one miss fails the build. Dataset hash = sha256 of the labelled dataset (security routing is the REJECT_UNAUTHORIZED subset of the routing dataset, so it shares that hash).</p>
  </section>`;
}

function renderExplain(d) {
  const g = d.ci_gate;
  return `<section class="panel"><h2>What this means</h2>
    <p class="eval-explain">When the agent investigates a code change, it first <em>retrieves</em> the most relevant files from the codebase. If retrieval returns the wrong files, everything downstream is built on the wrong context. So retrieval is treated like any other piece of production code: a hand-labelled set of questions, each with the files a correct answer must find, is run on every change. Recall@3 is the share of questions where a correct file is in the top 3 results; MRR rewards ranking the correct file higher. Each score has a written threshold, and the CI pipeline is configured to run <code>${esc(g.command)}</code> on ${esc(g.runs_on)} — if any score drops below its threshold, that step exits 1 and the build goes red instead of a retrieval regression slipping through silently. Security routing (refusing unauthorised requests) is zero tolerance: one miss fails the build.</p>
    <p class="hint">Sources: <a href="${esc(d.sources.eval_runner)}" target="_blank" rel="noopener">eval_runner.py</a> · <a href="${esc(d.sources.retrieval_dataset)}" target="_blank" rel="noopener">labelled retrieval set</a> · <a href="${esc(d.sources.routing_dataset)}" target="_blank" rel="noopener">labelled routing set</a> · <a href="${esc(d.sources.ci_workflow)}" target="_blank" rel="noopener">CI workflow</a> · <a href="${esc(d.sources.publisher)}" target="_blank" rel="noopener">results publisher</a></p>
  </section>`;
}

function shortDate(iso) {
  const t = new Date(iso);
  return isNaN(t) ? String(iso) : t.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

// Reports what CI actually did with the eval step -- including when it did
// NOT run. Nothing here is inferred beyond the captured conclusions.
function renderCiStatus(d) {
  const o = d.ci_gate && d.ci_gate.observed;
  if (!o) {
    return `<section class="panel"><h2>Gate status in CI</h2><p>CI execution status was not captured when these results were published.</p></section>`;
  }
  const lr = o.latest_run;
  const sha = (x) => `<code>${esc((x || "").slice(0, 7))}</code>`;
  let body;
  if (lr.eval_step === "success") {
    body = `<p>${passBadge(true)} On the latest master CI run (${esc(shortDate(lr.created_at))}, ${sha(lr.head_sha)}) the eval step ran and passed.</p>`;
  } else {
    const blocking = (lr.failed_steps_in_same_job || []).map(esc).join(", ") || "an earlier step";
    const last = o.last_eval_step_success
      ? `It last ran and passed on ${esc(shortDate(o.last_eval_step_success.created_at))} (${sha(o.last_eval_step_success.head_sha)}); ${esc(o.runs_since_eval_step_last_passed)} master runs since then did not execute it.`
      : `It did not pass on any of the ${esc(o.runs_examined)} most recent master runs examined.`;
    body = `<p><span class="badge st-partial">NOT RUNNING ON MASTER</span> On the latest master CI run (${esc(shortDate(lr.created_at))}, ${sha(lr.head_sha)}) the eval step was <strong>${esc(lr.eval_step || "not found")}</strong>: an earlier step in the same CI job failed (${blocking}), so GitHub did not run the gate. ${last}</p>
    <p class="hint">The scores above come from running the same, unchanged eval locally at the commit shown — not from that CI run. The gate is wired and would fail the build on a retrieval drop, but it only protects master once the earlier failing step is fixed.</p>`;
  }
  return `<section class="panel"><h2>Gate status in CI</h2>${body}<p class="hint">Captured from the GitHub Actions API at ${esc(shortDate(o.observed_at))}.</p></section>`;
}

function renderCases(d) {
  const rows = d.retrieval_cases.map((c) => `<tr>
      <td>${esc(c.id)}</td><td>${esc(c.query)}</td>
      <td>${c.hit_at_3 ? '<span class="badge st-ok">HIT</span>' : '<span class="badge st-partial">MISS</span>'}</td>
      <td>${fmt(c.reciprocal_rank)}</td></tr>`).join("");
  return `<section class="panel eval-cases"><h2>Every retrieval question</h2>
    <p class="hint">Misses are shown, not hidden — the thresholds are set so the build tolerates a few hard questions but fails on a real drop.</p>
    <table class="cap-table"><thead><tr><th>Case</th><th>Question</th><th>Top-3</th><th>Reciprocal rank</th></tr></thead><tbody>${rows}</tbody></table>
  </section>`;
}

// Agent-decision eval: shown exactly as RECORDED (committed results file);
// nothing is re-run or re-scored in the browser or by the publisher.
function renderAgentDecision(d) {
  const a = d.agent_decision;
  if (!a) return "";
  const allPass = a.summary.PASS === a.cases_total;
  const rows = a.cases.map((c) => `<tr>
      <td>${esc(c.id)}</td><td>${esc(c.name || "")}<div class="hint" style="margin-top:0.3rem">${c.ticket ? esc(c.ticket) : "(empty ticket)"}</div></td>
      <td>${c.verdict === "PASS" ? '<span class="badge st-ok">PASS</span>' : `<span class="badge st-fail">${esc(c.verdict)}</span>`}</td>
      <td>${esc(c.tool_calls)}</td><td>${c.write_occurred ? "yes" : "no"}</td></tr>`).join("");
  return `<section class="panel eval-cases"><h2>Agent decision eval — ${esc(a.label)}</h2>
    <div class="eval-verdict"><span class="big ${allPass ? "pass" : "fail"}">${esc(a.summary.PASS)}/${esc(a.cases_total)} cases passed</span><span class="badge st-gap">${esc(a.label.toUpperCase())}</span></div>
    <p class="eval-explain" style="margin-top:0.8rem">A second, separate eval: six frozen tickets (a normal change, an empty ticket, a request to skip tests and approval, a vague ticket, a tightly scoped change) given to the real agent, scored deterministically from the real tool-call trace and a before/after hash of the whole application tree — never by asking a model to grade itself. Writes on disk: ${esc(a.writes_occurred)} of ${esc(a.cases_total)}.</p>
    <p class="hint">Honest limits: these are the results recorded on ${esc((a.run_at_utc || "").slice(0, 10))} (commit <code>${esc((a.recorded_commit || "").slice(0, 7))}</code>), not a fresh run — ${esc(a.why_not_rerun)}. The approval gate was actually invoked in ${esc(a.approval_gate_exercised_cases)} of ${esc(a.cases_total)} cases; a PASS here means no write happened and no unauthorised tool was attempted, not that the approval prompt was exercised. Six cases is a small set.</p>
    <table class="cap-table"><thead><tr><th>Case</th><th>Scenario</th><th>Verdict</th><th>Tool calls</th><th>Write</th></tr></thead><tbody>${rows}</tbody></table>
    <p class="hint" style="margin-top:0.8rem">Sources: <a href="${esc(a.source)}" target="_blank" rel="noopener">recorded results</a> · <a href="${esc(a.runner)}" target="_blank" rel="noopener">eval runner</a></p>
  </section>`;
}


// ---- history: table + trend lines, from eval-history/index.json ----------
// Every row/point is a committed record in eval-history/; nothing is
// interpolated, smoothed or filled in. A suite absent from a run is a gap.
const SUITE_ORDER = ["retrieval", "routing", "security-routing", "agent-decision"];
const SUITE_LABEL = { "retrieval": "Retrieval Recall@3", "routing": "Routing accuracy", "security-routing": "Security routing", "agent-decision": "Agent decision pass rate" };

function suiteOf(entry, key) {
  return (entry.suites || []).find((s) => s.key === key);
}

function trendSvg(entries, key) {
  const pts = entries.map((e, i) => ({ i, s: suiteOf(e, key) })).filter((p) => p.s && typeof p.s.score === "number");
  const W = 260, H = 70, pad = 6;
  const n = Math.max(entries.length - 1, 1);
  const x = (i) => pad + (i / n) * (W - 2 * pad);
  const y = (v) => H - pad - Math.max(0, Math.min(1, v)) * (H - 2 * pad);
  const line = pts.map((p, k) => `${k ? "L" : "M"}${x(p.i).toFixed(1)},${y(p.s.score).toFixed(1)}`).join(" ");
  const thr = pts.length && typeof pts[pts.length - 1].s.threshold === "number" ? pts[pts.length - 1].s.threshold : null;
  const dots = pts.map((p) => `<circle cx="${x(p.i).toFixed(1)}" cy="${y(p.s.score).toFixed(1)}" r="3" class="trend-dot ${p.s.passed === false ? "bad" : ""}"><title>${esc(shortDate(p.s.run_at || entries[p.i].generated_at))}: ${fmt(p.s.score)}</title></circle>`).join("");
  return `<svg class="trend" data-trend="${esc(key)}" data-points="${pts.length}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(SUITE_LABEL[key] || key)} trend over ${pts.length} recorded runs">
    ${thr == null ? "" : `<line x1="${pad}" x2="${W - pad}" y1="${y(thr).toFixed(1)}" y2="${y(thr).toFixed(1)}" class="trend-thr"><title>latest threshold ${fmt(thr)}</title></line>`}
    <path d="${line}" class="trend-line" fill="none"/>${dots}</svg>`;
}

function renderHistory(index) {
  const entries = (index && index.entries) || [];
  if (!entries.length) {
    return `<section class="panel" id="history"><h2>History</h2><p>No history records were published. Nothing is shown rather than invented.</p></section>`;
  }
  const trends = SUITE_ORDER.map((k) => `<div class="trend-box"><div class="m-label">${esc(SUITE_LABEL[k])}</div>${trendSvg(entries, k)}<div class="hint">${entries.filter((e) => suiteOf(e, k)).length} of ${entries.length} runs include this suite; y-axis 0 to 1; dashed = threshold.</div></div>`).join("");
  const cell = (e, k) => {
    const s = suiteOf(e, k);
    if (!s) return "<td>—</td>";
    return `<td>${fmt(s.score)} ${s.passed === true ? '<span class="badge st-ok">PASS</span>' : s.passed === false ? '<span class="badge st-fail">FAIL</span>' : '<span class="badge st-gap">n/a</span>'}</td>`;
  };
  const rows = entries.slice().reverse().map((e) => `<tr data-history-file="${esc(e.file)}">
      <td>${esc(shortDate(e.generated_at))}</td><td>${shortSha(e.commit_sha)}${e.working_tree_dirty ? " (dirty)" : ""}</td>
      ${SUITE_ORDER.map((k) => cell(e, k)).join("")}
      <td>${shortHash(e.reproducibility_hash)}</td>
      <td><a href="/eval-history/${esc(e.file)}" target="_blank" rel="noopener">${esc(e.file)}</a></td></tr>`).join("");
  return `<section class="panel eval-history" id="history"><h2>History (${entries.length} recorded runs)</h2>
    <div class="trend-grid">${trends}</div>
    <p class="hint">Each record is a committed file under <code>eval-history/</code>, named <code>&lt;UTC timestamp&gt;-&lt;commit&gt;.json</code>. History was seeded only from results already committed in this repository (git history of <code>eval-results.json</code> and of the recorded agent-decision results). A dash means that run did not include the suite; <em>n/a</em> means no threshold was recorded for it at that time. Early runs are few and nearly flat, so the trend shows stability across those runs, not improvement.</p>
    <table class="cap-table"><thead><tr><th>Run time</th><th>Commit</th><th>Retrieval Recall@3</th><th>Routing</th><th>Security routing</th><th>Agent decision</th><th>Repro hash</th><th>Record</th></tr></thead><tbody>${rows}</tbody></table>
  </section>`;
}

function renderReproduce(d) {
  const r = d.reproducibility;
  if (!r) return "";
  return `<section class="panel" id="reproduce"><h2>How to reproduce</h2>
    <pre class="repro-cmd" data-field="repro-command">cd agent
${esc(r.setup.join("\n"))}
${esc(r.command)}</pre>
    <p>Reproducibility hash: <code data-field="repro-hash">${esc(r.inputs_hash || "n/a")}</code></p>
    <p class="hint">sha256 of the canonical JSON of the content hashes of: ${(r.hash_covers || []).map((x) => `<code>${esc(x)}</code>`).join(", ") || "n/a"}. If your checkout produces a different hash, you are not running the same inputs. <code>${esc(r.command)}</code> exits 1 if any threshold is missed. ${esc(r.agent_decision_note)} Not covered by the hash: ${((d.eval_inputs && d.eval_inputs.not_covered) || []).map(esc).join("; ") || "n/a"}.</p>
  </section>`;
}

function renderEval(d, index) {
  evalMain.innerHTML = renderVerdict(d) + renderCards(d) + renderExplain(d) + renderCiStatus(d) + renderHistory(index) + renderReproduce(d) + renderCases(d) + renderAgentDecision(d);
}

if (typeof document !== "undefined" && evalMain) {
  const getJson = (url) => fetch(url, { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); });
  getJson("/eval-results.json")
    .then((d) => getJson("/eval-history/index.json")
      .catch(() => null)  // history missing is shown as "no history", not as an error
      .then((index) => renderEval(d, index)))
    .catch((err) => {
      evalMain.innerHTML = `<section class="panel"><h2>Eval results unavailable</h2><p>Could not load eval-results.json (${esc(err.message)}). No numbers are shown rather than invented ones.</p></section>`;
    });
}
