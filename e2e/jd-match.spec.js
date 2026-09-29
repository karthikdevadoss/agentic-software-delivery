// Real-browser coverage for JD Match (/jd-match): the sample JD run renders a
// result table, evidence links resolve into the public repo or a live route,
// the canonical nav is present, the page is sane at phone width and logs no
// console errors. Each spec makes at most one real submission because the
// API has a per-minute cooldown; the result-table checks reuse one run.

const { test, expect } = require("@playwright/test");

test.describe("JD Match", () => {
  test("page explains the honesty model within the first screen and has no console errors", async ({ page }) => {
    const errors = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto("/jd-match");
    await expect(page.locator("h1")).toContainText("JD Match");
    await expect(page.getByText("How this stays honest")).toBeVisible();
    await expect(page.getByText(/code decides what you see/i)).toBeVisible();
    await expect(page.locator("#top-nav a")).not.toHaveCount(0);
    expect(errors).toEqual([]);
  });

  test("the sample button fills the textarea and a run renders a result table with registry links", async ({ page }) => {
    // A real run is two model calls plus, on a cold server, the local embedder's
    // first load -- well past the default 30s per-test budget.
    test.setTimeout(240_000);
    await page.goto("/jd-match");
    await page.click("#jd-sample");
    await expect(page.locator("#jd-text")).toHaveValue(/Senior Backend Engineer/, { timeout: 10_000 });
    await page.click("#jd-submit");
    await expect(page.locator("#jd-result-panel")).toBeVisible({ timeout: 120_000 });
    const summary = page.locator(".jd-summary-line");
    const refusal = page.locator(".jd-refusal");
    await expect(summary.or(refusal)).toBeVisible({ timeout: 120_000 });
    if (await refusal.count()) {
      // A cooldown/daily-cap/kill-switch refusal is an honest state, not a
      // broken page; assert it is rendered as such and stop here.
      await expect(refusal.locator(".jd-status-pill")).toBeVisible();
      return;
    }
    await expect(summary).toContainText(/demonstrated/);
    const rows = page.locator(".jd-table tbody tr");
    await expect(rows.first()).toBeVisible();
    const links = page.locator(".jd-cap-link");
    const n = await links.count();
    for (let i = 0; i < n; i++) {
      const href = await links.nth(i).getAttribute("href");
      expect(href).toMatch(/^https:\/\/(github\.com\/karthikdevadoss\/agentic-software-delivery\/|agentic-platform-backend-production\.up\.railway\.app\/|agentic-delivery-customer-app-production\.up\.railway\.app)/);
    }
    // the known-absent sentence in the sample must never be DEMONSTRATED
    const absentRow = rows.filter({ hasText: /vector database/i });
    if (await absentRow.count()) {
      await expect(absentRow.first().locator(".jd-status-pill")).not.toHaveText("DEMONSTRATED");
    }
    const bodyText = await page.locator("#jd-main").innerText();
    expect(bodyText).not.toMatch(/karthik/i);
  });

  test("an empty submission does not trigger a request", async ({ page }) => {
    await page.goto("/jd-match");
    let requestMade = false;
    page.on("request", (req) => { if (req.url().endsWith("/api/jd-match")) requestMade = true; });
    await page.click("#jd-submit");
    await page.waitForTimeout(300);
    expect(requestMade).toBe(false);
  });

  test("phone width: no horizontal overflow and the form is usable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/jd-match");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
    await expect(page.locator("#jd-submit")).toBeVisible();
  });

  test("JD Match is a canonical nav destination on other pages", async ({ page }) => {
    await page.goto("/ask-codebase");
    await expect(page.locator("#top-nav a", { hasText: "JD Match" })).toHaveAttribute("href", "/jd-match");
  });
});
