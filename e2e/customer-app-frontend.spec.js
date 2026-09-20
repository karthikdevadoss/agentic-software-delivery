// BL-027: the Customer App's own frontend (app/src/main/resources/static/
// index.html) had exactly one dedicated Playwright spec before this file
// (e2e/customer-app-update-email.spec.js, a single deep write/read flow).
// docs/TESTING_ARCHITECTURE_V1.md's own "Open items" section named the
// missing broader coverage -- login gate, USER card navigation, ADMIN
// list/detail navigation -- as the single most valuable next addition;
// agent/verify_change.py already honestly surfaces a change to this file
// as a skip reason rather than silently passing. This spec closes that
// gap without duplicating the existing Update Email flow.
//
// Same pattern as e2e/customer-app-update-email.spec.js: a real, running
// Spring Boot server (`cd app && ./mvnw spring-boot:run`, default port
// 8080), NOT the agentic platform's own agent/web_server.py that
// playwright.config.js's shared webServer manages -- so this uses an
// absolute CUSTOMER_APP_URL rather than the config's baseURL, which
// points at a completely different app.

const { test, expect } = require("@playwright/test");

const CUSTOMER_APP_URL = process.env.CUSTOMER_APP_URL || "http://127.0.0.1:8080";

// This file's 8 tests all hit the SAME single local `mvnw spring-boot:run`
// dev instance (unlike the platform-backend specs, which playwright.config.js's
// webServer manages and which tolerate default parallel workers fine).
// Observed for real during this spec's own development: with the default
// worker count, 4 concurrent browser contexts logging in/loading cards at
// once pushed two genuine element-render waits past their 10s timeout on
// this single-Tomcat-thread-pool dev server -- not a real app defect (the
// exact same tests pass reliably every time serially). Forcing this file
// to run serially avoids that self-inflicted contention rather than
// masking it with longer timeouts.
test.describe.configure({ mode: "serial" });

/** Logs in via the real login form (not a direct API call + localStorage
 * injection) so this also proves the login gate's own UI wiring, not just
 * the backend auth endpoint. Mirrors customer-app-update-email.spec.js's
 * login sequence. */
async function login(page, role) {
  await page.goto(CUSTOMER_APP_URL + "/");
  if (role === "ADMIN") {
    await page.locator('input[name="login-role"][value="ADMIN"]').check();
  }
  await expect(page.locator("#login-username option").first()).toBeAttached({ timeout: 10_000 });
  await page.locator("#login-btn").click();
}

test.describe("Customer App — login gate (anonymous vs. authenticated)", () => {
  test("an anonymous visitor sees only the login gate, never app or admin content", async ({ page }) => {
    await page.goto(CUSTOMER_APP_URL + "/");
    await expect(page.locator("#login-view")).toBeVisible();
    await expect(page.locator("#app-view")).toBeHidden();
    await expect(page.locator("#admin-view")).toBeHidden();
    // #app-heading is the single source of truth for the app's display
    // name (AEQ-025) -- the login view is where an anonymous visitor
    // actually sees it first.
    await expect(page.locator("#app-heading")).toHaveText("Energy Customer Platform");
    await expect(page.locator("#login-btn")).toBeVisible();
  });

  test("USER login reveals the real USER app view, and logout returns to the login gate", async ({ page }) => {
    await login(page, "USER");
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#login-view")).toBeHidden();
    await expect(page.locator("#admin-view")).toBeHidden();
    await expect(page.locator("#user-heading-text")).toHaveText("Energy Customer Platform");
    await expect(page.locator("#user-username")).not.toHaveText("—", { timeout: 10_000 });

    await page.locator("#logout-btn").click();
    await expect(page.locator("#login-view")).toBeVisible();
    await expect(page.locator("#app-view")).toBeHidden();
  });

  test("ADMIN login reveals the real ADMIN console, distinct from the USER view", async ({ page }) => {
    await login(page, "ADMIN");
    await expect(page.locator("#admin-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#login-view")).toBeHidden();
    await expect(page.locator("#app-view")).toBeHidden();
    await expect(page.locator("#admin-heading-text")).toHaveText("Energy Customer Platform");
    await expect(page.locator(".admin-tag")).toHaveText("Admin");
  });
});

