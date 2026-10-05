// Sprint 20 (2026-10-05): the Usage page is bounded. Written BEFORE the change.
//
// Measured 2026-09-29 (docs/UI_DEFECTS_2026-09-29.md D7): /usage was 5260px,
// 4.9 screens, with the point of the page below a dense heading. A hiring
// manager should see the point on the first screen and not scroll through the
// full breakdown unless they ask for it. The required wording from
// e2e/copy-contract.spec.js stays on the page and stays visible by default.

const { test, expect } = require("@playwright/test");

const VIEWPORT = { width: 1920, height: 940 };
const MAX_SCREENS = 3;

test.describe("Usage is bounded", () => {
  test.use({ viewport: VIEWPORT });

  test("without a click the page is at most three screens tall", async ({ page }) => {
    await page.goto("/usage", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Session History" })).toBeVisible();
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(height, `scrollHeight ${height}px is more than ${MAX_SCREENS} screens of ${VIEWPORT.height}px`)
      .toBeLessThanOrEqual(MAX_SCREENS * VIEWPORT.height);
  });

  test("the point is on the first screen", async ({ page }) => {
    await page.goto("/usage", { waitUntil: "networkidle" });
    const heading = page.getByRole("heading", { name: /Workbench Delivery Efficiency/i });
    await expect(heading).toBeVisible();
    const box = await heading.boundingBox();
    expect(box.y, "the efficiency heading must start within the first screen").toBeLessThan(VIEWPORT.height);
  });

  test("the full breakdown is still there, behind one control", async ({ page }) => {
    await page.goto("/usage", { waitUntil: "networkidle" });
    const control = page.locator("details.usage-breakdown > summary.usage-more");
    await expect(control).toBeVisible();
    await expect(control).toContainText(/full breakdown/i);
    const before = await page.evaluate(() => document.documentElement.scrollHeight);
    await control.click();
    await expect(page.getByRole("heading", { name: /What the spending is split into/i })).toBeVisible();
    const after = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(after).toBeGreaterThan(before);
  });

  test("the scope wording is visible by default, not hidden in the breakdown", async ({ page }) => {
    await page.goto("/usage", { waitUntil: "networkidle" });
    const visible = await page.evaluate(() => {
      const out = [];
      for (const el of document.querySelectorAll("header p, main p, main h2")) {
        if (el.closest("details:not([open])")) continue;
        out.push(el.innerText);
      }
      return out.join("\n");
    });
    expect(visible).toMatch(/does NOT include Claude Code/i);
    expect(visible).toMatch(/this platform's own metered spend/i);
  });
});
