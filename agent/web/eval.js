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

function renderCards(d) {
  const cards = d.metrics.map((m) => `
    <div class="metric-card ${m.passed ? "" : "failed"}" data-metric="${esc(m.key)}">
      <div class="m-label">${esc(m.label)}</div>
      <div class="m-score">${fmt(m.score)}</div>
      <div class="bar"><div class="fill" style="width:${pct(m.score)}%"></div><div class="tick" style="left:${pct(m.threshold)}%" title="threshold"></div></div>
      <div class="m-threshold">Threshold: ${comparatorText(m.comparator)} ${fmt(m.threshold)} &nbsp; ${passBadge(m.passed)}</div>
    </div>`).join("");
  const r5 = d.informational && d.informational.recall_at_5;
  return `<section class="panel"><h2>Score vs threshold</h2>
    <div class="metric-grid">${cards}</div>
    <p class="hint" style="margin-top:0.9rem">White tick = threshold. Recall@5 (not gated): ${fmt(r5)}.</p>
  </section>`;
}

function renderExplain(d) {
  const g = d.ci_gate;
  return `<section class="panel"><h2>What this means</h2>
    <p class="eval-explain">When the agent investigates a code change, it first <em>retrieves</em> the most relevant files from the codebase. If retrieval returns the wrong files, everything downstream is built on the wrong context. So retrieval is treated like any other piece of production code: a hand-labelled set of questions, each with the files a correct answer must find, is run on every change. Recall@3 is the share of questions where a correct file is in the top 3 results; MRR rewards ranking the correct file higher. Each score has a written threshold, and the CI pipeline is configured to run <code>${esc(g.command)}</code> on ${esc(g.runs_on)} — if any score drops below its threshold, that step exits 1 and the build fails, so a retrieval regression cannot be merged unnoticed. Security routing (refusing unauthorised requests) is zero tolerance: one miss fails the build.</p>
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

function renderEval(d) {
  evalMain.innerHTML = renderVerdict(d) + renderCards(d) + renderExplain(d) + renderCiStatus(d) + renderCases(d);
}

if (typeof document !== "undefined" && evalMain) {
  fetch("/eval-results.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(renderEval)
    .catch((err) => {
      evalMain.innerHTML = `<section class="panel"><h2>Eval results unavailable</h2><p>Could not load eval-results.json (${esc(err.message)}). No numbers are shown rather than invented ones.</p></section>`;
    });
}
