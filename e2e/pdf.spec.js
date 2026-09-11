// PDF book E2E (Phase 2, Section F): the Download Complete Book control
// must be present and its endpoint must return a real, non-empty PDF.

const { test, expect } = require("@playwright/test");

test.describe("Learn PDF book", () => {
  test("Download Complete Book control is visible on the Learn landing page", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.getByRole("link", { name: /DOWNLOAD COMPLETE BOOK/i })).toBeVisible();
  });

  test("the PDF endpoint returns an actual, non-empty PDF", async ({ request }) => {
    const response = await request.get("/api/learn/book.pdf");
    expect(response.ok()).toBeTruthy();
    expect(response.headers()["content-type"]).toContain("application/pdf");
    const body = await response.body();
    expect(body.length).toBeGreaterThan(1000);
    expect(body.subarray(0, 5).toString("latin1")).toBe("%PDF-");
  });
});
