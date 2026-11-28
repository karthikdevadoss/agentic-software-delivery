// /how-i-build (2026-11-28): how the platform is built with an AI coding agent.
const { test, expect } = require("@playwright/test");

test.describe("How I build with AI agents", () => {
  test("renders the authorship statement, the rules and the caught defects", async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/how-i-build");
    await expect(page.locator("h1")).toHaveText("How I build with AI coding agents");
    await expect(page.locator(".iv-lede")).toContainText("written by Claude Code");
    await expect(page.locator(".hb-rules li")).toHaveCount(7);
    await expect(page.locator(".hb-caught tbody tr")).toHaveCount(4);
    await expect(page.locator("#top-nav a").first()).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("is reachable from Home, /kraken and the Interviewer Brief", async ({ page }) => {
    for (const from of ["/", "/kraken", "/interviewer"]) {
      await page.goto(from);
      await expect(page.locator('a[href="/how-i-build"]').first(), from).toBeVisible();
    }
  });

  test("no horizontal scroll on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/how-i-build");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});
