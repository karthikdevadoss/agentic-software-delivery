// PDF book E2E (Phase 2, Section F): the Download Complete Book control
// must be present and its endpoint must return a real, non-empty PDF.

const { test, expect } = require("@playwright/test");

// Sprint 14: /learn and /jd-match are no longer public routes -- they 404 on
// the public deployment and are registered only when PRIVATE_SURFACES_ENABLED
// is set (agent/web_server.py). This spec is preserved, not deleted: it still
// runs whenever the private surface is enabled.
const PRIVATE_SURFACES = ["1", "true", "yes", "on"].includes(
  String(process.env.PRIVATE_SURFACES_ENABLED || "").toLowerCase());
test.skip(!PRIVATE_SURFACES, "private surface: set PRIVATE_SURFACES_ENABLED to run");


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
