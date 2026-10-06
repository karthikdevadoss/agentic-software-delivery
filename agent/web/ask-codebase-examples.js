// /ask-codebase/examples -- renders agent/web/ask-codebase-examples.json
// (agent/publish_ask_codebase_examples.py) exactly as recorded.

const aceMain = document.getElementById("ace-main");

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function statusBadge(s) {
  if (s === "STRONG_EVIDENCE") return '<span class="badge st-ok">STRONG EVIDENCE</span>';
  if (s === "WEAK_EVIDENCE") return '<span class="badge st-partial">WEAK EVIDENCE</span>';
  return `<span class="badge st-gap">${esc(s)}</span>`;
}

function lines(e) {
  if (!e.start_line) return "";
  return e.end_line && e.end_line !== e.start_line ? `:${e.start_line}-${e.end_line}` : `:${e.start_line}`;
}

function renderExample(x) {
  const ev = x.evidence.map((e) => `
    <div class="ace-ev">
      <div><span class="tag">#${esc(e.rank)}</span> <span class="tag real">score ${esc(Number(e.score).toFixed(3))}</span> <a href="${esc(e.source_url)}" target="_blank" rel="noopener"><code>${esc(e.source_path)}${esc(lines(e))}</code></a></div>
      <pre class="ace-excerpt">${esc(e.excerpt)}</pre>
    </div>`).join("");
  return `<section class="panel"><h2>${esc(x.query)}</h2>
    <p>${statusBadge(x.status)} <span class="hint">${esc(x.message)} Top ${esc(x.evidence.length)} of ${esc(x.evidence_returned)} shown.</span></p>
    ${ev}</section>`;
}

function renderSnapshot(d) {
  const summary = Object.entries(d.summary).map(([k, v]) => `${esc(v)} ${esc(k.replace("_", " ").toLowerCase())}`).join(", ");
  aceMain.innerHTML = `<section class="panel"><h2>About this snapshot</h2>
      <p>Recorded ${esc(d.generated_at)} at commit <code>${esc((d.commit_sha || "").slice(0, 7))}</code>${d.working_tree_dirty ? " (uncommitted changes present)" : ""} with embedding model <code>${esc(d.embedding_model)}</code>. LLM calls: ${esc(d.llm_calls)}. Result: ${summary}. A result counts as strong evidence when its top similarity score is at least ${esc(d.min_strong_score)} — the feature's own threshold; weaker matches are shown but labelled.</p>
      <p class="hint">Live answers can differ slightly as the indexed documents evolve; this page is a dated snapshot, not a live query. Sources: <a href="${esc(d.sources.feature)}" target="_blank" rel="noopener">feature</a> · <a href="${esc(d.sources.corpus)}" target="_blank" rel="noopener">curated corpus list</a> · <a href="${esc(d.sources.publisher)}" target="_blank" rel="noopener">snapshot publisher</a></p>
    </section>` + d.examples.map(renderExample).join("");
}

if (typeof document !== "undefined" && aceMain) {
  fetch("/ask-codebase-examples.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(renderSnapshot)
    .catch((err) => {
      aceMain.innerHTML = `<section class="panel"><h2>Snapshot unavailable</h2><p>Could not load ask-codebase-examples.json (${esc(err.message)}).</p></section>`;
    });
}
