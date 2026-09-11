// Focused tests for agent/web/learn.js — the recursive Learn Wikipedia
// client-side router (P0-A). Plain-Node vm-based harness (no jsdom, no
// new dependency), matching this project's existing convention
// (test_trainer_frontend.js). Exercises the REAL learn.js source loaded
// as-is against a small deterministic fixture tree (not the full real
// 268-topic tree, to keep this fast and independent of live data).
//
// Run: node agent/test_learn_frontend.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");

let failures = 0;
let passed = 0;

function assert(cond, msg) {
  if (!cond) { failures++; console.error("FAIL: " + msg); }
  else { passed++; }
}
function assertEqual(actual, expected, msg) {
  assert(JSON.stringify(actual) === JSON.stringify(expected), `${msg} (expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)})`);
}
function assertIncludes(haystack, needle, msg) {
  assert(String(haystack).includes(needle), `${msg} — expected to find ${JSON.stringify(needle)}`);
}

const FIXTURE_TREE = {
  generated_at_utc: "2026-09-11T00:00:00Z",
  git_commit: "abc1234",
  metrics: { total_domains: 1, total_reference_topics: 3, total_deep_topics: 1,
             current_project_experience_topics: 2, real_professional_experience_topics: 0,
             learned_understood_topics: 1, planned_not_experienced_topics: 0 },
  domains: [
    {
      slug: "system-design", title: "System Design", kind: "domain",
      short_overview: "How to design systems.",
      children: [
        {
          slug: "databases", title: "Databases", kind: "topic",
          short_overview: "Systems of record.",
          children: [
            {
              slug: "connection-pooling", title: "Connection Pooling", kind: "topic",
              short_overview: "Reuses connections.",
              experience_classification: "CURRENT_PROJECT_EXPERIENCE",
              children: [],
              sections: { what: "Reuses DB connections.", why: "Opening one is expensive." },
              related: ["hikaricp"],
            },
            {
              slug: "hikaricp", title: "HikariCP", kind: "topic",
              short_overview: "The default Spring Boot pool.",
              experience_classification: "CURRENT_PROJECT_EXPERIENCE",
              children: [], sections: { what: "A fast JDBC pool." },
            },
          ],
        },
      ],
    },
  ],
};

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function makeElement() {
  const el = {
    _innerHTML: "", value: "", style: {},
    get innerHTML() { return this._innerHTML; },
    set innerHTML(v) { this._innerHTML = v; },
    addEventListener() {},
  };
  return el;
}

function buildContext(initialPath) {
  const elements = { "learn-app": makeElement() };
  let currentPath = initialPath;
  const historyEntries = [];

  const documentStub = {
    getElementById: (id) => elements[id] || null,
    addEventListener: () => {},
    createElement: () => ({ set textContent(v) { this._t = v; }, get innerHTML() { return escapeHtml(this._t); } }),
    querySelectorAll: () => [],
  };

  const locationStub = { get pathname() { return currentPath; } };
  const historyStub = {
    pushState: (_s, _t, href) => { currentPath = href; historyEntries.push(href); },
  };

  const windowStub = {
    location: locationStub,
    addEventListener: () => {},
    scrollTo: () => {},
  };

  let fetchedTree = null;
  const fetchStub = async (url) => {
    if (url === "/learn-tree.json") {
      return { json: async () => FIXTURE_TREE };
    }
    throw new Error("unexpected fetch: " + url);
  };

  const sandbox = {
    document: documentStub,
    window: windowStub,
    location: locationStub,
    history: historyStub,
    fetch: fetchStub,
    console,
    setTimeout, clearTimeout,
  };
  vm.createContext(sandbox);
  return { sandbox, elements, get currentPath() { return currentPath; }, set currentPath(p) { currentPath = p; }, historyEntries };
}

async function loadLearnJs(ctx) {
  const src = fs.readFileSync(path.join(__dirname, "web", "learn.js"), "utf8");
  const script = new vm.Script(src, { filename: "learn.js" });
  script.runInContext(ctx.sandbox);
  // boot() is async and self-invoked at module load; give it a tick.
  await new Promise((r) => setTimeout(r, 20));
}

(async () => {
  // ---- Landing page ------------------------------------------------
  {
    const ctx = buildContext("/learn");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "System Design", "landing page shows the domain card");
    assertIncludes(html, "DOWNLOAD COMPLETE BOOK", "landing page shows the PDF download button");
    assertIncludes(html, "/api/learn/book.pdf", "PDF button links to the real PDF endpoint");
  }

  // ---- Domain click / dedicated route -------------------------------
  {
    const ctx = buildContext("/learn/system-design");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "System Design", "domain page shows its own title");
    assertIncludes(html, "Databases", "domain page shows its child topic");
    assertIncludes(html, "/learn/system-design/databases", "child link uses the correct nested route");
  }

  // ---- Deeper recursion + breadcrumb ---------------------------------
  {
    const ctx = buildContext("/learn/system-design/databases/connection-pooling");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "Connection Pooling", "leaf topic page shows its own title");
    assertIncludes(html, "breadcrumb", "leaf topic page renders a breadcrumb");
    assertIncludes(html, "System Design", "breadcrumb includes the root domain");
    assertIncludes(html, "Databases", "breadcrumb includes the intermediate topic");
    assertIncludes(html, "WHAT", "leaf topic renders its WHAT section");
    assertIncludes(html, "WHY", "leaf topic renders its WHY section");
  }

  // ---- Related topic links resolve correctly -------------------------
  {
    const ctx = buildContext("/learn/system-design/databases/connection-pooling");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "/learn/system-design/databases/hikaricp", "related topic link resolves to its real full path");
  }

  // ---- Invalid slug -> Not Found (client-side render) ----------------
  {
    const ctx = buildContext("/learn/does-not-exist");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "Not Found", "unknown path renders a Not Found state client-side");
  }

  // ---- UI hardening pass: domain/topic distinction, experience-badge
  // family kept separate from legacy evidence-status badges, back-link,
  // depth hints, PDF panel with loading/error handling -----------------
  {
    const ctx = buildContext("/learn");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "domain-kind-tag", "landing page visually tags domain cards as DOMAIN");
    assertIncludes(html, "exp-legend", "landing page shows the experience-classification legend");
    assertIncludes(html, "exp-badge-project", "legend uses the dedicated exp-badge family, not ev-badge");
    assert(!html.includes("ev-runtime-verified"), "experience classification must not reuse the legacy ev-badge classes");
  }
  {
    const ctx = buildContext("/learn/system-design");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "back-link", "topic page shows an explicit back-link, not just the breadcrumb");
    assertIncludes(html, "depth-hint", "child topic cards show a depth hint (sub-topic count or leaf)");
  }
  {
    // Within "databases"' child grid, both children (connection-pooling,
    // hikaricp) are themselves childless in the fixture -> each must be
    // marked as a leaf topic, not silently given a misleading sub-topic count.
    const ctx = buildContext("/learn/system-design/databases");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "depth-hint-leaf", "a childless child topic is visually marked as a leaf topic");
  }
  {
    const ctx = buildContext("/learn");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, 'id="learn-pdf-download"', "PDF download button exists with its stable id");
    assertIncludes(html, 'href="/api/learn/book.pdf"', "PDF button points at the real endpoint");
  }

  console.log(`${passed} passed, ${failures} failed`);
  process.exit(failures ? 1 : 0);
})();
