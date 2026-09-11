// Agentic Software Delivery — Learn: recursive technical Wikipedia router.
//
// ONE canonical knowledge source (agent/web/learn-tree.json, built by
// agent/build_learn_tree.py and served statically) drives both this
// interactive UI and the downloadable PDF book (agent/learn_pdf.py) —
// nothing here hand-authors content that could drift from the tree.
//
// Client-side router: reads window.location.pathname, walks the tree by
// slug segments, and renders either the landing page (no segments) or a
// dedicated topic page (breadcrumb + children + detailed sections).
// Internal links use history.pushState so Back/Forward work naturally;
// a fresh page load / bookmark / shared link still works because the
// SERVER (agent/web_server.py::learn_page) validates the same path
// against the same tree and returns a real HTTP 404 for an unknown one.

const APP_ROOT = document.getElementById("learn-app");
let TREE = null;

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

function currentSegments() {
  const path = window.location.pathname.replace(/^\/learn\/?/, "");
  return path ? path.split("/").filter(Boolean) : [];
}

function pathFor(segments) {
  return "/learn" + (segments.length ? "/" + segments.join("/") : "");
}

function resolvePath(segments) {
  let nodes = TREE.domains;
  let node = null;
  const breadcrumb = [{ title: "Learn", segments: [] }];
  for (const seg of segments) {
    node = (nodes || []).find(n => n.slug === seg);
    if (!node) return { node: null, breadcrumb: null };
    breadcrumb.push({ title: node.title, segments: breadcrumb[breadcrumb.length - 1].segments.concat(seg) });
    nodes = node.children;
  }
  return { node, breadcrumb };
}

function findBySlugAnywhere(slug, nodes) {
  nodes = nodes || TREE.domains;
  for (const n of nodes) {
    if (n.slug === slug) return n;
    if (n.children && n.children.length) {
      const found = findBySlugAnywhere(slug, n.children);
      if (found) return found;
    }
  }
  return null;
}

function pathToSlugAnywhere(slug) {
  // Depth-first search returning the full segment path to a slug found
  // anywhere in the tree, for rendering a "related topic" link even
  // when we only know its slug, not its full path.
  function walk(nodes, trail) {
    for (const n of nodes) {
      const next = trail.concat(n.slug);
      if (n.slug === slug) return next;
      if (n.children && n.children.length) {
        const found = walk(n.children, next);
        if (found) return found;
      }
    }
    return null;
  }
  return walk(TREE.domains, []);
}

function classificationLabel(c) {
  if (!c) return "";
  return c.replace(/_/g, " ").replace(/\w\S*/g, t => t[0].toUpperCase() + t.slice(1).toLowerCase());
}

const CLASS_BADGE_CLASS = {
  CURRENT_PROJECT_EXPERIENCE: "ev-runtime-verified",
  REAL_PROFESSIONAL_EXPERIENCE: "ev-production-verified",
  LEARNED_UNDERSTOOD: "ev-learned",
  PLANNED_NOT_EXPERIENCED: "ev-not-used",
};

function renderBreadcrumb(breadcrumb) {
  return `<nav class="breadcrumb">${breadcrumb.map((b, i) => {
    const isLast = i === breadcrumb.length - 1;
    const href = pathFor(b.segments);
    return isLast
      ? `<span class="crumb current">${esc(b.title)}</span>`
      : `<a class="crumb" data-link href="${href}">${esc(b.title)}</a><span class="crumb-sep">/</span>`;
  }).join("")}</nav>`;
}

function renderChildGrid(children, parentSegments) {
  if (!children || !children.length) return "";
  return `<section class="learn-block">
    <h3>Child Topics <span class="hint">(${children.length})</span></h3>
    <div class="topic-grid">
      ${children.map(c => {
        const href = pathFor(parentSegments.concat(c.slug));
        const badge = c.experience_classification
          ? `<span class="ev-badge ${CLASS_BADGE_CLASS[c.experience_classification] || ""}">${esc(classificationLabel(c.experience_classification))}</span>` : "";
        const count = c.children && c.children.length ? `<span class="hint"> (${c.children.length})</span>` : "";
        return `<a class="topic-card topic-card-link" data-link href="${href}">
          <div class="topic-head"><span class="topic-name">${esc(c.title)}${count}</span>${badge}</div>
          <div class="topic-def">${esc(c.short_overview || "")}</div>
        </a>`;
      }).join("")}
    </div>
  </section>`;
}

