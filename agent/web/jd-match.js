// JD Match -- renders POST /api/jd-match results. Renders exactly what
// agent/jd_match.py returned: statuses, reasons and registry links. Nothing
// is invented client-side; if the API refused, the refusal is shown as-is.

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

const STATUS = {
  DEMONSTRATED: { label: "DEMONSTRATED", cls: "jd-status-demo" },
  PARTIAL: { label: "PARTIAL", cls: "jd-status-partial" },
  NOT_DEMONSTRATED: { label: "NOT YET DEMONSTRATED", cls: "jd-status-none" },
};

function levelLabel(level) {
  return String(level || "").replace(/_/g, " ").toLowerCase();
}

function renderRefusal(data) {
  const panel = document.getElementById("jd-result-panel");
  const summary = document.getElementById("jd-summary");
  const container = document.getElementById("jd-result");
  panel.hidden = false;
  summary.innerHTML = "";
  container.innerHTML = "";
  const row = el("div", "jd-refusal");
  row.appendChild(el("span", "jd-status-pill jd-status-none", String(data.status || "ERROR").replace(/_/g, " ")));
  row.appendChild(el("span", "jd-refusal-message", data.message || "The request could not be matched."));
  container.appendChild(row);
}

function renderMatched(data) {
  const panel = document.getElementById("jd-result-panel");
  const summary = document.getElementById("jd-summary");
  const container = document.getElementById("jd-result");
  panel.hidden = false;
  summary.innerHTML = "";
  container.innerHTML = "";

  const s = data.summary || {};
  summary.appendChild(el("span", "jd-summary-line",
    `${s.demonstrated} demonstrated · ${s.partial} partial · ${s.not_demonstrated} not yet demonstrated · ${s.total} requirements`));
  if (data.injection_detected) {
    summary.appendChild(el("span", "jd-flag", "The pasted text contained instructions aimed at this tool; they were recorded and not followed."));
  }
  if (data.redacted_reasons) {
    summary.appendChild(el("span", "jd-flag", `${data.redacted_reasons} reason(s) withheld because the model's wording made a claim the evidence does not support.`));
  }

  const table = el("table", "jd-table");
  const thead = el("thead");
  const hr = el("tr");
  ["Requirement", "Status", "Why", "Evidence"].forEach((h) => hr.appendChild(el("th", null, h)));
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = el("tbody");
  (data.requirements || []).forEach((r) => {
    const tr = el("tr", "jd-row-" + (r.status || "").toLowerCase());
    tr.appendChild(el("td", "jd-req", r.text));
    const st = STATUS[r.status] || { label: r.status, cls: "jd-status-none" };
    const tdStatus = el("td");
    tdStatus.appendChild(el("span", "jd-status-pill " + st.cls, st.label));
    tr.appendChild(tdStatus);
    const tdWhy = el("td", "jd-why", r.reason || "");
    (r.notes || []).forEach((n) => tdWhy.appendChild(el("div", "jd-note", n)));
    tr.appendChild(tdWhy);
    const tdEv = el("td", "jd-evidence");
    (r.capabilities || []).forEach((c) => {
      const card = el("div", "jd-cap");
      card.appendChild(el("div", "jd-cap-name", c.display_name));
      card.appendChild(el("div", "jd-cap-level", "verification: " + levelLabel(c.verification_level)));
      (c.evidence_links || []).forEach((u) => {
        // Visible text is the path, not the host: a source file reads as
        // "agent/standing_interview.py · source", a live surface as
        // "/standing-interview · live". The href is the full URL.
        let text = u;
        const gh = u.match(/github\.com\/[^/]+\/[^/]+\/(?:blob|tree)\/master\/(.+)$/);
        const live = u.match(/^https?:\/\/[^/]+(\/.*)?$/);
        if (gh) text = gh[1] + " · source";
        else if (live && /railway\.app/.test(u)) text = (live[1] || "/") + " · live";
        const a = el("a", "jd-cap-link", text.slice(0, 90));
        a.href = u; a.target = "_blank"; a.rel = "noopener";
        card.appendChild(a);
      });
      (c.evidence_note || []).forEach((n) => card.appendChild(el("div", "jd-cap-note", n)));
      tdEv.appendChild(card);
    });
    if (!(r.capabilities || []).length) tdEv.appendChild(el("span", "jd-none", "—"));
    tr.appendChild(tdEv);
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
  container.appendChild(el("p", "hint", data.note || ""));
}

async function submitJd(jd) {
  const btn = document.getElementById("jd-submit");
  btn.disabled = true;
  btn.textContent = "MATCHING… (two model calls, up to a minute)";
  try {
    const resp = await fetch("/api/jd-match", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jd }) });
    const data = await resp.json();
    if (data.status === "MATCHED") renderMatched(data); else renderRefusal(data);
  } catch (e) {
    renderRefusal({ status: "REQUEST_FAILED", message: "Request failed — the server may be unreachable." });
  } finally {
    btn.disabled = false;
    btn.textContent = "MATCH AGAINST EVIDENCE";
  }
}

function main() {
  const form = document.getElementById("jd-form");
  const textarea = document.getElementById("jd-text");
  const charcount = document.getElementById("jd-charcount");
  textarea.addEventListener("input", () => { charcount.textContent = `${textarea.value.length} / 8000`; });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const jd = textarea.value.trim();
    if (!jd) return;
    submitJd(jd);
  });
  document.getElementById("jd-sample").addEventListener("click", async () => {
    const resp = await fetch("/api/jd-match/sample");
    const data = await resp.json();
    textarea.value = data.jd || "";
    charcount.textContent = `${textarea.value.length} / 8000`;
  });
}

main();
