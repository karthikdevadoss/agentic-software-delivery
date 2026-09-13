// PRIVACY P0 (2026-09-13): /profile must be hidden from public users. It
// was previously a public recruiter-facing resume page (see git history /
// docs/archive/profile_preserved/ for the preserved source), but this
// phase made it non-public per explicit Owner instruction. These tests
// exercise the RENDERED/network behavior (not just source grep) so a
// regression that re-exposes the page is caught immediately.

const { test, expect } = require("@playwright/test");

test.describe("Profile privacy — direct access must not expose content", () => {
  test("direct navigation to /profile returns a real 404, not the resume content", async ({ page }) => {
    const response = await page.goto("/profile");
    expect(response.status()).toBe(404);
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("Karthikeyan Devadoss");
    expect(bodyText).not.toContain("Senior Backend Engineer");
  });

  test("direct navigation to /profile.html (static fallback path) also does not expose content", async ({ page }) => {
    const response = await page.goto("/profile.html");
    expect(response.status()).toBe(404);
  });

  test("no public page links to /profile", async ({ page }) => {
    for (const path of ["/workbench", "/dashboard", "/usage", "/learn"]) {
      await page.goto(path);
      const profileLink = page.locator('a[href="/profile"]');
      await expect(profileLink).toHaveCount(0);
    }
  });
});

test.describe("Workbench — verified run access without submitting", () => {
  test("SEE A VERIFIED RUN is visible and resolves to real data", async ({ page }) => {
    await page.goto("/workbench");
    const link = page.getByRole("link", { name: /SEE A VERIFIED RUN/ });
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/usage\/session\/trainer-/);
    await expect(page.locator(".summary-value").getByText("COMPLETED", { exact: true })).toBeVisible();
  });

  test("Workbench renders correctly at mobile viewport (real defect this task fixed: missing viewport meta tag)", async ({ browser }) => {
    const context = await browser.newContext({ ...require("@playwright/test").devices["iPhone 12"] });
    const page = await context.newPage();
    await page.goto("/workbench");
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
    await context.close();
  });
});
