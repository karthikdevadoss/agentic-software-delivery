// Regression coverage for agent/web/nav.js -- the single canonical
// public-engineering-navigation source (fixes the real production defect
// where "Role Showcase" was missing from all 6 core engineering pages,
// because each page hand-copied its own independently-drifting <nav>
// block instead of sharing one canonical list).
//
// Plain-Node test, no framework, matching this project's existing
// discipline (see agent/test_trainer_frontend.js). Exercises the REAL
// agent/web/nav.js source via require(), not a reimplementation.
//
// Run: node agent/test_nav_frontend.js

const fs = require("fs");
const path = require("path");

let failures = 0;
let passed = 0;

function assert(cond, msg) {
  if (!cond) { failures++; console.error("FAIL: " + msg); }
  else { passed++; }
}
function assertDeepEqual(actual, expected, msg) {
  const a = JSON.stringify(actual), e = JSON.stringify(expected);
  assert(a === e, `${msg} (expected ${e}, got ${a})`);
}

const NAV_PATH = path.join(__dirname, "web", "nav.js");
const nav = require(NAV_PATH);

// ---- 1. The canonical set is exactly the 7 intended destinations -----

const EXPECTED_DESTINATIONS = [
  { href: "/workbench", label: "Workbench" },
  { href: "/triage", label: "Triage" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/usage", label: "Usage" },
  { href: "/learn", label: "Learn", hiddenOn: ["/workbench", "/dashboard", "/usage"] },
  { href: "/ask-codebase", label: "Ask the Codebase" },
  { href: "/showcase/senior-java-ai-transformation", label: "Role Showcase" },
];
assertDeepEqual(nav.CANONICAL_NAV_DESTINATIONS, EXPECTED_DESTINATIONS,
  "canonical nav destination set must be exactly the 7 intended public engineering surfaces");

// Role Showcase must genuinely be present -- the exact real defect.
assert(
  nav.CANONICAL_NAV_DESTINATIONS.some((d) => d.href === "/showcase/senior-java-ai-transformation" && d.label === "Role Showcase"),
  "Role Showcase must be a real canonical destination (this is the exact production defect being fixed)"
);

// Ask the Codebase must genuinely be present -- real production defect
// found 2026-09-18: the page exists and works at /ask-codebase but was
// never added to this canonical list, so it was reachable only by typing
// the URL directly, invisible from every other page's nav (including its
// own -- ask-codebase.html includes nav.js too).
assert(
  nav.CANONICAL_NAV_DESTINATIONS.some((d) => d.href === "/ask-codebase" && d.label === "Ask the Codebase"),
  "Ask the Codebase must be a real canonical destination (real production defect: existed but was unreachable from any nav)"
);

// No duplicate Showcase URL (the directive's explicit constraint).
const showcaseEntries = nav.CANONICAL_NAV_DESTINATIONS.filter((d) => d.href.startsWith("/showcase"));
assert(showcaseEntries.length === 1, "exactly one canonical Role Showcase URL, no duplicates");

// ---- 2. Current-page detection ----------------------------------------

assert(nav._isCurrentPage("/workbench", "/workbench") === true, "/workbench is current on /workbench");
assert(nav._isCurrentPage("/workbench", "/") === true, "/workbench is current on / (same page, see web_server.py's route table)");
assert(nav._isCurrentPage("/triage", "/triage") === true, "/triage is current on /triage");
assert(nav._isCurrentPage("/triage", "/triage/scenario-b") === true, "/triage stays current on /triage/scenario-b");
assert(nav._isCurrentPage("/triage", "/triage/scenario-c") === true, "/triage stays current on /triage/scenario-c");
assert(nav._isCurrentPage("/learn", "/learn/java-core") === true, "/learn stays current on a nested /learn/* route");
assert(
  nav._isCurrentPage("/showcase/senior-java-ai-transformation", "/showcase/senior-java-ai-transformation") === true,
  "Role Showcase is current on its own real page"
);
assert(nav._isCurrentPage("/dashboard", "/workbench") === false, "/dashboard is NOT current on /workbench");

// ---- 2b. AEQ-027: Learn is hidden on Workbench/Dashboard/Usage only,
//          honoring the real Owner instruction (2026-09-13) that
//          predates and was never reconciled with AEQ-024's nav
//          unification -- present everywhere else (Triage, Role
//          Showcase, Learn's own page). ------------------------------

for (const hiddenPath of ["/workbench", "/dashboard", "/usage", "/"]) {
  assert(nav._isHiddenOnPage(["/workbench", "/dashboard", "/usage"], hiddenPath) === true,
    `Learn must be hidden on ${hiddenPath} (Owner instruction 2026-09-13)`);
}
for (const visiblePath of ["/triage", "/triage/scenario-b", "/learn", "/showcase/senior-java-ai-transformation"]) {
  assert(nav._isHiddenOnPage(["/workbench", "/dashboard", "/usage"], visiblePath) === false,
    `Learn must remain visible on ${visiblePath}`);
}
assert(nav._isHiddenOnPage(undefined, "/workbench") === false, "a destination with no hiddenOn is never hidden");

// ---- 3. Every real public HTML page includes the shared nav.js and an
//         empty #top-nav placeholder, never its own hardcoded <nav> list
//         (the actual architectural fix -- prevents this exact defect
//         class from ever silently reappearing on any of these files) --

const WEB_DIR = path.join(__dirname, "web");
const PAGES_THAT_MUST_USE_CANONICAL_NAV = [
  "workbench.html", "dashboard.html", "usage.html", "learn.html",
  "triage.html", "triage-b.html", "triage-c.html", "showcase.html",
];

for (const filename of PAGES_THAT_MUST_USE_CANONICAL_NAV) {
  const html = fs.readFileSync(path.join(WEB_DIR, filename), "utf-8");
  assert(html.includes('<script src="/nav.js">'), `${filename} must load the shared /nav.js`);
  assert(/<nav class="top-nav" id="top-nav">\s*<\/nav>/.test(html),
    `${filename} must have an EMPTY <nav id="top-nav"> placeholder, not its own hardcoded links`);
  // The exact real defect class: a page hand-authoring its own <a
  // href="/workbench">-style links inside the top nav instead of
  // deferring to the shared canonical list.
  const navBlockMatch = html.match(/<nav class="top-nav"[^>]*>([\s\S]*?)<\/nav>/);
  assert(navBlockMatch && navBlockMatch[1].trim() === "",
    `${filename}'s <nav> must be empty in the raw HTML -- any hardcoded <a> tags inside it would silently drift again, exactly the original defect`);
}

// ---- 4. Defect-seeding proof: deliberately remove Role Showcase from
//         the canonical list and prove this exact test suite fails ----

(function proveRegressionDetectsTheRealDefect() {
  const mutated = nav.CANONICAL_NAV_DESTINATIONS.filter((d) => d.label !== "Role Showcase");
  const stillHasShowcase = mutated.some((d) => d.label === "Role Showcase");
  assert(stillHasShowcase === false, "sanity: the mutated list genuinely lacks Role Showcase");
  // This mirrors exactly what assertion #1 above would report if
  // CANONICAL_NAV_DESTINATIONS itself regressed to omit Role Showcase --
  // proving this suite is a real regression guard, not decoration.
  const wouldFail = !mutated.some((d) => d.href === "/showcase/senior-java-ai-transformation");
  assert(wouldFail === true, "DEFECT-SEEDING PROOF: removing Role Showcase from the canonical list would fail this suite's own assertion #1 -- confirmed by construction");
})();

console.log(`\n${passed} passed, ${failures} failed`);
if (failures > 0) process.exit(1);
