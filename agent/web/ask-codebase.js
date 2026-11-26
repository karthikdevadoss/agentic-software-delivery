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

// GitHub knowledge (2026-11-26): PRs/issues synced from GitHub with freshness.
// Titles and bodies are EXTERNAL content, so everything here is built with
// textContent (never innerHTML) and links are only followed to github.com.
function textEl(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}

function ago(iso) {
  const t = Date.parse(iso || "");
  if (Number.isNaN(t)) return "unknown";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 60) return `${mins} min ago`;
  const h = Math.round(mins / 60);
  return h < 48 ? `${h} h ago` : `${Math.round(h / 24)} days ago`;
}

function renderGithub(data) {
  const panel = document.getElementById("ac-github-panel");
  const box = document.getElementById("ac-github");
  const meta = document.getElementById("ac-github-meta");
  box.textContent = "";
  panel.hidden = false;
  const st = data.status || {};
  const src = st.source === "live" ? "live sync" : st.source === "snapshot" ? "committed snapshot (live sync pending)" : "not synced yet";
  meta.textContent = `Synced ${ago(st.synced_at)} from ${src} · ${st.documents || 0} items from ${st.repo || "GitHub"} · `
    + "only changed items are re-embedded, deleted items are removed · public data, retrieval only, no model call"
    + (st.last_error ? ` · last sync error: ${st.last_error}` : "");
  const hits = data.results || [];
  if (!hits.length) {
    box.appendChild(textEl("p", "hint", "No pull requests or issues indexed yet."));
    return;
  }
  hits.forEach((h) => {
    const card = textEl("div", "ac-evidence-card");
    const head = textEl("div", "ac-evidence-path");
    const url = String(h.url || "");
    const title = `${h.kind === "issue" ? "Issue" : "PR"} #${h.number}: ${h.title}`;
    if (url.startsWith("https://github.com/")) {
      const a = textEl("a", "ac-source-link", title);
      a.href = url; a.target = "_blank"; a.rel = "noopener";
      head.appendChild(a);
    } else {
      head.appendChild(textEl("span", "", title));
    }
    const state = String(h.state || "").toLowerCase();
    const pill = textEl("span", "ac-status-pill " + (state === "merged" ? "ac-status-strong" : "ac-status-weak"), state.toUpperCase());
    pill.style.marginLeft = "0.6rem";
    head.appendChild(pill);
    card.appendChild(head);
    card.appendChild(textEl("p", "hint", `score ${Number(h.score).toFixed(4)} · updated on GitHub ${ago(h.updated_at)} · indexed ${ago(h.indexed_at)}`));
    const body = String(h.excerpt || "").split("\n").slice(2).join(" ").trim();
    if (body) card.appendChild(textEl("p", "ac-github-excerpt", body.length > 280 ? body.slice(0, 280) + "…" : body));
    box.appendChild(card);
  });
}

async function fetchGithub(query, attempt = 0) {
  try {
    const resp = await fetch(`/api/ask-github?q=${encodeURIComponent(query)}`);
    if (!resp.ok) return;
    const data = await resp.json();
    renderGithub(data);
    // Just after a server start the index may still be loading: retry a few
    // times rather than leaving "No pull requests indexed yet" on screen.
    if (!(data.status || {}).documents && attempt < 10) {
      setTimeout(() => fetchGithub(query, attempt + 1), 3000);
    }
  } catch (e) {
    /* GitHub knowledge is additive; the codebase answer above stands on its own. */
  }
}

async function submitQuery(query) {
  fetchGithub(query);
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

  // Deep link (2026-11-26): /ask-codebase?q=... fills the box and runs the
  // search once on load, so a guided tour can link straight to an answer.
  // Same 300-character cap as typing; retrieval only, no model call.
  const deepLinked = new URLSearchParams(window.location.search).get("q");
  if (deepLinked && deepLinked.trim()) {
    textarea.value = deepLinked.trim().slice(0, 300);
    charcount.textContent = `${textarea.value.length} / 300`;
    submitQuery(textarea.value);
  }
}

main();
