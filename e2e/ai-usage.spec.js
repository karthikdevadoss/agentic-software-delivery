// /ai-usage: AI Usage Intelligence dashboard (2026-11-28). Public visitors get
// the fictional demo dataset only; live data needs the owner token.
const { test, expect } = require("@playwright/test");

test.describe("AI Usage Intelligence", () => {
  test("public view renders labelled demo data with every section", async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/ai-usage");
    await expect(page.locator("#au-banner")).toContainText("DEMONSTRATION DATA");
    await expect(page.locator("#au-status")).toContainText("Demo data");
    await expect(page.locator("#au-tiles .au-tile").first()).toBeVisible();
    await expect(page.locator("#au-tiles")).toContainText("Cost per verified success");
    await expect(page.locator("#ch-cost svg")).toBeVisible();
    await expect(page.locator("#au-breakdown tbody tr").first()).toBeVisible();
    await expect(page.locator("#au-recs .au-rec").first()).toBeVisible();
    await expect(page.locator("#au-models table").first()).toBeVisible();
    await expect(page.locator("#au-learning .au-tile").first()).toBeVisible();
    await expect(page.locator("#au-method")).toContainText("not an invoice");
    expect(errors).toEqual([]);
  });

  test("session drill-down shows the requests that drove cost", async ({ page }) => {
    await page.goto("/ai-usage");
    await page.locator("#au-sessions tr.clickable").first().click();
    await expect(page.locator("#au-session-detail h3")).toContainText("Session ");
    await expect(page.locator("#au-session-detail")).toContainText("Requests that drove the cost");
  });

  test("a filter narrows the breakdown", async ({ page }) => {
    await page.goto("/ai-usage");
    await expect(page.locator("#au-breakdown tbody tr").first()).toBeVisible();
    await page.selectOption("#f-team_id", "team_support");
    await expect(page.locator("#au-breakdown")).not.toContainText("claude-opus-5-5");
  });

  test("live data without the owner token is refused, not replaced by demo", async ({ page, request }) => {
    const r = await request.get("/api/ai-usage/overview?dataset=live");
    expect(r.status()).toBe(403);
    await page.goto("/ai-usage");
    await page.selectOption("#f-dataset", "live");
    await expect(page.locator("#au-status")).toContainText("Could not load");
    await expect(page.locator("#au-owner")).toBeVisible();
  });

  test("no horizontal overflow on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/ai-usage");
    await expect(page.locator("#au-recs .au-rec").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});
