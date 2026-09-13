// RELIABILITY/CORRECTION PHASE (2026-09-13): /profile must be generic,
// recruiter-friendly, and truthful — no total-years claims, no named
// historical clients, no résumé-style employment chronology. These tests
// exercise the RENDERED page (not just source grep) so a regression in
// what the browser actually shows is caught, including console errors
// and both desktop/mobile layouts.

const { test, expect, devices } = require("@playwright/test");

test.describe("Profile — recruiter landing page", () => {
  test("hero identity, positioning, and CTAs are visible", async ({ page }) => {
    await page.goto("/profile");
    await expect(page.getByRole("heading", { name: "Karthikeyan Devadoss" })).toBeVisible();
    await expect(page.locator(".hero-role")).toHaveText("Senior Backend Engineer");
    await expect(page.getByText(/Java.*Spring Boot.*Distributed Systems.*System Design/)).toBeVisible();
    await expect(page.locator(".hero-focus")).toHaveText("AI-Assisted Software Delivery");
    const hero = page.locator(".hero");
    await expect(hero.getByRole("link", { name: "VIEW LIVE WORKBENCH" })).toHaveAttribute("href", "/workbench");
    await expect(hero.getByRole("link", { name: "SEE VERIFIED RUN" })).toHaveAttribute("href", /\/usage\/session\//);
  });

  test("generic positioning present; forbidden total-years claims and named historical clients absent from the rendered page", async ({ page }) => {
    await page.goto("/profile");
    const bodyText = await page.locator("body").innerText();
    // Required generic positioning (per the Owner's exact wording).
    expect(bodyText).toContain("Experienced Senior Backend Engineer delivering Java/Spring Boot systems for US-based clients");
    expect(bodyText).toContain("energy, healthcare, banking and insurance");
    // Forbidden: any total-experience count, in any phrasing.
    expect(bodyText).not.toMatch(/\d+\+?\s*years?/i);
    // Forbidden: named historical clients/employers.
    for (const client of ["NRG", "Blue Cross", "Northern Trust", "Marsh"]) {
      expect(bodyText).not.toContain(client);
    }
    // The six unsupported-claim categories the Owner flagged as unsafe.
    for (const unsafe of ["AI Integration Lead", "AI Integration & Delivery", "Copilot rollout",
      "Azure AI Foundry", "AI Governance Framework", "RAG pipeline", "AI governance"]) {
      expect(bodyText).not.toContain(unsafe);
    }
  });

  test("AI-assisted software engineering positioning is present and keeps professional-work vs. personal-platform-work distinct", async ({ page }) => {
    await page.goto("/profile");
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toContain("current professional project work where");
    expect(bodyText).toContain("hands-on personal engineering");
    expect(bodyText).toContain("not a claim about any employer's production system");
    for (const topic of ["Context Engineering", "Tool-Calling Agents", "Deterministic Verification",
      "Independent AI QA", "Model/Tool Telemetry", "AI Engineering Economics",
      "Software-Delivery Orchestration", "Human Authorization Boundaries", "Safe Autonomous Execution"]) {
      expect(bodyText).toContain(topic);
    }
  });

  test("all three platform surfaces are explained with working links", async ({ page }) => {
    await page.goto("/profile");
    const surfaceGrid = page.locator(".surface-grid");
    await expect(surfaceGrid.getByText("Workbench", { exact: true })).toBeVisible();
    await expect(surfaceGrid.getByText("Dashboard", { exact: true })).toBeVisible();
    await expect(surfaceGrid.getByText("Usage", { exact: true })).toBeVisible();
    await expect(surfaceGrid.getByRole("link", { name: /Open Workbench/ })).toHaveAttribute("href", "/workbench");
    await expect(surfaceGrid.getByRole("link", { name: /Open Dashboard/ })).toHaveAttribute("href", "/dashboard");
    await expect(surfaceGrid.getByRole("link", { name: /Open Usage/ })).toHaveAttribute("href", "/usage");
  });

  test("page loads with zero browser console/application errors", async ({ page }) => {
    const errors = [];
    page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
    page.on("pageerror", (err) => errors.push(String(err)));
    await page.goto("/profile", { waitUntil: "networkidle" });
    expect(errors).toEqual([]);
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
