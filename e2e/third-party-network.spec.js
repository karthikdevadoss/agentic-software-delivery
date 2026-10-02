// Sprint 17, BL-C5. What a public page FETCHES on first load.
//
// THE MEASUREMENT THAT MADE THIS NECESSARY. The BEFORE capture against real
// production (visual-audit-sprint17-before/manifest.json, 2026-09-30) found
// every one of the nine public pages requesting fonts.googleapis.com on load --
// 1 request on Home and Case Study, 3 on the other seven. Home's own body font
// has been a system stack since Sprint 14, so it was fetching nine typefaces and
// rendering none of them.
//
// WHAT THIS ASSERTS, and what it deliberately does not
// ----------------------------------------------------
// It is NOT "the app may never contact another server", which would be both
// wrong and unenforceable. Three specific things:
//
//   1. ZERO third-party FONT requests. A recruiter in Germany opening a
//      portfolio site should not have their browser call Google, and a system
//      stack paints on the first frame instead of after a round trip.
//   2. ZERO tracker/analytics requests. None exist today; this keeps it that
//      way by accident-prevention rather than by anyone remembering.
//   3. Any OTHER third-party request is reported by host so a new one has to be
//      looked at rather than arriving unnoticed.
//
// Explicitly allowed: same-origin API calls (that is the application working),
// and outbound LINKS to GitHub or LinkedIn -- a link that exists is not a
// request. Only what the page actually fetches counts, which is why this reads
// Playwright's request events rather than grepping the HTML for a hostname.

const { test, expect } = require("@playwright/test");

const PUBLIC_PAGES = [
  ["home", "/"],
  ["workbench", "/workbench"],
  ["triage", "/triage"],
  ["ask-codebase", "/ask-codebase"],
  ["showcase", "/showcase/senior-java-ai-transformation"],
  ["usage", "/usage"],
  ["standing-interview", "/standing-interview"],
  ["case-study", "/case-study/durable-agent"],
  ["dashboard", "/dashboard"],
];

const FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net",
                    "fonts.bunny.net", "cdn.jsdelivr.net/fontsource"];

const TRACKER_HOSTS = [
  "google-analytics.com", "googletagmanager.com", "analytics.google.com",
  "doubleclick.net", "facebook.net", "connect.facebook.com", "hotjar.com",
  "segment.io", "segment.com", "mixpanel.com", "amplitude.com", "sentry.io",
  "clarity.ms", "plausible.io", "posthog.com", "fullstory.com", "intercom.io",
  "newrelic.com", "matomo.cloud", "statcounter.com",
];

// Hosts a page may legitimately reach, each with the reason. Empty is the
// healthy state and it is empty. An entry here is a decision, not a waiver:
// adding one means someone accepted a third-party dependency on a public page.
const APPROVED_THIRD_PARTY = {};

function collect(page, baseHost) {
  const seen = { fonts: [], trackers: [], other: [], sameOrigin: 0 };
  page.on("request", (req) => {
    const url = req.url();
    let host;
    try { host = new URL(url).host; } catch { return; }  // data:/blob: is not a fetch
    if (!host || host === baseHost) { seen.sameOrigin++; return; }
    if (FONT_HOSTS.some((h) => host.includes(h))) { seen.fonts.push(url); return; }
    if (TRACKER_HOSTS.some((h) => host.includes(h))) { seen.trackers.push(url); return; }
    if (Object.keys(APPROVED_THIRD_PARTY).some((h) => host.includes(h))) return;
    seen.other.push(url);
  });
  return seen;
}

test.describe("Third-party network behaviour on public page load", () => {
  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} makes no third-party font request`, async ({ page, baseURL }) => {
      const baseHost = new URL(baseURL).host;
      const seen = collect(page, baseHost);
      await page.goto(route, { waitUntil: "networkidle" });
      // document.fonts.ready is what actually settles a webfont fetch -- a
      // networkidle alone can land before a @font-face in a late stylesheet
      // has been resolved.
      await page.evaluate(() => (document.fonts ? document.fonts.ready : null));
      expect(
        seen.fonts,
        `${name} fetched ${seen.fonts.length} third-party font resource(s): ` +
        `${seen.fonts.join(", ")}. The design lock (docs/DESIGN.md) is system/local ` +
        `fonts only -- see the nine <link> triplets removed in Sprint 17.`
      ).toEqual([]);
    });

    test(`${name} makes no tracker or analytics request`, async ({ page, baseURL }) => {
      const baseHost = new URL(baseURL).host;
      const seen = collect(page, baseHost);
      await page.goto(route, { waitUntil: "networkidle" });
      expect(
        seen.trackers,
        `${name} fetched ${seen.trackers.length} tracker/analytics resource(s): ` +
        `${seen.trackers.join(", ")}. None is approved on a public page.`
      ).toEqual([]);
    });

    test(`${name} makes no unapproved third-party request of any kind`, async ({ page, baseURL }) => {
      const baseHost = new URL(baseURL).host;
      const seen = collect(page, baseHost);
      await page.goto(route, { waitUntil: "networkidle" });
      expect(
        seen.other,
        `${name} fetched ${seen.other.length} unapproved third-party resource(s): ` +
        `${seen.other.join(", ")}. If one of these is genuinely wanted, add its host ` +
        `to APPROVED_THIRD_PARTY with the real reason -- do not delete this assertion.`
      ).toEqual([]);
      // A page that fetched nothing at all would pass every assertion above
      // vacuously, which would make this whole spec worthless the day a route
      // starts 404ing. Same-origin traffic proves the page really loaded.
      expect(
        seen.sameOrigin,
        `${name} made zero same-origin requests, so this spec proved nothing. ` +
        `The page probably did not load.`
      ).toBeGreaterThan(0);
    });
  }
});

test.describe("The guard itself detects the known-bad case", () => {
  // CLAUDE.md: a diagnostic whose clean result nobody has watched go dirty is
  // not trusted. This injects the exact <link> that was removed from nine pages
  // and proves the detection fires -- so a future green result means something.
  //
  // It routes the request to an abort rather than letting it reach Google: the
  // point is that the REQUEST was made and seen, not that it succeeded.
  test("an injected Google Fonts link is caught", async ({ page, baseURL }) => {
    const baseHost = new URL(baseURL).host;
    const seen = collect(page, baseHost);
    await page.route("**fonts.googleapis.com**", (r) => r.abort());
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400&display=swap";
      document.head.appendChild(link);
    });
    await page.waitForTimeout(700);
    expect(
      seen.fonts.length,
      "the font-request detector did not see an injected fonts.googleapis.com " +
      "stylesheet, so its clean results on the nine real pages prove nothing"
    ).toBeGreaterThan(0);
  });
});
