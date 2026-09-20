// First-ever Playwright spec for the Customer App's own frontend
// (app/src/main/resources/static/index.html) -- a real, running Spring
// Boot server (`cd app && ./mvnw spring-boot:run`, default port 8080),
// NOT the agentic platform's own agent/web_server.py that
// playwright.config.js's shared webServer manages. Uses an absolute URL
// (same pattern as e2e/workbench-real-acceptance.spec.js's
// CUSTOMER_APP_URL constant) rather than the config's baseURL, which
// points at a completely different app.
//
// Real gap this proves fixed (BL-013, 2026-09-20): Update Email
// (PUT /customers/{id}) previously had no uniqueness check at all -- see
// docs/interview-scenarios/14-update-email-uniqueness-gap.md for the
// full story. This spec proves the real browser flow end-to-end: login,
// edit email, save, and the change survives a reload -- the one thing a
// pure API/HTTP integration test (CustomerControllerIntegrationTest)
// cannot prove, since it never touches the actual rendered UI.

const { test, expect } = require("@playwright/test");

const CUSTOMER_APP_URL = process.env.CUSTOMER_APP_URL || "http://127.0.0.1:8080";

test.describe("Customer App — Update Email (real browser flow)", () => {
  test("login, edit email, save, and the new email persists across a reload", async ({ page }) => {
    await page.goto(CUSTOMER_APP_URL + "/");

    // USER role is the default radio selection; the username dropdown is
    // populated asynchronously from /auth/personas -- wait for a real
    // option rather than assuming timing.
    await expect(page.locator("#login-username option").first()).toBeAttached({ timeout: 10_000 });
    // Demo password is pre-filled on purpose (see index.html's own note).
    await page.locator("#login-btn").click();

    // A successful login swaps #login-view out for #app-view (see
    // showApp() in index.html) and boot() loads the profile section.
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#profile-body")).toContainText("@", { timeout: 10_000 });

    const newEmail = `playwright-${Date.now()}@example.com`;

    await page.locator("#edit-email-btn").click();
    await page.locator("#new-email").fill(newEmail);
    await page.locator("#save-email-btn").click();

    await expect(page.locator("#email-save-result")).toContainText("Email updated", { timeout: 10_000 });
    await expect(page.locator("#profile-body")).toContainText(newEmail, { timeout: 10_000 });

    // Reload proves the value was actually persisted server-side, not
    // just optimistically rendered client-side.
    await page.reload();
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#profile-body")).toContainText(newEmail, { timeout: 10_000 });
  });
});