const SECTION_LABELS = [
  ["what", "WHAT"], ["why", "WHY"], ["how", "HOW"], ["when", "WHEN"],
  ["system_design", "SYSTEM DESIGN"], ["real_experience", "REAL EXPERIENCE / OUR EXPERIENCE"],
  ["development_steps", "DEVELOPMENT STEPS"], ["decisions", "DECISIONS"],
  ["alternatives", "ALTERNATIVES / TRADEOFFS"], ["testing", "TESTING"],
  ["failure_modes", "FAILURE MODES / LESSONS"], ["real_incidents", "REAL INCIDENTS"],
  ["ai_role", "AI ROLE"], ["human_role", "HUMAN ROLE"],
  ["best_practices", "BEST PRACTICES"], ["evidence", "EVIDENCE"],
];

function renderSectionValue(value) {
  if (Array.isArray(value)) {
    return `<ul>${value.map(v => `<li>${esc(v)}</li>`).join("")}</ul>`;
  }
  if (value && typeof value === "object") {
    return Object.entries(value).filter(([, v]) => v).map(([k, v]) =>
      `<div class="deep-block"><strong>${esc(k.replace(/_/g, " ").replace(/\w\S*/g, t => t[0].toUpperCase() + t.slice(1)))}:</strong> ${esc(v)}</div>`
    ).join("");
  }
  return `<p>${esc(value)}</p>`;
}

function renderSections(sections) {
  if (!sections) return "";
  const blocks = SECTION_LABELS
    .filter(([key]) => sections[key] && (!Array.isArray(sections[key]) || sections[key].length))
    .map(([key, label]) => `<div class="learn-section-block">
      <h4>${label}</h4>
      ${renderSectionValue(sections[key])}
    </div>`);
  if (sections.interview) {
    blocks.push(`<div class="learn-section-block deep-interview">
      <h4>INTERVIEW PREPARATION</h4>
      ${renderSectionValue(sections.interview)}
    </div>`);
  }
  return blocks.join("");
}

function renderRelated(related) {
  if (!related || !related.length) return "";
  const links = related.map(slug => {
    const path = pathToSlugAnywhere(slug);
    const node = path ? findBySlugAnywhere(slug) : null;
    if (!path || !node) return `<span class="related-chip related-chip-unresolved">${esc(slug)}</span>`;
    return `<a class="related-chip" data-link href="${pathFor(path)}">${esc(node.title)}</a>`;
  }).join(" ");
  return `<section class="learn-block"><h3>Related Topics</h3><div class="related-chips">${links}</div></section>`;
}

function renderTopicPage(node, breadcrumb) {
  const badge = node.experience_classification
    ? `<span class="ev-badge ${CLASS_BADGE_CLASS[node.experience_classification] || ""}">${esc(classificationLabel(node.experience_classification))}</span>` : "";
  const status = node.status ? `<span class="ev-badge">${esc(node.status)}</span>` : "";
  return `
    ${renderBreadcrumb(breadcrumb)}
    <h2 class="topic-title">${esc(node.title)} ${badge} ${status}</h2>
    ${node.short_overview ? `<p class="topic-overview">${esc(node.short_overview)}</p>` : ""}
    ${renderChildGrid(node.children, breadcrumb[breadcrumb.length - 1].segments)}
    ${renderRelated(node.related)}
    <section class="learn-block">${renderSections(node.sections)}</section>
  `;
}

