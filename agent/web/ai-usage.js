// AI Usage Intelligence page (2026-11-28). Renders /api/ai-usage/*.
// All data is written with textContent, never parsed as markup. Unknown values are
// shown as "unknown", never as 0.

const $ = (id) => document.getElementById(id);
const FILTERS = ["team_id", "user_id", "project_id", "model", "activity_category"];

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}
const unknown = "unknown";
const usd = (v, dp = 2) => (v === null || v === undefined ? unknown : `$${Number(v).toFixed(v !== 0 && Math.abs(v) < 0.01 ? 4 : dp)}`);
const num = (v) => (v === null || v === undefined ? unknown : Number(v).toLocaleString("en-GB"));
const pct = (v) => (v === null || v === undefined ? unknown : `${(v * 100).toFixed(1)}%`);
const ms = (v) => (v === null || v === undefined ? unknown : `${(v / 1000).toFixed(2)} s`);

function token() {
  try { return sessionStorage.getItem("au-owner-token") || ""; } catch (e) { return ""; }
}

function params(extra = {}) {
  const p = new URLSearchParams();
  p.set("dataset", $("f-dataset").value);
  p.set("range", $("f-range").value);
  if ($("f-range").value === "custom") {
    if ($("f-start").value) p.set("start", $("f-start").value);
    if ($("f-end").value) p.set("end", $("f-end").value);
  }
  FILTERS.forEach((f) => { const v = $(`f-${f}`).value; if (v) p.set(f, v); });
  Object.entries(extra).forEach(([k, v]) => p.set(k, v));
  return p.toString();
}

async function api(path, extra) {
  const headers = {};
  if ($("f-dataset").value === "live" && token()) headers["X-Owner-Token"] = token();
  const resp = await fetch(`/api/ai-usage/${path}?${params(extra)}`, { headers });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.error || `HTTP ${resp.status}`);
  return data;
}

// --- tooltip -----------------------------------------------------------------
const tip = $("au-tip");
function showTip(evt, text) {
  tip.textContent = text;
  tip.hidden = false;
  const x = Math.min(evt.clientX + 12, window.innerWidth - tip.offsetWidth - 8);
  tip.style.left = `${x}px`;
  tip.style.top = `${evt.clientY + 12}px`;
}
function hideTip() { tip.hidden = true; }

// --- bar chart (one series, one axis, hover tooltip) ----------------------------
function barChart(container, rows, key, fmt) {
  container.textContent = "";
  const vals = rows.map((r) => r[key]);
  const known = vals.filter((v) => v !== null && v !== undefined);
  if (!known.length) { container.appendChild(el("p", "hint", "No data in this period.")); return; }
  // viewBox = rendered size, so text and bars are never stretched.
  const W = Math.max(Math.round(container.clientWidth) || 600, 200), H = 150, padL = 4, padB = 18, gap = 2;
  const max = Math.max(...known, 0) || 1;
  const n = rows.length;
  const bw = Math.max((W - padL) / n - gap, 1);
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `${container.previousElementSibling ? container.previousElementSibling.textContent : "chart"}: ${n} days, maximum ${fmt(max)}`);
  const base = document.createElementNS(ns, "line");
  base.setAttribute("x1", 0); base.setAttribute("x2", W); base.setAttribute("y1", H - padB); base.setAttribute("y2", H - padB);
  base.setAttribute("class", "axis");
  svg.appendChild(base);
  rows.forEach((r, i) => {
    const v = r[key];
    const x = padL + i * (bw + gap);
    // generous invisible hit area, taller than the bar
    const hit = document.createElementNS(ns, "rect");
    hit.setAttribute("x", x); hit.setAttribute("y", 0); hit.setAttribute("width", bw + gap); hit.setAttribute("height", H - padB);
    hit.setAttribute("fill", "transparent");
    const label = `${r.day}: ${v === null || v === undefined ? unknown : fmt(v)}`;
    hit.addEventListener("mousemove", (e) => showTip(e, label));
    hit.addEventListener("mouseleave", hideTip);
    if (v !== null && v !== undefined && v > 0) {
      const h = ((H - padB - 4) * v) / max;
      const bar = document.createElementNS(ns, "rect");
      bar.setAttribute("x", x); bar.setAttribute("y", H - padB - h);
      bar.setAttribute("width", bw); bar.setAttribute("height", h);
      bar.setAttribute("rx", Math.min(2, bw / 2));
      bar.setAttribute("class", "bar");
      svg.appendChild(bar);
    }
    svg.appendChild(hit);
  });
  [[0, rows[0].day], [n - 1, rows[n - 1].day]].forEach(([i, d], k) => {
    const t = document.createElementNS(ns, "text");
    t.setAttribute("x", k ? W - 2 : padL); t.setAttribute("y", H - 4);
    t.setAttribute("text-anchor", k ? "end" : "start");
    t.setAttribute("class", "ax-label");
    t.textContent = d;
    svg.appendChild(t);
  });
  const top = document.createElementNS(ns, "text");
  top.setAttribute("x", W - 2); top.setAttribute("y", 10); top.setAttribute("text-anchor", "end");
  top.setAttribute("class", "ax-label");
  top.textContent = `max ${fmt(max)}`;
  svg.appendChild(top);
  container.appendChild(svg);
}

