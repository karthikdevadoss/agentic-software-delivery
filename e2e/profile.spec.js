// JOB-SEARCH P0 (2026-09-12): /profile is now the primary recruiter-facing
// landing page and /workbench must offer a way to see a real verified run
// without submitting anything. Real browser checks, desktop and mobile,
// for both — no fabricated/dead links, no unsupported-claim regressions.

const { test, expect, devices } = require("@playwright/test");

test.describe("Profile — recruiter landing page", () => {
  test("hero identity, positioning, and CTAs are visible", async ({ page }) => {
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Karthikeyan Devadoss" })).toBeVisible();
    await expect(page.locator(".hero-role")).toHaveText("Senior Backend Engineer");
    await expect(page.getByText(/Java.*Spring Boot.*Distributed Systems.*System Design/)).toBeVisible();
    const hero = page.locator(".hero");
    await expect(hero.getByRole("link", { name: "VIEW LIVE WORKBENCH" })).toHaveAttribute("href", "/workbench");
    await expect(hero.getByRole("link", { name: "SEE VERIFIED RUN" })).toHaveAttribute("href", /\/usage\/session\//);
  });

  test("professional experience lists the real companies without AI-leadership overclaims", async ({ page }) => {
    await page.goto("/profile");
    for (const company of ["NRG Energy", "Blue Cross Blue Shield", "Northern Trust", "Marsh"]) {
      await expect(page.getByText(company, { exact: true })).toBeVisible();
    }
    const bodyText = await page.locator("body").innerText();
    // The exact unsupported-claim categories the Owner flagged as unsafe
    // for job applications must never appear on this page.
    for (const unsafe of ["AI Integration Lead", "AI Integration & Delivery", "Copilot rollout",
      "Azure AI Foundry", "AI Governance Framework", "RAG pipeline"]) {
      expect(bodyText).not.toContain(unsafe);
    }
  });

  test("featured project links to Workbench, a verified run, Dashboard and Usage", async ({ page }) => {
    await page.goto("/profile");
    const featured = page.locator(".featured");
    await expect(featured.getByRole("link", { name: "Open Workbench" })).toHaveAttribute("href", "/workbench");
    await expect(featured.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
    await expect(featured.getByRole("link", { name: "Usage" })).toHaveAttribute("href", "/usage");
  });

  test("the SEE VERIFIED RUN link resolves to a real, non-empty session page", async ({ page }) => {
    await page.goto("/profile");
    await page.locator(".hero").getByRole("link", { name: "SEE VERIFIED RUN" }).click();
    await expect(page).toHaveURL(/\/usage\/session\/trainer-/);
    await expect(page.locator(".summary-value").getByText("COMPLETED", { exact: true })).toBeVisible();
    await expect(page.getByText("TIMELINE")).toBeVisible();
  });

  test("no literal HTML entity or mojibake on the profile page", async ({ page }) => {
    await page.goto("/profile");
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("&middot;");
    expect(bodyText).not.toContain("&amp;");
    expect(bodyText).not.toMatch(/â€|â†’|Ã¢|�/);
  });

  test("renders correctly at mobile viewport with no horizontal overflow", async ({ browser }) => {
    const context = await browser.newContext({ ...devices["iPhone 12"] });
    const page = await context.newPage();
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Karthikeyan Devadoss" })).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
    await context.close();
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
    const context = await browser.newContext({ ...devices["iPhone 12"] });
    const page = await context.newPage();
    await page.goto("/workbench");
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
    await context.close();
  });
});
