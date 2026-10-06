// "Ask the Codebase" -- renders GET /api/ask-codebase?q=... results.
// Never fabricates a score/status the API didn't return; renders exactly
// what agent/ask_codebase.py's real response contains.

function el(tag, className, html) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

const STATUS_LABELS = {
  STRONG_EVIDENCE: { label: "STRONG EVIDENCE", cls: "ac-status-strong" },
  WEAK_EVIDENCE: { label: "WEAK EVIDENCE", cls: "ac-status-weak" },
  NO_EVIDENCE: { label: "NO EVIDENCE FOUND", cls: "ac-status-none" },
  INVALID_QUERY: { label: "INVALID QUESTION", cls: "ac-status-none" },
  INDEX_UNAVAILABLE: { label: "INDEX UNAVAILABLE", cls: "ac-status-none" },
};

function sourceTypeLabel(t) {
  return String(t || "").replace(/_/g, " ");
}

function renderResult(data) {
  const panel = document.getElementById("ac-result-panel");
  const container = document.getElementById("ac-result");
  container.innerHTML = "";
  panel.hidden = false;

  const statusInfo = STATUS_LABELS[data.status] || { label: data.status, cls: "ac-status-none" };
  const statusRow = el("div", "ac-status-row");
  statusRow.appendChild(el("span", "ac-status-pill " + statusInfo.cls, statusInfo.label));
  statusRow.appendChild(el("span", "ac-status-message", data.message || ""));
  container.appendChild(statusRow);

  if (!data.evidence || data.evidence.length === 0) return;

  const list = el("div", "ac-evidence-list");
  data.evidence.forEach((item) => {
    const card = el("div", "ac-evidence-card");

    const head = el("div", "ac-evidence-head");
    head.appendChild(el("span", "ac-evidence-rank", `#${item.rank}`));
    head.appendChild(el("span", "ac-evidence-score", `score ${item.score}`));
    head.appendChild(el("span", "ac-evidence-type", sourceTypeLabel(item.source_type)));
    card.appendChild(head);

    const pathLine = el("div", "ac-evidence-path");
    const link = el("a", null, item.source_path + (item.symbol ? `  ·  ${item.symbol}` : ""));
    link.href = item.source_url;
    link.target = "_blank";
    link.rel = "noopener";
    pathLine.appendChild(link);
    if (item.start_line) {
      pathLine.appendChild(el("span", "ac-evidence-lines", ` (lines ${item.start_line}${item.end_line && item.end_line !== item.start_line ? "-" + item.end_line : ""})`));
    }
    card.appendChild(pathLine);

    const pre = document.createElement("pre");
    pre.className = "ac-evidence-excerpt";
    pre.textContent = item.excerpt.length > 900 ? item.excerpt.slice(0, 900) + "\n…" : item.excerpt;
    card.appendChild(pre);

    list.appendChild(card);
  });
  container.appendChild(list);
}

async function submitQuery(query) {
  const submitBtn = document.getElementById("ac-submit");
  submitBtn.disabled = true;
  submitBtn.textContent = "SEARCHING…";
  try {
    const resp = await fetch(`/api/ask-codebase?q=${encodeURIComponent(query)}`);
    const data = await resp.json();
    renderResult(data);
  } catch (e) {
    renderResult({ status: "INDEX_UNAVAILABLE", message: "Request failed — the server may be unreachable.", evidence: [] });
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "SEARCH THE CODEBASE";
  }
}

// BL-105 (Sprint 27): shows this page's own retrieval quality in plain
// English, read directly from the same published eval-results.json the
// /eval page uses -- never a separate or re-derived number.
function renderQuality(d) {
  const box = document.getElementById("ac-quality");
  const byKey = {};
  (d.metrics || []).forEach((m) => { byKey[m.key] = m; });
  const recall3 = byKey.recall_at_3;
  const mrr = byKey.mrr;
  const recall5 = d.informational && d.informational.recall_at_5;

  if (!recall3 || !mrr) {
    box.innerHTML = `<p class="hint">Retrieval quality numbers are not available right now.</p>`;
    return;
  }

  const when = new Date(d.generated_at);
  const whenText = isNaN(when) ? d.generated_at : when.toUTCString();
  const pct = (n) => `${Math.round(n * 100)}%`;

  box.innerHTML = `
    <p>Measured against a hand-labelled set of ${(d.labelled_set || {}).retrieval_cases || "?"} real
    questions with a known correct answer, so this is a real score, not a self-report:</p>
    <ul class="ac-quality-list">
      <li><strong>${pct(recall3.score)} of the time</strong>, the file that actually answers the
      question appears somewhere in the top 3 results shown.</li>
      <li>When it does appear, it is usually <strong>close to the top</strong>, not buried at
      position 3 — that is what "mean reciprocal rank" (${mrr.score.toFixed(2)} out of 1.0) means
      in plain terms: 1.0 would mean always ranked first.</li>
      ${typeof recall5 === "number" ? `<li>Widening the window to the top 5 results instead of 3 catches the right file <strong>${pct(recall5)} of the time</strong> (tracked, not yet a required gate).</li>` : ""}
    </ul>
    <p class="hint">Measured ${esc(whenText)} at commit <code>${esc((d.commit_sha || "").slice(0, 7))}</code>.
    Full breakdown, every question, and what happens when a score drops: <a href="/eval">the retrieval eval page →</a></p>
  `;
}

function loadQuality() {
  fetch("/eval-results.json", { cache: "no-cache" })
    .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(renderQuality)
    .catch((err) => {
      document.getElementById("ac-quality").innerHTML =
        `<p class="hint">Could not load the latest measured retrieval quality (${esc(err.message)}). No number is shown rather than an invented one.</p>`;
    });
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function main() {
  const form = document.getElementById("ac-form");
  const textarea = document.getElementById("ac-query");
  const charcount = document.getElementById("ac-charcount");

  textarea.addEventListener("input", () => {
    charcount.textContent = `${textarea.value.length} / 300`;
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const query = textarea.value.trim();
    if (!query) return;
    submitQuery(query);
  });

  document.querySelectorAll(".ac-example-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      textarea.value = btn.textContent;
      charcount.textContent = `${textarea.value.length} / 300`;
      submitQuery(textarea.value);
    });
  });

  loadQuality();
}

main();
