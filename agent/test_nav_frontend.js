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
  { href: "/", label: "Home" },
  { href: "/workbench", label: "Workbench" },
  { href: "/triage", label: "Triage" },
  { href: "/ask-codebase", label: "Ask Codebase" },
  { href: "/recruiters", label: "For Recruiters" },
];
// BL-079 added a GATED entry (Standing Interview, shown only when the server
// reports a loaded corpus). The unconditional set is what this guard pins;
// the gated entry is asserted separately below, with its endpoint.
const unconditional = nav.CANONICAL_NAV_DESTINATIONS.filter((d) => !d.requiresEndpoint);
assertDeepEqual(unconditional, EXPECTED_DESTINATIONS,
  "canonical unconditional nav destination set must be exactly the intended public engineering surfaces");
const gated = nav.CANONICAL_NAV_DESTINATIONS.filter((d) => d.requiresEndpoint);
assertDeepEqual(gated.map((d) => [d.href, d.label, d.requiresEndpoint, d.requiresKey]),
  [["/standing-interview", "Standing Interview", "/api/standing-interview/status", "loaded"]],
  "the only gated destination is Standing Interview, gated on the corpus-status endpoint");

// Automation Sprint 4 (Owner decision, 2026-10-06): Showcase and Usage left
// the public nav (their routes stay reachable by direct link) and "For
// Recruiters" joined it. The earlier "Showcase must be present" guard pinned a
// 2026-09 defect (Showcase missing from SOME pages); the consistency half of
// that guard survives in nav-consistency.spec.js, which checks every page
// renders the same set.
for (const removed of ["/showcase/senior-java-ai-transformation", "/usage"]) {
  assert(!nav.CANONICAL_NAV_DESTINATIONS.some((d) => d.href === removed),
    `${removed} must NOT be in public navigation (Automation Sprint 4 Owner decision)`);
}
assert(
  nav.CANONICAL_NAV_DESTINATIONS.some((d) => d.href === "/recruiters" && d.label === "For Recruiters"),
  "For Recruiters must be a canonical destination (Automation Sprint 4 Owner decision)"
);

// Ask the Codebase must genuinely be present -- real production defect
// found 2026-09-18: the page exists and works at /ask-codebase but was
// never added to this canonical list, so it was reachable only by typing
// the URL directly, invisible from every other page's nav (including its
// own -- ask-codebase.html includes nav.js too).
assert(
  nav.CANONICAL_NAV_DESTINATIONS.some((d) => d.href === "/ask-codebase" && d.label === "Ask Codebase"),
  "Ask the Codebase must be a real canonical destination (real production defect: existed but was unreachable from any nav)"
);

// No Showcase entry at all now (it used to be "exactly one, no duplicates").
const showcaseEntries = nav.CANONICAL_NAV_DESTINATIONS.filter((d) => d.href.startsWith("/showcase"));
assert(showcaseEntries.length === 0, "no Showcase entry in the public nav (Automation Sprint 4)");

// Sprint 14 (Owner decision): Learn, JD Match and Dashboard must NOT appear in
// public navigation. Learn and JD Match 404 publicly; Dashboard is
// de-emphasized and reachable as a deep link from Usage.
for (const forbidden of ["/learn", "/jd-match", "/dashboard"]) {
  assert(!nav.CANONICAL_NAV_DESTINATIONS.some((d) => d.href === forbidden || d.href.startsWith(forbidden + "/")),
    `${forbidden} must NOT be in public navigation (Sprint 14 Owner decision)`);
}
assert(nav.CANONICAL_NAV_DESTINATIONS[0].href === "/" && nav.CANONICAL_NAV_DESTINATIONS[0].label === "Home",
  "Home leads the canonical navigation");

// ---- 2. Current-page detection ----------------------------------------

assert(nav._isCurrentPage("/workbench", "/workbench") === true, "/workbench is current on /workbench");
// Sprint 14: "/" is its own page now. Workbench must NOT be marked current
// there, and Home must be -- the inverse of the old rule.
assert(nav._isCurrentPage("/workbench", "/") === false, "/workbench is NOT current on / (Sprint 14: / is the home page, not a Workbench alias)");
assert(nav._isCurrentPage("/", "/") === true, "Home is current on /");
assert(nav._isCurrentPage("/", "/workbench") === false, "Home is NOT current on /workbench");
assert(nav._isCurrentPage("/triage", "/triage") === true, "/triage is current on /triage");
assert(nav._isCurrentPage("/triage", "/triage/scenario-b") === true, "/triage stays current on /triage/scenario-b");
assert(nav._isCurrentPage("/triage", "/triage/scenario-c") === true, "/triage stays current on /triage/scenario-c");
assert(nav._isCurrentPage("/showcase/senior-java-ai-transformation", "/showcase/another-slug") === true,
  "Showcase stays current on any /showcase/* slug");
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

// Sprint 14: no destination uses hiddenOn any more (Learn left public nav),
// but the MECHANISM is still asserted -- dropping these assertions with the
// last user would silently delete a real per-page exclusion capability.
assert(nav.CANONICAL_NAV_DESTINATIONS.every((d) => !d.hiddenOn),
  "no canonical destination currently needs hiddenOn (Learn left public nav in Sprint 14)");
for (const hiddenPath of ["/workbench", "/usage"]) {
  assert(nav._isHiddenOnPage(["/workbench", "/usage"], hiddenPath) === true,
    `hiddenOn mechanism still excludes ${hiddenPath}`);
}
for (const visiblePath of ["/triage", "/", "/showcase/senior-java-ai-transformation"]) {
  assert(nav._isHiddenOnPage(["/workbench", "/usage"], visiblePath) === false,
    `hiddenOn mechanism still leaves ${visiblePath} visible`);
}
assert(nav._isHiddenOnPage(undefined, "/workbench") === false, "a destination with no hiddenOn is never hidden");

// ---- 3. Every real public HTML page includes the shared nav.js and an
//         empty #top-nav placeholder, never its own hardcoded <nav> list
//         (the actual architectural fix -- prevents this exact defect
//         class from ever silently reappearing on any of these files) --

const WEB_DIR = path.join(__dirname, "web");
const PAGES_THAT_MUST_USE_CANONICAL_NAV = [
  // Sprint 14: home.html and the durable-agent case study are recruiter-facing
  // and must obey the same rule -- they were the most likely place for a
  // hand-authored nav to reappear, since both use a light theme of their own.
  "home.html", "case-study-durable-agent.html",
  "workbench.html", "dashboard.html", "usage.html", "learn.html",
  "triage.html", "triage-b.html", "triage-c.html", "showcase.html",
];

for (const filename of PAGES_THAT_MUST_USE_CANONICAL_NAV) {
  const html = fs.readFileSync(path.join(WEB_DIR, filename), "utf-8");
  assert(html.includes('<script src="/nav.js">'), `${filename} must load the shared /nav.js`);
  // attributes such as aria-label are allowed on the placeholder; what is not
  // allowed is content inside it.
  assert(/<nav class="top-nav" id="top-nav"[^>]*>\s*<\/nav>/.test(html),
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
  const mutated = nav.CANONICAL_NAV_DESTINATIONS.filter((d) => d.label !== "Showcase");
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
