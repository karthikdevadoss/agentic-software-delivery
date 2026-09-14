// Reusable showcase renderer — ONE template for every showcases/<slug>/
// showcase.yaml manifest, reached at /showcase/<slug>. Renders only data
// returned by GET /api/showcase/<slug>; never fabricates a capability or
// evidence link that isn't in the manifest/registry.

function slugFromPath() {
  const m = window.location.pathname.match(/^\/showcase\/([^/]+)/);
  return m ? m[1] : null;
}

function statusClass(status) {
  return "sc-status-" + String(status || "").toLowerCase();
}

function el(tag, className, html) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

function renderCaveat(main, unresolvedIds) {
  if (!unresolvedIds || unresolvedIds.length === 0) return;
  const div = el(
    "div",
    "sc-caveat",
    "Note: this showcase references capability id(s) not currently found in " +
    "docs/PORTFOLIO_CAPABILITIES.yaml — shown honestly rather than silently " +
    "dropped: <strong>" + unresolvedIds.join(", ") + "</strong>"
  );
  main.appendChild(div);
}

function renderPrimaryDemo(main, showcase) {
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Start Here"));
  const demo = showcase.primary_demo || {};
  panel.appendChild(el("p", null, demo.what_to_expect || ""));
  const row = el("div", "sc-cta-row");
  if (demo.url) {
    const a = el("a", "button", "START THE LIVE DEMO");
    a.href = demo.url;
    a.target = "_blank";
    a.rel = "noopener";
    row.appendChild(a);
  }
  panel.appendChild(row);
  main.appendChild(panel);
}

function renderRequirementMap(main, showcase) {
  const reqs = showcase.job_requirements_addressed || [];
  const caps = showcase.capabilities || [];
  if (reqs.length === 0 || caps.length === 0) return;

  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Their Requirement -> Our Live/Tested Evidence"));
  const grid = el("div", "sc-req-map");

  // Pair requirements with capabilities positionally where counts allow a
  // clean 1:1 story; otherwise fall back to listing each capability against
  // its own engineering_problem_solved, which is honest either way.
  caps.forEach((cap, i) => {
    const row = el("div", "sc-req-row");
    const left = el("div");
    left.appendChild(el("div", "sc-req-arrow", "REQUIREMENT"));
    left.appendChild(el("div", "sc-req-text", reqs[i] || reqs[reqs.length - 1] || ""));
    const right = el("div");
    right.appendChild(el("div", "sc-req-arrow", "EVIDENCE"));
    const capName = el("span", "sc-cap-name", cap.display_name);
    const pill = el("span", "sc-status-pill " + statusClass(cap.production_state), (cap.production_state || "").replace(/_/g, " "));
    const nameLine = el("div");
    nameLine.appendChild(capName);
    nameLine.appendChild(pill);
    right.appendChild(nameLine);
    right.appendChild(el("div", "sc-cap-meta", cap.engineering_problem_solved || ""));
    row.appendChild(left);
    row.appendChild(right);
    grid.appendChild(row);
  });

  panel.appendChild(grid);
  main.appendChild(panel);
}

function renderTalkingPoints(main, showcase) {
  const points = showcase.recommended_talking_points || [];
  if (points.length === 0) return;
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Recommended Talking Points"));
  const ul = el("ul", "sc-talking-points");
  points.forEach((p) => ul.appendChild(el("li", null, p)));
  panel.appendChild(ul);
  main.appendChild(panel);
}

function renderEvidence(main, showcase) {
  const items = showcase.secondary_evidence || [];
  if (items.length === 0) return;
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Further Evidence"));
  const ul = el("ul", "sc-evidence-list");
  items.forEach((item) => {
    const li = el("li");
    const a = el("a", null, item.name);
    a.href = item.url;
    if (/^https?:\/\//.test(item.url)) {
      a.target = "_blank";
      a.rel = "noopener";
    }
    li.appendChild(a);
    ul.appendChild(li);
  });
  panel.appendChild(ul);
  main.appendChild(panel);
}

function renderNav(main, showcase) {
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Explore The Platform Directly"));
  const row = el("div", "sc-cta-row");
  const links = [
    ["OPEN CUSTOMER APP", (showcase.production_urls || {}).customer_app],
    ["OPEN WORKBENCH", (showcase.primary_demo || {}).url],
    ["VIEW DASHBOARD", "/dashboard"],
    ["VIEW USAGE", "/usage"],
    ["VIEW LEARN", "/learn"],
  ];
  links.forEach(([label, url]) => {
    if (!url) return;
    const a = el("a", "button secondary", label);
    a.href = url;
    if (/^https?:\/\//.test(url)) { a.target = "_blank"; a.rel = "noopener"; }
    row.appendChild(a);
  });
  panel.appendChild(row);
  main.appendChild(panel);
}

async function main() {
  const slug = slugFromPath();
  const main_el = document.getElementById("sc-main");
  if (!slug) {
    main_el.innerHTML = '<p class="hint">No showcase slug in the URL.</p>';
    return;
  }
  let showcase;
  try {
    const resp = await fetch(`/api/showcase/${encodeURIComponent(slug)}`);
    if (!resp.ok) {
      main_el.innerHTML = `<p class="hint">Showcase "${slug}" not found (HTTP ${resp.status}).</p>`;
      return;
    }
    showcase = await resp.json();
  } catch (e) {
    main_el.innerHTML = '<p class="hint">Failed to load showcase data.</p>';
    return;
  }

  document.title = showcase.title + " — Showcase";
  document.getElementById("sc-title").innerHTML =
    (showcase.title || "Showcase") + ' <span class="sub">— evidence-backed, not a technology badge list</span>';
  document.getElementById("sc-target-role").textContent =
    "Target role: " + (showcase.target_role || "") +
    (showcase.last_verified ? `  ·  Last verified ${showcase.last_verified}` : "");

  main_el.innerHTML = "";
  renderCaveat(main_el, showcase.unresolved_capability_ids);
  renderPrimaryDemo(main_el, showcase);
  renderRequirementMap(main_el, showcase);
  renderTalkingPoints(main_el, showcase);
  renderEvidence(main_el, showcase);
  renderNav(main_el, showcase);
}

main();