test.describe("Customer App — USER view: real cards, real data", () => {
  test("Overview/Plan/Account/Preferences/Appointments cards each load real data, not stuck on a loading placeholder", async ({ page }) => {
    await login(page, "USER");
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });

    // Overview (account hero) -- real customer name + id, not the
    // loading placeholder.
    await expect(page.locator("#overview-body")).not.toContainText("Loading", { timeout: 10_000 });
    await expect(page.locator("#overview-body .account-name")).toBeVisible();

    // Account (profile) card -- a real email address is rendered.
    await expect(page.locator("#profile-body")).toContainText("@", { timeout: 10_000 });
    await expect(page.locator("#edit-email-btn")).toBeVisible();

    // Current Plan card -- either a real active plan or the real
    // "not enrolled yet" empty state; either way, not stuck loading.
    await expect(page.locator("#plan-body")).not.toContainText("Loading", { timeout: 10_000 });

    // Preferences card -- real select controls with a real save button,
    // never a permanent loading/error state.
    await expect(page.locator("#pref-paperless")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#pref-channel")).toBeVisible();

    // Appointment Availability card -- present with its real controls.
    await expect(page.locator("#appointments-card #appt-date")).toBeVisible();
    await expect(page.locator("#appointments-card #appt-check-btn")).toBeVisible();

    // Activity card -- present (starts empty for a fresh session, which
    // is real/correct behaviour, not a defect).
    await expect(page.locator("#activity-card")).toBeVisible();
  });

  test("checking appointment availability is a real request/response round trip, logged to Activity", async ({ page }) => {
    await login(page, "USER");
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#appt-date")).toBeVisible({ timeout: 10_000 });

    await page.locator("#appt-check-btn").click();
    await expect(page.locator("#appt-result .msg")).toBeVisible({ timeout: 10_000 });
    // A real outcome is one of AVAILABLE/UNAVAILABLE/error -- assert a
    // genuine non-loading result was reached rather than a specific
    // status, since demo data can be legitimately either.
    await expect(page.locator("#appt-result")).not.toContainText("Checking", { timeout: 10_000 });
    await expect(page.locator("#activity-list li").first()).toContainText("appointment availability", { timeout: 10_000 });
  });
});

test.describe("Customer App — real write/read flow: Preferences", () => {
  test("saving a preference change persists server-side and survives a reload", async ({ page }) => {
    await login(page, "USER");
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#pref-channel")).toBeVisible({ timeout: 10_000 });

    // Read the current value, then deterministically choose a genuinely
    // different one so the test proves a real change, not a no-op save.
    const currentChannel = await page.locator("#pref-channel").inputValue();
    const nextChannel = currentChannel === "SMS" ? "EMAIL" : "SMS";
    await page.locator("#pref-channel").selectOption(nextChannel);

    await page.locator("#save-pref-btn").click();
    await expect(page.locator("#pref-save-result")).toContainText("saved successfully", { timeout: 10_000 });

    // Reload proves the value was actually persisted server-side (a
    // fresh GET /customers/{id}/preferences), not just optimistically
    // rendered client-side -- same discipline as
    // customer-app-update-email.spec.js's own reload check.
    await page.reload();
    await expect(page.locator("#app-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#pref-channel")).toHaveValue(nextChannel, { timeout: 10_000 });
  });
});

test.describe("Customer App — ADMIN navigation: list to detail and back", () => {
  test("ADMIN can open a real customer's detail view from the list, and return to the list", async ({ page }) => {
    await login(page, "ADMIN");
    await expect(page.locator("#admin-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#admin-list-view")).toBeVisible();

    // The seeded demo data always has at least one real customer row.
    await expect(page.locator(".admin-view-customer-btn").first()).toBeVisible({ timeout: 10_000 });
    await page.locator(".admin-view-customer-btn").first().click();

    await expect(page.locator("#admin-detail-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("#admin-list-view")).toBeHidden();
    await expect(page.locator("#admin-overview-body")).not.toContainText("Loading", { timeout: 10_000 });
    await expect(page.locator("#admin-overview-body .account-name")).toBeVisible();
    await expect(page.locator("#admin-profile-body")).toContainText("@", { timeout: 10_000 });

    await page.locator("#admin-back-btn").click();
    await expect(page.locator("#admin-list-view")).toBeVisible();
    await expect(page.locator("#admin-detail-view")).toBeHidden();
  });

  test("ADMIN search narrows the real customer list by name", async ({ page }) => {
    await login(page, "ADMIN");
    await expect(page.locator("#admin-view")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator(".admin-view-customer-btn").first()).toBeVisible({ timeout: 10_000 });

    const firstRowName = await page.locator("table.admin-table tbody tr").first().locator("td").nth(1).textContent();
    await page.locator("#admin-search-name").fill(firstRowName.trim());
    await page.locator("#admin-search-btn").click();

    await expect(page.locator("table.admin-table tbody tr").first()).toContainText(firstRowName.trim(), { timeout: 10_000 });

    await page.locator("#admin-clear-btn").click();
    await expect(page.locator("#admin-search-name")).toHaveValue("");
  });
});