// --- tables ----------------------------------------------------------------------
function table(cols, rows, onRow) {
  const wrap = el("div", "au-scroll");
  const t = el("table", "au-table");
  const thead = el("thead");
  const hr = el("tr");
  cols.forEach((c) => hr.appendChild(el("th", c.num ? "num" : "", c.label)));
  thead.appendChild(hr);
  t.appendChild(thead);
  const tb = el("tbody");
  rows.forEach((r) => {
    const tr = el("tr", onRow ? "clickable" : "");
    cols.forEach((c) => {
      const td = el("td", c.num ? "num" : "");
      const v = c.render ? c.render(r) : r[c.key];
      if (v instanceof Node) td.appendChild(v); else td.textContent = v === null || v === undefined ? unknown : String(v);
      tr.appendChild(td);
    });
    if (onRow) {
      tr.tabIndex = 0;
      tr.addEventListener("click", () => onRow(r));
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter") onRow(r); });
    }
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  wrap.appendChild(t);
  return wrap;
}

function tile(label, value, note, chip) {
  const d = el("div", "au-tile");
  d.appendChild(el("div", "t-label", label));
  const v = el("div", "t-value", value);
  d.appendChild(v);
  if (note || chip) {
    const n = el("div", "t-note", note || "");
    if (chip) n.appendChild(el("span", "au-chip", chip));
    d.appendChild(n);
  }
  return d;
}

// --- sections ---------------------------------------------------------------------
function renderBanner(data) {
  const b = $("au-banner");
  b.className = "au-banner" + (data.dataset === "live" ? " live" : "");
  b.textContent = data.dataset === "demo"
    ? `DEMONSTRATION DATA. ${data.demo_label} Nothing here is a real customer, deployment or saving.`
    : "LIVE DATA from this platform's own ledger: its gateway calls (metered API) and the owner's Claude Code sessions (equivalent API value, not spend).";
}

function fillFilters(avail) {
  FILTERS.forEach((f) => {
    const sel = $(`f-${f}`);
    const cur = sel.value;
    sel.textContent = "";
    sel.appendChild(el("option", "", "All")).value = "";
    (avail[f] || []).forEach((v) => { const o = el("option", "", v); o.value = v; sel.appendChild(o); });
    sel.value = (avail[f] || []).includes(cur) ? cur : "";
  });
}

function renderOverview(data) {
  const o = data.overview, v = o.value;
  const t = $("au-tiles");
  t.textContent = "";
  const costChip = data.dataset === "demo" ? "demo" : "list-price estimate";
  t.appendChild(tile("Metered API spend", usd(o.spend_estimated), `estimate; ${o.spend_estimated_coverage}`, costChip));
  t.appendChild(tile("Subscription usage at API prices", usd(o.equivalent_api_value),
    `not money spent; ${o.equivalent_api_value_coverage}`, "equivalent value"));
  t.appendChild(tile("List-price cost, all usage", usd(o.cost_estimated), `basis for cost per outcome; ${o.cost_coverage}`));
  t.appendChild(tile("Provider-reported cost", usd(o.cost_reported), `${o.cost_reported_coverage} calls`, "billing data not connected"));
  t.appendChild(tile("Requests", num(o.requests), `${num(o.successful_requests)} successful`));
  t.appendChild(tile("Input tokens", num(o.input_tokens), `uncached; ${o.input_tokens_coverage} reported`));
  t.appendChild(tile("Output tokens", num(o.output_tokens), `${o.output_tokens_coverage} reported`));
  t.appendChild(tile("Cached input read", num(o.cache_read_tokens), `${o.cache_read_tokens_coverage} reported`));
  t.appendChild(tile("Sessions", num(o.sessions)));
  t.appendChild(tile("Tasks", num(o.tasks), `${num(v.completed)} completed`));
  t.appendChild(tile("Verified successful tasks", num(v.verified_successes), "objective or human evidence"));
  t.appendChild(tile("Cost per verified success", usd(o.cost_per_verified_success, 4), "all spend incl. failed attempts ÷ verified"));
  t.appendChild(tile("Cost per request", usd(o.avg_cost_per_request, 4)));
  t.appendChild(tile("Cost per task", usd(o.avg_cost_per_task, 4)));
  t.appendChild(tile("Average response time", ms(o.avg_latency_ms), `${o.latency_coverage} measured`));
  t.appendChild(tile("Error rate", pct(o.error_rate)));
  t.appendChild(tile("Retry rate", pct(o.retry_rate)));
  if (o.budget) {
    t.appendChild(tile("Monthly budget used", pct(o.budget.consumed_ratio),
      `${usd(o.budget.spent)} of ${usd(o.budget.limit)}; ${usd(o.budget.remaining)} left`, o.budget.enforced_by));
  }
  const b = $("au-billing");
  b.textContent = "";
  b.appendChild(el("h3", "", "By billing category"));
  b.appendChild(el("p", "hint", "Metered API spend and the list-price value of subscription usage are different things and are never added together as 'spend'."));
  b.appendChild(table([
    { label: "Category", render: (r) => r.key },
    { label: "Meaning", render: (r) => (data.billing_legend[r.key] || "") },
    { label: "Requests", key: "requests", num: true },
    { label: "Estimated cost", num: true, render: (r) => usd(r.cost_estimated) },
  ], data.by_billing_category));
}

let lastDaily = null;
let resizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => { if (lastDaily) renderCharts(lastDaily); }, 150);
});

