// Home page live token strip (2026-10-21). Every number here is read at page
// load from /token-xray.json (published by agent/publish_token_xray.py from
// docs/evidence/token-xray-2026-10-21) and /api/trainer/catalogue (the real
// limits of a public Workbench click). Nothing is hard-coded, so the strip
// can never drift from the data.
(function () {
  const strip = document.getElementById("token-strip");
  const live = document.getElementById("token-live");
  if (!strip) return;
  const fmt = n => Number(n).toLocaleString("en-US");
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  fetch("/token-xray.json").then(r => (r.ok ? r.json() : Promise.reject(r.status))).then(d => {
    const max = Math.max(...d.tasks.map(t => t.wrong_tokens));
    strip.innerHTML = d.tasks.map(t => `
      <div class="tcell" title="${esc(t.label)}: ${fmt(t.wrong_tokens)} vs ${fmt(t.right_tokens)} tokens">
        <b>${esc(t.label)}</b>
        <div class="tbar" style="width:${(100 * t.wrong_tokens / max).toFixed(1)}%"></div>
        <div class="tbar ok" style="width:${Math.max(2, 100 * t.right_tokens / max).toFixed(1)}%"></div>
        <span><span class="x">${esc(t.token_multiple)}</span>${fmt(t.wrong_tokens)} vs ${fmt(t.right_tokens)} tokens</span>
      </div>`).join("");
    const base = `Wrong way (red) vs right way (green), tokens per task. Total ${fmt(d.totals.wrong_tokens)} vs ${fmt(d.totals.right_tokens)}, ${esc(d.statistic)}, ${esc(d.provider)}.`;
    live.innerHTML = `${base} <a href="/tokens">How it was measured →</a>`;
    return fetch("/api/trainer/catalogue").then(r => (r.ok ? r.json() : null)).then(c => {
      if (!c || !c.limits) return;
      live.innerHTML = `${base} <b>Live on this site:</b> a Workbench click makes ${Number(c.limits.model_calls_per_click)} model calls and costs $${Number(c.limits.usd_per_click).toFixed(2)}. <a href="/tokens">How it was measured →</a>`;
    });
  }).catch(() => { /* keep the static line already in the page */ });
})();
