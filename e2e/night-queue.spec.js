// Night queue (2026-10-05), item 52: a real browser check of the three routes a
// recruiter is sent to, plus the one-pager added as item 51. No deploy: this runs
// against a local server only.

const { test, expect } = require("@playwright/test");

const ROUTES = ["/", "/workbench", "/triage"];

test.describe("Browser check of the recruiter routes", () => {
  for (const route of ROUTES) {
    test(`${route} loads, renders its heading and logs no error`, async ({ page }) => {
      const problems = [];
      page.on("console", (message) => {
        if (message.type() === "error") problems.push(message.text());
      });
      page.on("pageerror", (error) => problems.push(String(error)));
      const response = await page.goto(route, { waitUntil: "domcontentloaded" });
      expect(response.status()).toBe(200);
      await expect(page.locator("h1")).toBeVisible();
      await expect(page.locator("#top-nav a")).not.toHaveCount(0, { timeout: 10_000 });
      expect(problems, `${route} logged: ${problems.join(" | ")}`).toEqual([]);
    });

    test(`${route} does not scroll sideways at phone width`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(route, { waitUntil: "domcontentloaded" });
      const overflow = await page.evaluate(() => {
        const el = document.documentElement;
        return el.scrollWidth - el.clientWidth;
      });
      expect(overflow).toBeLessThanOrEqual(1);
    });
  }

  test("the one-pager loads and tells both halves of the approval story", async ({ page }) => {
    const response = await page.goto("/one-pager", { waitUntil: "domcontentloaded" });
    expect(response.status()).toBe(200);
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/deterministic/i);
    expect(body).toMatch(/without a person/i);
    expect(body).toMatch(/waits for a person/i);
    expect(body).not.toMatch(/every change needs a person/i);
    expect(body).not.toMatch(/self-approv/i);
  });

  test("the one-pager links resolve", async ({ page, request }) => {
    await page.goto("/one-pager");
    const hrefs = await page.locator("main a[href^='/']").evaluateAll(
      (nodes) => nodes.map((n) => n.getAttribute("href")));
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) {
      const resp = await request.get(href);
      expect(resp.status(), `${href} did not resolve`).toBe(200);
    }
  });

  test("the Standing Interview page says the records behind it are private", async ({ page }) => {
    await page.goto("/standing-interview");
    const body = await page.locator("body").innerText();
    expect(body).toMatch(/private/i);
    expect(body).toMatch(/not published here|are private/i);
  });
});