function renderCharts(daily) {
  lastDaily = daily;
  barChart($("ch-cost"), daily, "cost_estimated", (v) => `$${v.toFixed(2)}`);
  barChart($("ch-verified"), daily, "verified_successes", (v) => `${v}`);
  barChart($("ch-requests"), daily, "requests", (v) => `${v}`);
  barChart($("ch-cpv"), daily, "cost_per_verified_success", (v) => `$${v.toFixed(4)}`);
}

function renderTrends(daily) {
  renderCharts(daily);
  const box = $("au-daily-table");
  box.textContent = "";
  box.appendChild(table([
    { label: "Day", key: "day" }, { label: "Requests", key: "requests", num: true },
    { label: "Est. cost", num: true, render: (r) => usd(r.cost_estimated) },
    { label: "Tokens", num: true, render: (r) => num(r.total_tokens) },
    { label: "Tasks completed", key: "tasks_completed", num: true },
    { label: "Verified", key: "verified_successes", num: true },
    { label: "Cost / verified", num: true, render: (r) => usd(r.cost_per_verified_success, 4) },
    { label: "Error rate", num: true, render: (r) => pct(r.error_rate) },
    { label: "Avg latency", num: true, render: (r) => ms(r.avg_latency_ms) },
    { label: "Models", render: (r) => r.models.join(", ") },
  ], daily));
}

function renderBreakdown(data) {
  const box = $("au-breakdown");
  box.textContent = "";
  const total = data.rows.reduce((s, r) => s + (r.cost_estimated || 0), 0) || 1;
  box.appendChild(table([
    { label: "Key", key: "key" },
    { label: "Share of cost", render: (r) => {
      const s = el("span");
      const bar = el("span", "au-share"); bar.style.width = `${Math.max(((r.cost_estimated || 0) / total) * 120, 1)}px`;
      s.appendChild(bar); s.appendChild(document.createTextNode(pct((r.cost_estimated || 0) / total)));
      return s; } },
    { label: "Est. cost", num: true, render: (r) => usd(r.cost_estimated) },
    { label: "Requests", key: "requests", num: true },
    { label: "Input tokens", num: true, render: (r) => num(r.input_tokens) },
    { label: "Output tokens", num: true, render: (r) => num(r.output_tokens) },
    { label: "Error rate", num: true, render: (r) => pct(r.error_rate) },
    { label: "Retry rate", num: true, render: (r) => pct(r.retry_rate) },
    { label: "Verified", key: "verified_successes", num: true },
    { label: "Cost / verified", num: true, render: (r) => usd(r.cost_per_verified_success, 4) },
  ], data.rows.slice(0, 50)));
}