function flattenSearchIndex() {
  const index = [];
  function walk(nodes, trail, titles) {
    for (const n of nodes) {
      const segs = trail.concat(n.slug);
      const path = titles.concat(n.title);
      index.push({ title: n.title, overview: n.short_overview || "", segments: segs, breadcrumbTitles: path });
      if (n.children && n.children.length) walk(n.children, segs, path);
    }
  }
  walk(TREE.domains, [], []);
  return index;
}

let SEARCH_INDEX = null;

function renderLanding() {
  const m = TREE.metrics || {};
  SEARCH_INDEX = SEARCH_INDEX || flattenSearchIndex();
  const domainCards = TREE.domains.map(d => {
    const count = (d.children || []).length;
    return `<a class="topic-card topic-card-link domain-card" data-link href="${pathFor([d.slug])}">
      <div class="topic-head"><span class="topic-name">${esc(d.title)}</span><span class="hint">${count} topic(s)</span></div>
      <div class="topic-def">${esc(d.short_overview || "")}</div>
    </a>`;
  }).join("");

  return `
    <section class="panel">
      <input id="learn-search" type="text" placeholder="Search topics (e.g. RAG, connection pooling, approval)…" />
      <p class="hint" id="learn-count">
        ${m.total_domains || TREE.domains.length} domains · ${m.total_reference_topics || 0} reference topics ·
        ${m.total_deep_topics || 0} deep evidence-backed topics
      </p>
      <p class="hint">
        Experience: ${m.current_project_experience_topics || 0} current-project ·
        ${m.real_professional_experience_topics || 0} professional ·
        ${m.learned_understood_topics || 0} learned/understood ·
        ${m.planned_not_experienced_topics || 0} planned
      </p>
      <a id="learn-pdf-download" class="pdf-download-btn" href="/api/learn/book.pdf" download>
        ⬇ DOWNLOAD COMPLETE BOOK (PDF)
      </a>
      <p class="hint" id="learn-pdf-meta">Generated from this exact knowledge tree — commit ${esc(TREE.git_commit || "unknown")}.</p>
    </section>
    <div id="learn-search-results"></div>
    <div id="learn-domain-grid" class="topic-grid domain-grid">${domainCards}</div>
  `;
}

function wireSearch() {
  const input = document.getElementById("learn-search");
  const resultsRoot = document.getElementById("learn-search-results");
  const gridRoot = document.getElementById("learn-domain-grid");
  if (!input) return;
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    if (!q) {
      resultsRoot.innerHTML = "";
      gridRoot.style.display = "";
      return;
    }
    gridRoot.style.display = "none";
    const matches = SEARCH_INDEX.filter(e =>
      e.title.toLowerCase().includes(q) || e.overview.toLowerCase().includes(q)
    ).slice(0, 60);
    resultsRoot.innerHTML = `<p class="hint">${matches.length} match(es)</p>` + matches.map(m => `
      <a class="search-result" data-link href="${pathFor(m.segments)}">
        <div class="search-result-title">${esc(m.title)}</div>
        <div class="search-result-path">${m.breadcrumbTitles.map(esc).join(" › ")}</div>
      </a>`).join("");
  });
}

function render() {
  const segments = currentSegments();
  if (!segments.length) {
    APP_ROOT.innerHTML = renderLanding();
    wireSearch();
    return;
  }
  const { node, breadcrumb } = resolvePath(segments);
  if (!node) {
    APP_ROOT.innerHTML = `<section class="panel"><h2>Not Found</h2>
      <p>No Learn topic exists at <code>${esc(pathFor(segments))}</code>.</p>
      <a data-link href="/learn">&larr; Back to Learn</a></section>`;
    return;
  }
  APP_ROOT.innerHTML = renderTopicPage(node, breadcrumb);
  window.scrollTo(0, 0);
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("a[data-link]");
  if (!link) return;
  e.preventDefault();
  const href = link.getAttribute("href");
  if (href !== window.location.pathname) {
    history.pushState(null, "", href);
  }
  render();
});

window.addEventListener("popstate", render);

async function boot() {
  const resp = await fetch("/learn-tree.json");
  TREE = await resp.json();
  render();
}

boot();
