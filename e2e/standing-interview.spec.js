// Sprint 20 (2026-10-05), BL-146: the Standing Interview's first browser spec.
// Written BEFORE the change. It does not call the model: the page's static
// surface and its accessibility are what is asserted here.

const { test, expect } = require("@playwright/test");

test.describe("Standing Interview surface", () => {
  test("the page loads with its heading, names the candidate, and has one main landmark", async ({ page }) => {
    await page.goto("/standing-interview");
    await expect(page.locator("h1")).toContainText(/Standing Interview/i);
    await expect(page.locator("body")).toContainText("Karthikeyan Devadoss");
    await expect(page.locator("main")).toHaveCount(1);
  });

  test("the question field has an accessible name and the answer thread is a live region", async ({ page }) => {
    await page.goto("/standing-interview");
    await expect(page.getByRole("textbox", { name: /interview question/i })).toBeVisible();
    const thread = page.locator("#si-thread");
    await expect(thread).toHaveAttribute("aria-live", "polite");
  });

  test("the page says it answers from the written record or says so", async ({ page }) => {
    await page.goto("/standing-interview");
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/recorded engineering knowledge|written record/i);
    expect(body).toMatch(/(says so|tells you|say so).{0,60}(instead|rather)/i);
  });

  test("the canonical navigation renders on the page", async ({ page }) => {
    await page.goto("/standing-interview");
    const nav = page.locator("#top-nav");
    await expect(nav.locator("a")).not.toHaveCount(0, { timeout: 10_000 });
    for (const label of ["Home", "Workbench", "Triage", "Showcase", "Usage"]) {
      expect(await nav.locator("a").allTextContents()).toContain(label);
    }
  });
});