function renderValue(o) {
  const v = o.value, box = $("au-value");
  box.textContent = "";
  const kv = el("div", "au-kv");
  const add = (k, val) => { const d = el("div"); d.appendChild(el("span", "", k)); d.appendChild(document.createTextNode(val)); kv.appendChild(d); };
  add("Task success rate", pct(v.task_success_rate));
  add("Verified success rate", pct(v.verified_success_rate));
  add("First-attempt success", `${pct(v.first_attempt_success_rate)} (${v.first_attempt_basis})`);
  add("Rework rate", pct(v.rework_rate));
  add("Cost of unsuccessful attempts", usd(v.cost_of_unsuccessful_attempts));
  add("Human review time", v.human_review_minutes === null ? unknown : `${v.human_review_minutes} min`);
  add("Time saved, measured", v.time_saved_minutes_measured === null ? unknown : `${v.time_saved_minutes_measured} min`);
  add("Time saved, estimated", v.time_saved_minutes_estimated === null ? unknown : `${v.time_saved_minutes_estimated} min (estimate)`);
  box.appendChild(kv);
  box.appendChild(el("h3", "", "How each outcome is known"));
  box.appendChild(table([{ label: "Evidence", key: "k" }, { label: "Tasks", key: "n", num: true }, { label: "Counts as verified?", key: "c" }],
    Object.entries(v.evidence_mix).map(([k, n]) => ({ k, n, c: (k === "objective" || k === "human") ? "yes" : "no" }))));
}

