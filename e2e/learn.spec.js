// Learn journey E2E (Phase 2). Resilient locators (role/text) throughout,
// Playwright's built-in auto-waiting/web-first assertions -- no arbitrary
// sleeps, no brittle DOM-position selectors. Exercises the REAL deployed
// tree (production-scale content), not a fixture.
//
// Escaped-defect coverage (each Owner-found incident, 2026-09-11, now has
// a permanent regression here in addition to its unit/Node-level test):
//   - related-topic navigation context bug (Connection Pooling -> Pool Sizing)
//   - literal "&AMP;" / mojibake on public pages

const { test, expect } = require("@playwright/test");

test.describe("Learn recursive journey", () => {
  test("landing page shows domains, not a flat card dump", async ({ page }) => {
    await page.goto("/learn");
    await expect(page.getByRole("heading", { name: /Learn/i }).first()).toBeVisible();
    await expect(page.getByText("DOMAIN").first()).toBeVisible();
    await expect(page.locator("a.domain-card", { hasText: "System Design" })).toBeVisible();
  });

  test("full drill-down: System Design -> Databases -> Connection Pooling -> Pool Sizing", async ({ page }) => {
    await page.goto("/learn");
    await page.locator("a.domain-card", { hasText: "System Design" }).click();
    await expect(page).toHaveURL(/\/learn\/system-design$/);
    await expect(page.getByRole("heading", { name: "System Design" })).toBeVisible();

    await page.locator("a.topic-card-link", { hasText: "Databases" }).click();
    await expect(page).toHaveURL(/\/learn\/system-design\/databases$/);

    await page.locator("a.topic-card-link", { hasText: "Connection Pooling" }).click();
    await expect(page).toHaveURL(/\/learn\/system-design\/databases\/connection-pooling$/);
    await expect(page.getByRole("heading", { name: "Connection Pooling" })).toBeVisible();
    await expect(page.locator("h4", { hasText: "WHAT" })).toBeVisible();
    await expect(page.locator("h4", { hasText: "HOW" })).toBeVisible();

    // The exact real Owner-found defect: clicking the "Pool Sizing"
    // related-topic chip must not silently lose the journey.
    await page.locator("a.related-chip", { hasText: "Pool Sizing" }).click();
    await expect(page).toHaveURL(/\/learn\/system-design\/performance\/pool-sizing\?from=/);
    // Canonical breadcrumb stays truthful (real hierarchy: Performance, not Databases).
    await expect(page.locator(".breadcrumb")).toContainText("System Design");
    await expect(page.locator(".breadcrumb")).toContainText("Performance");
    // Contextual back-link points to the real origin, not the canonical parent.
    await expect(page.getByRole("link", { name: /Back to Connection Pooling/i })).toBeVisible();
    await expect(page.locator(".referenced-from")).toBeVisible();

    // Browser Back must behave naturally.
    await page.goBack();
    await expect(page).toHaveURL(/\/learn\/system-design\/databases\/connection-pooling$/);
  });

  test("directly visiting Pool Sizing (no context) shows its real canonical parent", async ({ page }) => {
    await page.goto("/learn/system-design/performance/pool-sizing");
    await expect(page.getByRole("link", { name: /Back to Performance/i })).toBeVisible();
    await expect(page.locator(".referenced-from")).toHaveCount(0);
  });

  test("What/Why/How/When and AI/human responsibility topics are reachable", async ({ page }) => {
    await page.goto("/learn/ai-assisted-software-engineering");
    // Exact-text match on the topic name itself -- "Approval" also
    // appears as a substring inside the sibling "Human Role, Approval,
    // and Interruption" deep-dive card, so a substring filter is ambiguous.
    await page.locator(".topic-name", { hasText: /^Human Role/ }).first().click();
    await expect(page.locator(".topic-name", { hasText: /^Approval$/ })).toBeVisible();
    await expect(page.locator(".topic-name", { hasText: /^Interruption$/ })).toBeVisible();
    await expect(page.locator(".topic-name", { hasText: /^Clarification$/ })).toBeVisible();
    await expect(page.locator(".topic-name", { hasText: /^Escalation$/ })).toBeVisible();
  });

  test("unknown topic slug returns a real 404, not a silent 200", async ({ page }) => {
    const response = await page.goto("/learn/this-topic-definitely-does-not-exist-xyz");
    expect(response.status()).toBe(404);
  });

  test("no literal HTML entity or known mojibake anywhere on the rendered page", async ({ page }) => {
    await page.goto("/learn/system-design/databases/connection-pooling");
    await expect(page.locator("h2.topic-title")).toBeVisible(); // wait for client-side render to complete
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("&AMP;");
    expect(bodyText).not.toContain("&amp;amp;");
    expect(bodyText).not.toMatch(/â€|â†’|Ã¢/);
  });

  test("interview preparation content is present on a mature deep topic", async ({ page }) => {
    await page.goto("/learn/ai-assisted-software-engineering/independent-qa-evaluation");
    await expect(page.getByText("INTERVIEW PREPARATION")).toBeVisible();
  });
});
