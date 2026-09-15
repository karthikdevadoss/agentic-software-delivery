// Public/recruiter golden journey (Base Architecture V3 Section 13).
// Complements e2e/link-integrity.spec.js (which only proves rendered
// links resolve): this proves each public page actually renders its own
// real identity and content, not just a 200 status code -- the Owner's
// own experience finding AEQ-022 by hand was a page that returned 200
// everywhere except the one broken link a status check alone would never
// catch. "Do not call browser coverage complete merely because HTTP 200
// is returned" (the directive's own words).

const { test, expect } = require("@playwright/test");

const PUBLIC_PAGES = [
  { path: "/", title: /Workbench/, heading: /Workbench/ },
  { path: "/workbench", title: /Workbench/, heading: /Workbench/ },
  { path: "/dashboard", title: /Dashboard/, heading: /Evidence Dashboard/ },
  { path: "/usage", title: /Usage/, heading: /Usage/ },
  { path: "/triage", title: /Incident Triage Lab/, heading: /Incident Triage Lab/ },
  { path: "/triage/scenario-b", title: /Incident Triage Lab \(Scenario B\)/, heading: /Incident Triage Lab/ },
  { path: "/triage/scenario-c", title: /Incident Triage Lab \(Scenario C\)/, heading: /Incident Triage Lab/ },
  { path: "/learn", title: /Learn/, heading: /Learn/ },
];

test.describe("Public golden journey — page identity and real content", () => {
  for (const { path, title, heading } of PUBLIC_PAGES) {
    test(`${path} has the correct page identity and renders real content`, async ({ page }) => {
      await page.goto(path);
      await expect(page).toHaveTitle(title);
      await expect(page.locator("h1").first()).toContainText(heading);
    });
  }

  test("/showcase/senior-java-ai-transformation resolves its real title, never stays stuck on the loading placeholder", async ({ page }) => {
    // The raw server-rendered HTML shows a "loading..." placeholder
    // (agent/web/showcase.html) until agent/web/showcase.js's async
    // fetch of /api/showcase/<slug> completes and replaces it -- a real
    // browser proves the JS-populated title actually arrives, which a
    // plain HTTP status/HTML-source check (like link-integrity.spec.js)
    // cannot.
    await page.goto("/showcase/senior-java-ai-transformation");
    await expect(page.locator("#sc-title")).not.toContainText("loading", { timeout: 10_000 });
    await expect(page.locator("#sc-title")).toContainText("Senior Java Backend", { timeout: 10_000 });
  });

  test("Showcase's canonical navigation CTAs (Explore The Platform Directly) are real and visible", async ({ page }) => {
    await page.goto("/showcase/senior-java-ai-transformation");
    await expect(page.getByRole("link", { name: "OPEN CUSTOMER APP" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("link", { name: "OPEN WORKBENCH" })).toBeVisible({ timeout: 10_000 });
  });

  test("Workbench's primary requirement-submission CTA is present (the actual recruiter-facing action, not just the page shell)", async ({ page }) => {
    await page.goto("/workbench");
    await expect(page.getByRole("textbox").first()).toBeVisible();
  });
});
