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
              related: ["hikaricp", "pool-sizing"],
            },
            {
              slug: "hikaricp", title: "HikariCP", kind: "topic",
              short_overview: "The default Spring Boot pool.",
              experience_classification: "CURRENT_PROJECT_EXPERIENCE",
              children: [], sections: { what: "A fast JDBC pool." },
            },
          ],
        },
        {
          slug: "performance", title: "Performance", kind: "topic",
          short_overview: "How fast and how much load a system can carry.",
          children: [
            {
              // Canonically lives under Performance, NOT Databases -- the
              // exact real Owner-reported scenario (2026-09-11).
              slug: "pool-sizing", title: "Pool Sizing", kind: "topic",
              short_overview: "How many pooled connections to allocate.",
              experience_classification: "LEARNED_UNDERSTOOD",
              children: [], sections: { what: "Sizing a pool correctly." },
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

  const locationStub = {
    get pathname() { return currentPath.split("?")[0]; },
    get search() { const i = currentPath.indexOf("?"); return i === -1 ? "" : currentPath.slice(i); },
  };
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
    URLSearchParams,
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

  // ---- Related-topic navigation context (Owner-observed defect,
  // 2026-09-11): Connection Pooling -> related "Pool Sizing" must NOT
  // silently lose the user's journey, and must NOT duplicate the node
  // under two canonical parents ------------------------------------------
  {
    // Canonical direct/bookmarked visit: no ?from= -> normal canonical
    // back-link to the REAL parent (Performance), no "Referenced from".
    const ctx = buildContext("/learn/system-design/performance/pool-sizing");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "Back to Performance", "direct visit to Pool Sizing uses its real canonical parent");
    assertIncludes(html, "System Design", "canonical breadcrumb still includes the true hierarchy");
    assert(!html.includes("referenced-from"), "a direct/bookmarked visit shows no 'Referenced from' context");
  }
  {
    // Clicking the related-topic chip from Connection Pooling's page must
    // link with a ?from= context, not a bare canonical URL.
    const ctx = buildContext("/learn/system-design/databases/connection-pooling");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "/learn/system-design/performance/pool-sizing?from=system-design%2Fdatabases%2Fconnection-pooling",
      "related-topic link to Pool Sizing carries the Connection Pooling origin as context");
  }
  {
    // Arriving at Pool Sizing WITH the origin context: contextual back
    // link to Connection Pooling, a "Referenced from" trail, AND the
    // canonical breadcrumb must still show the TRUE hierarchy (System
    // Design / Performance / Pool Sizing) -- never duplicated content.
    const ctx = buildContext("/learn/system-design/performance/pool-sizing?from=system-design%2Fdatabases%2Fconnection-pooling");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "Back to Connection Pooling", "contextual back-link points to the real origin, not the canonical parent");
    assertIncludes(html, "referenced-from", "a 'Referenced from' trail is shown when arriving via context");
    assertIncludes(html, "Databases", "referenced-from trail names the real origin path");
    assertIncludes(html, "Pool Sizing", "canonical breadcrumb still shows this node's one true title");
    assert(!html.includes("Back to Performance"), "contextual back-link replaces (not duplicates) the canonical one");
  }
  {
    // An invalid/stale ?from= must fail safe to canonical navigation, not
    // crash or dead-end.
    const ctx = buildContext("/learn/system-design/performance/pool-sizing?from=does-not-exist%2Fanywhere");
    await loadLearnJs(ctx);
    const html = ctx.elements["learn-app"].innerHTML;
    assertIncludes(html, "Back to Performance", "an unresolvable ?from= falls back to the canonical parent, not a crash");
  }

  console.log(`${passed} passed, ${failures} failed`);
  process.exit(failures ? 1 : 0);
})();
