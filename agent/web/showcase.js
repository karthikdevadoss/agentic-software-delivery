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

// Sprint 17 (BL-D). PROGRESSIVE DISCLOSURE, and not one piece of evidence
// removed -- the brief was explicit about that, and it is right: the density is
// this page's strongest asset and also the reason nobody finds the best parts.
//
// MEASURED: the BEFORE capture put the first control at y=964 desktop and y=1343
// at 390px, and the page ran to 12229px tall on a phone with every claim at
// identical visual priority. A recruiter scanning for thirty seconds sees the
// first three inches and gives equal weight to everything in them, which means
// the strongest four proofs compete with the weakest twenty.
//
// The fix is a ROLE-FIT SUMMARY as the first card: who this is for, a one-line
// proposition, the strongest four to six proofs as headline figures, and one
// obvious route deeper. Everything that was below stays below, in the same
// order, unchanged.
function renderRoleFit(main, showcase) {
  const panel = el("section", "panel sc-rolefit");
  panel.appendChild(el("h2", null, "Role fit"));

  if (showcase.target_role) {
    // Built from nodes rather than an interpolated innerHTML string: every other
    // renderer in this file passes trusted manifest text through el()'s
    // innerHTML, and this module has no escaper. A textContent child cannot
    // inject markup regardless of what the manifest holds.
    const role = el("p", "sc-rolefit-role");
    role.appendChild(el("strong", null, "Written for: "));
    const roleText = document.createElement("span");
    roleText.textContent = showcase.target_role;
    role.appendChild(roleText);
    panel.appendChild(role);
  }

  const demo = showcase.primary_demo || {};
  if (demo.name) {
    const prop = el("p", "sc-rolefit-prop");
    prop.textContent = demo.name;
    panel.appendChild(prop);
  }

  // The strongest proofs, as COUNTED figures rather than as a list of claims.
  // Every number here is a real length of a real array in the showcase manifest
  // -- there is no hand-maintained second copy that could drift, which is the
  // defect class AEQ-022 was.
  const caps = showcase.capabilities || [];
  const verified = caps.filter((c) => c.verification_status &&
    /verified|tested/i.test(c.verification_status));
  const figures = [
    [String(caps.length), "capabilities, each with its own evidence link"],
    [String(verified.length), "of those independently verified or tested"],
    [String((showcase.job_requirements_addressed || []).length), "job requirements mapped to real work"],
    [String((showcase.secondary_evidence || []).length), "additional evidence items"],
    [String((showcase.production_urls || []).length), "live production URLs you can open now"],
  ].filter(([n]) => n !== "0");

  // CTA BEFORE the figures, deliberately. With the grid first, the primary
  // action measured at y=812 -- past the brief's 700-800 band, and the 431px of
  // counted evidence sitting above it is context, not a reason to act. The
  // recruiter meets the proposition, then the way in, then the proof. Measured
  // after the move: y=642.
  const row = el("div", "sc-cta-row");
  if (demo.url) {
    const a = el("a", "button", "START THE LIVE DEMO");
    a.href = demo.url;
    a.target = "_blank";
    a.rel = "noopener";
    a.setAttribute("data-primary-action", "");
    row.appendChild(a);
  }
  const deeper = el("a", "sc-rolefit-deeper", "Read the full evidence below ↓");
  deeper.href = "#sc-requirement-map";
  row.appendChild(deeper);
  panel.appendChild(row);

  const grid = el("div", "sc-rolefit-grid");
  for (const [value, label] of figures) {
    const cell = el("div", "sc-rolefit-stat");
    const v = el("div", "sc-rolefit-value"); v.textContent = value;
    const l = el("div", "sc-rolefit-label"); l.textContent = label;
    cell.appendChild(v); cell.appendChild(l);
    grid.appendChild(cell);
  }
  if (figures.length) panel.appendChild(grid);

  main.appendChild(panel);
}

function renderPrimaryDemo(main, showcase) {
  // Sprint 17: the DUPLICATE "START THE LIVE DEMO" button is gone from here.
  //
  // Adding the role-fit card above put a second button with identical text on
  // the same page, which broke e2e/interview-walkthrough.spec.js's
  // getByText("START THE LIVE DEMO") on Playwright strict mode -- a real
  // regression, caught by an existing spec, and the right answer was not to
  // relax that spec to .first(). Two identically-labelled primary buttons a
  // screen apart is poor design and a screen reader announces them as the same
  // control twice.
  //
  // The role-fit card's CTA is now the page's single primary action. This panel
  // keeps its whole explanatory paragraph -- nothing was deleted -- and is
  // retitled to say what it actually is now that the button lives above it.
  const panel = el("section", "panel");
  panel.appendChild(el("h2", null, "What happens when you start it"));
  const demo = showcase.primary_demo || {};
  panel.appendChild(el("p", null, demo.what_to_expect || ""));
  main.appendChild(panel);
}

function renderRequirementMap(main, showcase) {
  const caps = showcase.capabilities || [];
  if (caps.length === 0) return;

  const panel = el("section", "panel");
  panel.id = "sc-requirement-map";   // the target of the role-fit card's "read the full evidence" link
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
    // Sprint 14: "VIEW LEARN" removed. /learn is no longer a public route
    // (Owner decision), so this button would have become a dead link.
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


// Sprint 15 (D9): dates are stored ISO and read aloud in English. "2026-09-29"
// is a field value; "29 Sep 2026" is what a visitor expects to see.
function humanDate(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
  if (!m) return String(iso || "");
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
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
  // Sprint 15 (D8): the h1 used to carry the role title AND the editorial
  // line in one heading, which wrapped mid-word at 1920 as "evidence-" /
  // "backed". The title is now just the title; the argument moved to the
  // sentence beneath it, where it reads as a sentence.
  document.getElementById("sc-title").textContent = showcase.title || "Showcase";
  document.getElementById("sc-target-role").textContent =
    "Every claim on this page links to a real run you can open — evidence, not a " +
    "list of technology badges." +
    (showcase.target_role ? ` Written for a ${showcase.target_role} role.` : "") +
    // D9: "Last verified 2026-09-29" is how the file stores it, not how a
    // person reads it.
    (showcase.last_verified ? ` Checked ${humanDate(showcase.last_verified)}.` : "");

  main_el.innerHTML = "";
  renderCaveat(main_el, showcase.unresolved_capability_ids, showcase.unresolved_requirement_texts);
  renderRoleFit(main_el, showcase);
  renderPrimaryDemo(main_el, showcase);
  renderInterviewWalkthrough(main_el, walkthrough);
  renderDeterministicVsLlm(main_el, walkthrough && walkthrough.deterministic_vs_llm);
  renderRequirementMap(main_el, showcase);
  renderTalkingPoints(main_el, showcase);
  renderEvidence(main_el, showcase);
  renderNav(main_el, showcase);
}

main();
