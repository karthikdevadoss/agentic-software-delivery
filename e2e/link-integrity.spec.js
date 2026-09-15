// Generalized public-link-integrity sweep (Base Architecture V3, Phase 1
// audit MEDIUM finding, docs/INTELLIGENCE_PLACEMENT_V3.md): before this
// spec, only Showcase's manifest-driven links had an automated check
// (agent/test_showcase_data.py, added for AEQ-022 -- a bare repo-relative
// path rendered as <a href>, 404ing on /showcase/<slug>'s current page).
// Every OTHER public page's rendered <a href> set (hardcoded nav links,
// JS-rendered links) had zero automated coverage; the same defect class
// could recur anywhere and nothing would catch it. This crawls every real
// public route's rendered links and asserts each resolves to a real
// destination, mirroring agent/test_showcase_data.py's classify_link()
// logic (BARE_RELATIVE_PATH / broken internal route = fail).

const { test, expect } = require("@playwright/test");

// Real public routes, from agent/web_server.py's own route table (not
// memorized/assumed) -- "/control-plane" is deliberately internal/debug,
// not public navigation, so it's excluded; there is no public "/profile"
// route in the current route table.
const PUBLIC_PAGES = [
  "/",
  "/workbench",
  "/dashboard",
  "/usage",
  "/showcase/senior-java-ai-transformation",
  "/triage",
  "/triage/scenario-b",
  "/triage/scenario-c",
  "/learn",
];

function classifyHref(href) {
  if (/^https?:\/\/[^/]+/i.test(href)) return "ABSOLUTE_EXTERNAL";
  if (href.startsWith("/")) return "INTERNAL_PATH";
  if (href.startsWith("mailto:") || href.startsWith("#")) return "NON_NAVIGATIONAL";
  // The exact AEQ-022 defect shape: a bare relative path with no leading
  // "/" and no scheme -- never valid as a rendered destination.
  return "BARE_RELATIVE_PATH";
}

test.describe("Public link integrity", () => {
  for (const pagePath of PUBLIC_PAGES) {
    test(`every rendered link on ${pagePath} resolves to a real destination`, async ({ page, request }) => {
      await page.goto(pagePath);
      const hrefs = await page.locator("a[href]").evaluateAll((els) =>
        els.map((el) => el.getAttribute("href")).filter(Boolean)
      );

      const broken = [];
      const checkedInternal = new Set();
      for (const href of hrefs) {
        const kind = classifyHref(href);
        if (kind === "BARE_RELATIVE_PATH") {
          broken.push(`${href} (BARE_RELATIVE_PATH -- the exact AEQ-022 defect shape)`);
          continue;
        }
        if (kind === "ABSOLUTE_EXTERNAL" || kind === "NON_NAVIGATIONAL") {
          continue; // well-formed absolute URL or a non-navigational anchor -- not this sweep's job to fetch external hosts
        }
        // INTERNAL_PATH: must actually resolve. Strip query/hash before
        // the request, dedupe repeats (many pages repeat the same nav
        // link across every row of a table, no need to re-fetch each).
        const pathOnly = href.split("#")[0].split("?")[0];
        if (checkedInternal.has(pathOnly)) continue;
        checkedInternal.add(pathOnly);
        const res = await request.get(pathOnly);
        if (res.status() >= 400) {
          broken.push(`${href} -> HTTP ${res.status()} (BROKEN_INTERNAL_ROUTE)`);
        }
      }

      expect(
        broken,
        `Page ${pagePath} has link(s) that will not resolve for a real visitor:\n` + broken.join("\n")
      ).toEqual([]);
    });
  }
});
