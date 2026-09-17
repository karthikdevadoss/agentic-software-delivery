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

function renderCaveat(main, unresolvedIds, unresolvedReqs) {
  if (unresolvedIds && unresolvedIds.length) {
    main.appendChild(el(
      "div",
      "sc-caveat",
      "Note: this showcase references capability id(s) not currently found in " +
      "docs/PORTFOLIO_CAPABILITIES.yaml — shown honestly rather than silently " +
      "dropped: <strong>" + unresolvedIds.join(", ") + "</strong>"
    ));
  }
  if (unresolvedReqs && unresolvedReqs.length) {
    main.appendChild(el(
      "div",
      "sc-caveat",
      "Note: a capability's addresses_requirement text doesn't exactly match any " +
      "entry in job_requirements_addressed (likely drift/typo) — shown honestly " +
      "rather than silently mismatched: <strong>" + unresolvedReqs.join("; ") + "</strong>"
    ));
  }
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
  const caps = showcase.capabilities || [];
  if (caps.length === 0) return;

  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Their Requirement -> Our Live/Tested Evidence"));
  const grid = el("div", "sc-req-map");

  // AEQ-026: each capability names EXACTLY which requirement it addresses
  // (showcase_data.py's addresses_requirement, resolved server-side) --
  // never paired by array position. A capability with no matching named
  // requirement (addresses_requirement: null) is real additional evidence,
  // shown honestly as such rather than force-matched to the nearest
  // requirement just to fill a row.
  caps.forEach((cap) => {
    const row = el("div", "sc-req-row");
    const left = el("div");
    const hasRequirement = !!cap.addresses_requirement;
    left.appendChild(el("div", "sc-req-arrow", hasRequirement ? "REQUIREMENT" : "ADDITIONAL EVIDENCE"));
    left.appendChild(el("div", "sc-req-text", hasRequirement ? cap.addresses_requirement : "Not tied to a single named requirement above -- real, tested capability shown as additional strength."));
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

function evidenceLine(item) {
  if (item.url) {
    const a = el("a", null, item.label);
    a.href = item.url;
    a.target = "_blank";
    a.rel = "noopener";
    return a;
  }
  return el("span", null, `${item.label}: ${item.value || ""}`);
}

function renderHowToExplain(container, howTo) {
  if (!howTo) return;
  const order = ["why", "what", "how", "tradeoff", "failure", "verification"];
  const box = el("div", "sc-how-to-explain");
  box.appendChild(el("div", "sc-how-to-title", "How to explain this in an interview"));
  const dl = el("dl", "sc-how-to-grid");
  order.forEach((key) => {
    if (!howTo[key]) return;
    dl.appendChild(el("dt", null, key.toUpperCase()));
    dl.appendChild(el("dd", null, howTo[key]));
  });
  box.appendChild(dl);
  container.appendChild(box);
}

function renderFeaturedStory(story) {
  const details = el("details", "sc-story sc-story-featured");
  const summary = el("summary");
  summary.appendChild(el("span", "sc-story-title", story.title));
  if (story.live_demo && story.live_demo.url) {
    const badge = el("span", "sc-live-badge", "LIVE DEMO");
    summary.appendChild(badge);
  }
  details.appendChild(summary);

  const body = el("div", "sc-story-body");
  const fields = [
    ["Business problem", story.business_problem],
    ["Engineering requirement", story.engineering_requirement],
    ["Design decision", story.design_decision],
    ["Implementation", story.implementation],
    ["Java / Spring / DB / runtime details", story.runtime_details],
    ["Testing", story.testing],
    ["Failure mode", story.failure_mode],
    ["Verification", story.verification],
    ["At 10x scale", story.at_scale],
  ];
  fields.forEach(([label, value]) => {
    if (!value) return;
    const row = el("div", "sc-story-field");
    row.appendChild(el("div", "sc-story-field-label", label));
    row.appendChild(el("div", "sc-story-field-value", value));
    body.appendChild(row);
  });

  if (story.live_demo && story.live_demo.url) {
    const row = el("div", "sc-cta-row");
    const a = el("a", "button", story.live_demo.label || "See it live");
    a.href = story.live_demo.url;
    if (/^https?:\/\//.test(story.live_demo.url)) { a.target = "_blank"; a.rel = "noopener"; }
    row.appendChild(a);
    body.appendChild(row);
  }

  if (story.real_evidence && story.real_evidence.length) {
    const evBox = el("div", "sc-story-evidence");
    evBox.appendChild(el("div", "sc-story-field-label", "Real evidence"));
    const ul = el("ul", "sc-evidence-list");
    story.real_evidence.forEach((item) => {
      const li = el("li");
      li.appendChild(evidenceLine(item));
      ul.appendChild(li);
    });
    evBox.appendChild(ul);
    body.appendChild(evBox);
  }

  renderHowToExplain(body, story.how_to_explain);
  details.appendChild(body);
  return details;
}

function renderCompactStory(story) {
  const row = el("div", "sc-story-compact");
  const left = el("div");
  left.appendChild(el("div", "sc-story-compact-title", story.title));
  left.appendChild(el("div", "sc-story-compact-line", story.one_line || ""));
  row.appendChild(left);

  const right = el("div", "sc-story-compact-links");
  if (story.doc_path) {
    const a = el("a", null, "Full write-up");
    a.href = `https://github.com/karthikdevadoss/agentic-software-delivery/blob/master/${story.doc_path}`;
    a.target = "_blank";
    a.rel = "noopener";
    right.appendChild(a);
  }
  if (story.live_demo && story.live_demo.url) {
    const a = el("a", null, story.live_demo.label || "See it live");
    a.href = story.live_demo.url;
    if (/^https?:\/\//.test(story.live_demo.url)) { a.target = "_blank"; a.rel = "noopener"; }
    right.appendChild(a);
  }
  row.appendChild(right);
  return row;
}

function renderDeterministicVsLlm(main, det) {
  if (!det) return;
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, det.title || "Deterministic vs. LLM-Driven"));
  if (det.summary) panel.appendChild(el("p", null, det.summary));
  const ul = el("ul", "sc-det-list");
  (det.points || []).forEach((p) => {
    const li = el("li");
    li.appendChild(el("div", "sc-det-claim", p.claim));
    li.appendChild(el("div", "sc-det-mechanism", p.mechanism));
    if (p.evidence) {
      const ev = el("div", "sc-det-evidence", `Evidence: ${p.evidence}`);
      li.appendChild(ev);
    }
    ul.appendChild(li);
  });
  panel.appendChild(ul);
  main.appendChild(panel);
}

function renderInterviewWalkthrough(main, walkthrough) {
  if (!walkthrough || !walkthrough.paths || walkthrough.paths.length === 0) return;

  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Interview Walkthrough"));
  if (walkthrough.intro) panel.appendChild(el("p", null, walkthrough.intro));

  const tabRow = el("div", "sc-path-tabs");
  const pathSections = [];
  walkthrough.paths.forEach((path, i) => {
    const tab = el("button", "sc-path-tab" + (i === 0 ? " active" : ""), path.label);
    tab.type = "button";
    tab.addEventListener("click", () => {
      tabRow.querySelectorAll(".sc-path-tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      pathSections.forEach((s, j) => { s.style.display = j === i ? "" : "none"; });
    });
    tabRow.appendChild(tab);
  });
  panel.appendChild(tabRow);

  walkthrough.paths.forEach((path, i) => {
    const section = el("div", "sc-path-section");
    section.style.display = i === 0 ? "" : "none";
    section.appendChild(el("p", "sc-path-summary", path.summary || ""));

    const featured = (path.stories || []).filter((s) => s.featured);
    const compact = (path.stories || []).filter((s) => !s.featured);

    featured.forEach((story) => section.appendChild(renderFeaturedStory(story)));

    if (compact.length) {
      const compactBox = el("div", "sc-story-compact-list");
      compact.forEach((story) => compactBox.appendChild(renderCompactStory(story)));
      section.appendChild(compactBox);
    }

    if (path.start_link) {
      const row = el("div", "sc-cta-row");
      const a = el("a", "button secondary", "Start here: " + path.label);
      a.href = path.start_link;
      if (/^https?:\/\//.test(path.start_link)) { a.target = "_blank"; a.rel = "noopener"; }
      row.appendChild(a);
      section.appendChild(row);
    }

    pathSections.push(section);
    panel.appendChild(section);
  });

  main.appendChild(panel);
}

function renderNav(main, showcase) {
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "Explore The Platform Directly"));
  const row = el("div", "sc-cta-row");
  const links = [
    ["OPEN CUSTOMER APP", (showcase.production_urls || {}).customer_app],
    ["OPEN WORKBENCH", (showcase.primary_demo || {}).url],
    ["ASK THE CODEBASE", "/ask-codebase"],
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

  let walkthrough = null;
  try {
    const wResp = await fetch("/api/interview-walkthrough");
    if (wResp.ok) walkthrough = await wResp.json();
  } catch (e) {
    // Non-fatal: the showcase itself still renders without the walkthrough.
  }

  document.title = showcase.title + " — Showcase";
  document.getElementById("sc-title").innerHTML =
    (showcase.title || "Showcase") + ' <span class="sub">— evidence-backed, not a technology badge list</span>';
  document.getElementById("sc-target-role").textContent =
    "Target role: " + (showcase.target_role || "") +
    (showcase.last_verified ? `  ·  Last verified ${showcase.last_verified}` : "");

  main_el.innerHTML = "";
  renderCaveat(main_el, showcase.unresolved_capability_ids, showcase.unresolved_requirement_texts);
  renderPrimaryDemo(main_el, showcase);
  renderInterviewWalkthrough(main_el, walkthrough);
  renderDeterministicVsLlm(main_el, walkthrough && walkthrough.deterministic_vs_llm);
  renderRequirementMap(main_el, showcase);
  renderTalkingPoints(main_el, showcase);
  renderEvidence(main_el, showcase);
  renderNav(main_el, showcase);
}

main();
