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
}

main();
