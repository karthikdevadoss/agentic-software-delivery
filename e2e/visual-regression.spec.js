// Sprint 17, BL-E. Screenshot regression, GATED OFF.
//
//   VISUAL_REGRESSION=1 npx playwright test e2e/visual-regression.spec.js
//   VISUAL_REGRESSION=1 npx playwright test e2e/visual-regression.spec.js --update-snapshots
//
// WHY IT IS OFF, and it is not squeamishness. The Owner has not accepted the new
// baseline. Gating release health on screenshots he has not seen would block
// every branch on a diff nobody agreed to -- and the branch that produced those
// screenshots is the one asking for his opinion. Turning this on is a decision
// for after he has looked, and it is recorded as backlog rather than implied.
//
// WHAT IT CATCHES AND WHAT IT CANNOT, said plainly because Sprints 15 and 16
// both shipped green guards on pages he disliked:
//
//   CATCHES  unintended visual CHANGE. A stylesheet edit that moved a page
//            nobody was looking at. This is a real and common defect here: the
//            Sprint 15 defects came from style.css and dashboard.css, which move
//            every page at once.
//   CANNOT   whether a page looks good. A screenshot baseline of an ugly page is
//            an ugly baseline, faithfully defended. Nothing in this file, and
//            nothing in any guard this sprint adds, measures aesthetics. That
//            remains the Owner's judgement and only his.
//
// MASKING. Only genuinely volatile values -- live timestamps, current cost
// totals, run ids, dynamic counters. Masking is a real cost: a masked region is
// a region this spec no longer protects, so a large mask buys a stable test by
// giving up the coverage the test existed for. Masks here are element-scoped and
// listed per page, never a whole content region.

const { test, expect } = require("@playwright/test");

const ENABLED = ["1", "true", "yes", "on"].includes(
  String(process.env.VISUAL_REGRESSION || "").toLowerCase()
);

// Element-scoped masks. Each entry is a real CSS selector on that page whose
// rendered text changes between runs for reasons that are not a visual
// regression. Anything not listed here IS compared.
const VOLATILE = {
  // Cost totals, run counts and window figures move every time a real run
  // happens or a real Claude Code session is captured.
  usage: [".exec-value", ".econ-value", ".session-id-hint", ".full-session-id",
          ".ledger-recent", ".provenance", "time", ".session-row"],
  dashboard: [".exec-value", ".econ-value", ".stat-value", "time", "code"],
  // "Checked <date>" in the tagline, and the verified-run id resolved at runtime.
  showcase: [".tagline"],
  workbench: ["#target-app-body", ".verified-run-link", "#rs-runid"],
  // The suggested-question chips are drawn from live corpus state.
  "standing-interview": [],
  home: [],
  triage: [],
  "ask-codebase": [],
  "case-study": [],
};

// Pages whose length is a function of how much REAL HISTORY the environment
// holds, capped for this suite only.
//
// MEASURED, and it is not a regression: /usage is 6,759px tall against
// production (2 session rows) and 69,830px tall against this laptop (511 session
// rows, the machine's own accumulated development history). Dashboard is 16,853
// and 47,614. A fullPage screenshot of a 69,830px page times out in Chromium at
// any reasonable limit, and a 69,830px baseline would be useless to diff even if
// it were captured -- a one-row change would shift everything below it.
//
// So these two are captured to a bounded height from the top. That is SCOPING,
// not masking: the region below the cap is not hidden behind a coloured
// rectangle, it is simply outside this suite's remit, and the full-length
// screenshots still exist in the review packs. The cap is well past the first
// screen at either viewport, so the part a recruiter actually sees is compared.
// PER-PAGE, because one number was wrong. With a 4000px cap, /usage desktop
// differed from its own baseline by 256,034 pixels (4%) on a repeat run against
// the same machine and the same tree -- and it was right to. Within those 4000px
// sit the live event-ledger figures and the session-history rows, and both change
// whenever a real run or a real Claude Code session is captured. When a row is
// added, everything below it shifts, and index-based masking cannot follow that.
//
// This is exactly the false-positive-every-run failure the Sprint 16 handoff
// predicted for screenshot baselines on live-data pages. The answer is not a
// looser threshold -- that would blind the suite to real change everywhere -- nor
// a bigger mask, which would hollow out the coverage. It is to compare the part
// of the page that is genuinely stable: /usage's first screen, its four cost
// metrics and its scope explanation, all of which sit above 1600px. What is
// below remains covered by the full-length review packs and by
// e2e/responsive-invariants.spec.js.
const HISTORY_CAP_PX = { usage: 1600, dashboard: 4000 };
const HISTORY_UNBOUNDED = new Set(Object.keys(HISTORY_CAP_PX));