function renderRecs(data) {
  $("au-recs-note").textContent = data.note;
  const box = $("au-recs");
  box.textContent = "";
  if (!data.recommendations.length) { box.appendChild(el("p", "hint", "No recommendations: no rule found enough evidence in this view.")); return; }
  const list = el("div", "au-recs");
  data.recommendations.forEach((r) => {
    const c = el("article", "au-rec");
    const h = el("h3", "", r.title);
    h.appendChild(el("span", "au-chip", `confidence: ${r.confidence}`));
    if (r.requires_evaluation) h.appendChild(el("span", "au-chip", "evaluate before acting"));
    c.appendChild(h);
    const dl = el("dl");
    const row = (k, v) => { dl.appendChild(el("dt", "", k)); dl.appendChild(el("dd", "", v)); };
    row("Evidence", Object.entries(r.evidence).map(([k, v]) => `${k.replace(/_/g, " ")}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · "));
    row("Why it matters", r.why_it_matters);
    row("Suggested action", r.suggested_action);
    row("Potential benefit", r.potential_benefit.estimated_usd === null ? r.potential_benefit.basis : `${usd(r.potential_benefit.estimated_usd)} — ${r.potential_benefit.basis}`);
    row("Limitations", r.limitations);
    c.appendChild(dl);
    list.appendChild(c);
  });
  box.appendChild(list);
}

function renderModels(data) {
  const box = $("au-models");
  box.textContent = "";
  data.categories.forEach((cat) => {
    box.appendChild(el("h3", "", cat.activity_category));
    const s = cat.suggestion;
    box.appendChild(el("p", "au-suggest hint", s
      ? `Suggestion: ${s.model} — ${s.reason}. ${s.caveat} Routing is not changed automatically.`
      : "No suggestion: fewer than two models with enough tasks and verified outcomes to compare."));
    box.appendChild(table([
      { label: "Model", key: "model" }, { label: "Tasks", key: "tasks", num: true },
      { label: "Verified success", num: true, render: (r) => pct(r.verified_success_rate) },
      { label: "Cost / verified", num: true, render: (r) => usd(r.cost_per_verified_success, 4) },
      { label: "Est. cost", num: true, render: (r) => usd(r.cost_estimated) },
      { label: "Avg tokens", num: true, render: (r) => num(r.avg_tokens) },
      { label: "Avg latency", num: true, render: (r) => ms(r.avg_latency_ms) },
      { label: "Error rate", num: true, render: (r) => pct(r.error_rate) },
      { label: "Retry rate", num: true, render: (r) => pct(r.retry_rate) },
    ], cat.models));
  });
}

async function openSession(row) {
  const box = $("au-session-detail");
  box.hidden = false;
  box.textContent = "Loading session…";
  try {
    const data = await (async () => {
      const headers = {};
      if ($("f-dataset").value === "live" && token()) headers["X-Owner-Token"] = token();
      const r = await fetch(`/api/ai-usage/sessions/${encodeURIComponent(row.session_id)}?dataset=${$("f-dataset").value}`, { headers });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || r.status);
      return d.session;
    })();
    box.textContent = "";
    box.appendChild(el("h3", "", `Session ${data.session_id}`));
    const kv = el("div", "au-kv");
    const add = (k, val) => { const d = el("div"); d.appendChild(el("span", "", k)); d.appendChild(document.createTextNode(val)); kv.appendChild(d); };
    add("Purpose", data.purpose || unknown);
    add("Requests", num(data.totals.requests));
    add("Estimated cost", usd(data.totals.cost_estimated, 4));
    add("Input / output tokens", `${num(data.totals.input_tokens)} / ${num(data.totals.output_tokens)}`);
    add("Models", data.models.join(", ") || unknown);
    add("Duration", data.duration_seconds === null ? unknown : `${data.duration_seconds} s`);
    add("Retries", num(data.requests.filter((r) => r.is_retry).length));
    add("Errors", num(data.requests.filter((r) => r.success === false).length));
    box.appendChild(kv);
    box.appendChild(el("h4", "", "Requests that drove the cost"));
    box.appendChild(table([
      { label: "Model", key: "model" },
      { label: "Est. cost", num: true, render: (r) => usd(r.cost_estimated, 4) },
      { label: "Share", num: true, render: (r) => pct(r.cost_share) },
      { label: "Uncached input", num: true, render: (r) => num(r.input_tokens) },
      { label: "Cached input", num: true, render: (r) => num(r.cache_read_tokens) },
      { label: "Prompt make-up (estimated)", render: (r) => r.context_components
        ? Object.entries(r.context_components).filter(([k]) => k !== "source").map(([k, v]) => `${k} ${num(v)}`).join(" · ") + ` (${r.context_components.source})`
        : "not measured" },
    ], data.top_cost_requests));
    if (data.outcomes.length) {
      box.appendChild(el("h4", "", "Outcomes"));
      box.appendChild(table([{ label: "Task", key: "task_id" }, { label: "Status", key: "status" },
        { label: "Evidence", key: "evidence" }, { label: "Verified", render: (r) => (r.verified_success ? "yes" : "no") }], data.outcomes));
    }
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } catch (e) {
    box.textContent = `Could not load the session: ${e.message}`;
  }
}

function renderSessions(data) {
  const box = $("au-sessions");
  box.textContent = "";
  box.appendChild(el("p", "hint", `${num(data.total_sessions)} sessions in this view; showing the 25 most expensive.`));
  box.appendChild(table([
    { label: "Session", key: "session_id" }, { label: "Purpose", key: "purpose" }, { label: "Person", key: "user_id" },
    { label: "Requests", key: "requests", num: true },
    { label: "Est. cost", num: true, render: (r) => usd(r.cost_estimated, 4) },
    { label: "Models", render: (r) => r.models.join(", ") },
    { label: "Retries", key: "retries", num: true }, { label: "Errors", key: "errors", num: true },
  ], data.sessions.slice(0, 25), openSession));
}

function renderLearning(data) {
  const m = data.learning, box = $("au-learning");
  box.textContent = "";
  if (!m.sessions) { box.appendChild(el("p", "hint", "No learning records in this view.")); return; }
  const t = el("div", "au-tiles");
  t.appendChild(tile("Concepts verified", num(m.concepts_verified), `of ${num(m.concepts_introduced)} introduced`));
  t.appendChild(tile("Verified per hour", m.verified_per_hour === null ? unknown : m.verified_per_hour, `${m.learning_minutes} min of learning`));
  t.appendChild(tile("Cost per verified concept", usd(m.cost_per_verified_concept, 4), m.ai_cost_coverage));
  t.appendChild(tile("First-attempt accuracy", pct(m.first_attempt_accuracy)));
  t.appendChild(tile("Attempts per verified concept", m.attempts_per_verified_concept ?? unknown));
  t.appendChild(tile("Retention accuracy", pct(m.retention_accuracy), `${m.retention_tests} retention checks`));
  t.appendChild(tile("Explained but not yet verified", num(m.unverified_explanations), "never counted as learned"));
  box.appendChild(t);
  box.appendChild(table([{ label: "Section", key: "section" }, { label: "Introduced", key: "introduced", num: true },
    { label: "Verified", key: "verified", num: true }, { label: "Objective", key: "objective", num: true },
    { label: "Progress", num: true, render: (r) => pct(r.progress) }], m.by_section));
  box.appendChild(el("p", "hint", `Record sources: ${m.sources.join(", ")}.`));
}

function renderMethod(data) {
  const box = $("au-method");
  box.textContent = "";
  box.appendChild(el("h3", "", "Where each measurement comes from"));
  box.appendChild(table([{ label: "Label", key: "k" }, { label: "Meaning", key: "v" }],
    Object.entries(data.provenance_legend).map(([k, v]) => ({ k, v }))));
  box.appendChild(el("h3", "", "Billing categories"));
  box.appendChild(table([{ label: "Category", key: "k" }, { label: "Meaning", key: "v" }],
    Object.entries(data.billing_legend).map(([k, v]) => ({ k, v }))));
  [
    "Cost = tokens × the provider's published list price in force on the request's date (uncached input, cached input, cache writes and output priced separately; long-context tiers applied). It is an estimate of API expenditure, not an invoice and not the provider's own cost.",
    "Token meaning: input = uncached input; cached reads and cache writes are separate; output includes any reasoning tokens. OpenAI's reported input is converted (it includes cached tokens). Sources: docs/AI_USAGE_SOURCES.md in the repository.",
    "Personal ChatGPT or Claude subscription usage is not measurable by any application; it is never shown as if it were.",
    "Nested agent runs are counted once: only individual model calls carry tokens and cost; agent and workflow records group them.",
    "No prompt or response text is stored or shown for analytics; only metadata such as token counts, timings and outcomes.",
  ].forEach((t) => box.appendChild(el("p", "", t)));
}

// --- orchestration -------------------------------------------------------------------
// Each load gets a number; only the newest may draw. Without this a slow demo
// response could land after the user switched to Live and show demo numbers
// under a Live selection.
let loadSeq = 0;
const SECTIONS = ["au-tiles", "au-billing", "ch-cost", "ch-verified", "ch-requests", "ch-cpv", "au-daily-table",
  "au-breakdown", "au-value", "au-recs", "au-models", "au-sessions", "au-learning"];

async function load() {
  const mine = ++loadSeq;
  const status = $("au-status");
  status.textContent = "Loading…";
  try {
    const [ov, br, recs, models, sess, learn] = await Promise.all([
      api("overview"), api("breakdown", { by: $("f-by").value }), api("recommendations"),
      api("models"), api("sessions"), api("learning")]);
    if (mine !== loadSeq) return;
    renderBanner(ov);
    fillFilters(ov.filters_available);
    renderOverview(ov);
    renderTrends(ov.daily);
    renderBreakdown(br);
    renderValue(ov.overview);
    renderRecs(recs);
    renderModels(models);
    renderSessions(sess);
    renderLearning(learn);
    renderMethod(ov);
    const w = ov.window;
    status.textContent = `${ov.dataset === "demo" ? "Demo data" : "Live data"} · ${w.start || "all time"} to ${w.end || "today"}`;
  } catch (e) {
    if (mine !== loadSeq) return;
    // Never leave the previous dataset's numbers on screen under a failed selection.
    SECTIONS.forEach((id) => { $(id).textContent = ""; });
    $("au-session-detail").hidden = true;
    lastDaily = null;
    status.textContent = `Could not load: ${e.message}`;
    if ($("f-dataset").value === "live") $("au-banner").textContent = "Live data needs the owner token. The demo dataset is open to everyone.";
  }
}

function init() {
  $("f-range").addEventListener("change", () => {
    document.querySelectorAll(".au-custom").forEach((n) => { n.hidden = $("f-range").value !== "custom"; });
    if ($("f-range").value !== "custom") load();
  });
  ["f-start", "f-end", "f-by", ...FILTERS.map((f) => `f-${f}`)].forEach((id) => $(id).addEventListener("change", load));
  $("f-dataset").addEventListener("change", () => {
    $("au-owner").hidden = $("f-dataset").value !== "live";
    FILTERS.forEach((f) => { $(`f-${f}`).value = ""; });
    load();
  });
  $("f-token-apply").addEventListener("click", () => {
    try { sessionStorage.setItem("au-owner-token", $("f-token").value); } catch (e) { /* storage blocked: header not sent */ }
    $("f-token").value = "";
    load();
  });
  load();
}

init();