const PAGES = [
  ["home", "/"],
  ["workbench", "/workbench"],
  ["triage", "/triage"],
  ["ask-codebase", "/ask-codebase"],
  ["showcase", "/showcase/senior-java-ai-transformation"],
  ["usage", "/usage"],
  ["standing-interview", "/standing-interview"],
  ["case-study", "/case-study/durable-agent"],
];

const VIEWPORTS = [
  ["desktop", 1920, 1080],
  ["mobile", 390, 844],
];

// Deterministic settling. A fixed sleep captures a different page on a loaded
// machine than on an idle one, and a screenshot baseline whose content depends
// on machine load is not a baseline.
async function settle(page) {
  try { await page.waitForLoadState("networkidle", { timeout: 20000 }); } catch { /* long-poll */ }
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  let last = -1;
  for (let i = 0; i < 20; i++) {
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    if (h === last) break;
    last = h;
    await page.waitForTimeout(150);
  }
  // Freeze anything that animates, so a caret or a transition mid-flight cannot
  // produce a one-pixel diff that reads as a regression.
  await page.addStyleTag({
    content: `*, *::before, *::after {
      animation-play-state: paused !important;
      transition: none !important;
      caret-color: transparent !important;
    }`,
  });
}

test.describe("Visual regression", () => {
  test.skip(!ENABLED,
    "VISUAL_REGRESSION is not set. This suite is deliberately OFF: the Owner has " +
    "not accepted the screenshot baseline, and gating on an unapproved baseline " +
    "would block every branch on a diff nobody agreed to. Run it with " +
    "VISUAL_REGRESSION=1, and see docs/TESTING.md for when it becomes gating.");

  for (const [vpName, width, height] of VIEWPORTS) {
    for (const [name, route] of PAGES) {
      test(`${name} at ${vpName} matches its baseline`, async ({ page }) => {
        // A 70,000px page needs more than the 30s default: settling polls its
        // height, and Playwright resolves one locator per masked element.
        // Measured: /usage desktop needed ~45s before the mask list was bounded
        // below, and still deserves headroom on a loaded machine.
        test.setTimeout(120_000);
        const capped = HISTORY_UNBOUNDED.has(name);
        // A CAPPED PAGE IS CAPTURED BY MAKING THE VIEWPORT THE FRAME, not by
        // clipping a full-page render. `fullPage: true` with a `clip` still makes
        // Chromium lay out and rasterise all 70,000px before throwing away the
        // part outside the clip, which blows toHaveScreenshot's own 5s budget no
        // matter how long the test timeout is -- that was the real cause of the
        // failure here, and it took two wrong fixes (a longer test timeout, a
        // smaller mask list) to find it. A tall viewport rasterises 1920x4000 and
        // nothing else.
        await page.setViewportSize({
          width,
          height: capped ? HISTORY_CAP_PX[name] : height,
        });
        await page.goto(route, { waitUntil: "domcontentloaded" });
        await settle(page);

        const docHeight = await page.evaluate(() => document.documentElement.scrollHeight);
        const captureBottom = capped
          ? Math.min(docHeight, HISTORY_CAP_PX[name])
          : docHeight;

        // MASK ONLY WHAT IS ACTUALLY CAPTURED. /usage has 511 .session-row
        // elements on this machine and every one of them was being resolved into
        // its own locator -- the overwhelming majority of them below the capture
        // cap, so they could not have appeared in the image at all. That alone
        // pushed the test past its timeout: a mask is not free, and masking
        // something outside the frame is pure cost.
        const selectors = VOLATILE[name] || [];
        const mask = [];
        for (const sel of selectors) {
          const visibleIndexes = await page.evaluate(
            ([selector, bottom]) => Array.from(document.querySelectorAll(selector))
              .map((el, i) => [i, el.getBoundingClientRect().top + window.scrollY])
              .filter(([, top]) => top < bottom)
              .map(([i]) => i),
            [sel, captureBottom]
          );
          const loc = page.locator(sel);
          for (const i of visibleIndexes) mask.push(loc.nth(i));
        }

        await expect(page).toHaveScreenshot(`${name}-${vpName}.png`, {
          // fullPage only for pages whose length is bounded by their content.
          fullPage: !capped,
          timeout: 30_000,
          mask,
          maskColor: "#ff00ff",
          // A handful of pixels of text antialiasing differs between runs on the
          // same machine. 0.4% of the page is far below any real visual change
          // (a moved element, a changed colour, a different font) and far above
          // subpixel noise.
          maxDiffPixelRatio: 0.004,
          animations: "disabled",
          scale: "css",
        });
      });
    }
  }
});
