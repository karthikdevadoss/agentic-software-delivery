// PRIVACY P0 (2026-09-13): /profile must be hidden from public users. It
// was previously a public recruiter-facing resume page (see git history /
// docs/archive/profile_preserved/ for the preserved source), but this
// phase made it non-public per explicit Owner instruction. These tests
// exercise the RENDERED/network behavior (not just source grep) so a
// regression that re-exposes the page is caught immediately.

const { test, expect } = require("@playwright/test");

test.describe("Profile privacy — direct access must not expose content", () => {
  test("direct navigation to /profile returns a real 404, not the resume content", async ({ page }) => {
    const response = await page.goto("/profile");
    expect(response.status()).toBe(404);
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("Karthikeyan Devadoss");
    expect(bodyText).not.toContain("Senior Backend Engineer");
  });

  test("direct navigation to /profile.html (static fallback path) also does not expose content", async ({ page }) => {
    const response = await page.goto("/profile.html");
    expect(response.status()).toBe(404);
  });

  test("no public page links to /profile", async ({ page }) => {
    for (const path of ["/workbench", "/dashboard", "/usage", "/learn"]) {
      await page.goto(path);
      const profileLink = page.locator('a[href="/profile"]');
      await expect(profileLink).toHaveCount(0);
    }
  });
});

test.describe("Workbench — verified run access without submitting", () => {
  // RECRUITER-FACING VERIFIED-RUN P0 (2026-09-13): real defect the Owner
  // found by manual testing — this CTA used to be a bare hard-coded
  // href to one specific old run_id (trainer-4733d1c0), which silently
  // went stale the moment a newer real run completed. These tests drive
  // a real browser through the full recruiter journey: the link's
  // destination must come from the live backend selection (GET
  // /api/workbench/verified-run), not a value baked into the page.

  test("SEE A VERIFIED RUN resolves live to the backend's current selection, not a hard-coded id", async ({ page }) => {
    // Ask the backend directly first — this is the ground truth the
    // rendered link must match, whatever real run happens to be
    // selected at test time (this must never assume a fixed id).
    const apiResp = await page.request.get("/api/workbench/verified-run");
    const apiData = await apiResp.json();
    test.skip(!apiData.available, "no verified run currently available — honest empty state, not a failure of this test");

    await page.goto("/workbench");
    const link = page.getByRole("link", { name: /SEE A VERIFIED RUN/ });
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute("href", `/usage/session/${apiData.run_id}`);

    await link.click();
    await expect(page).toHaveURL(`/usage/session/${apiData.run_id}`);
  });

  test("the verified-run page clearly identifies itself as a real production run with full evidence", async ({ page }) => {
    const apiResp = await page.request.get("/api/workbench/verified-run");
    const apiData = await apiResp.json();
    test.skip(!apiData.available, "no verified run currently available");

    await page.goto(`/usage/session/${apiData.run_id}`);

    // 3. Clearly identifies itself as a verified production run.
    await expect(page.getByRole("heading", { name: "VERIFIED PRODUCTION RUN" })).toBeVisible();
    // 4. Run ID matches the backend's own selection, shown on the page.
    await expect(page.getByText(apiData.run_id)).toBeVisible();
    // 5. Requirement is shown.
    const evidencePanel = page.locator(".verified-run-panel");
    await expect(evidencePanel.getByText(/Requirement:/)).toBeVisible();
    // 6. Deployment/production verification evidence is shown.
    await expect(evidencePanel.getByText("Railway deployment ID")).toBeVisible();
    await expect(evidencePanel.getByText("Observed production value")).toBeVisible();
    await expect(evidencePanel.getByText("Requested effect verified in production")).toBeVisible();
    // 7. Usage is available but clearly distinguished, not the first thing shown.
    const fullUsageLink = evidencePanel.getByRole("link", { name: /VIEW FULL USAGE DETAILS/ });
    await expect(fullUsageLink).toBeVisible();

    // 8. Navigate back cleanly.
    await page.getByRole("link", { name: /Back to Usage/ }).click();
    await expect(page).toHaveURL("/usage");
  });

  test("Workbench renders correctly at mobile viewport (real defect this task fixed: missing viewport meta tag)", async ({ browser }) => {
    const context = await browser.newContext({ ...require("@playwright/test").devices["iPhone 12"] });
    const page = await context.newPage();
    await page.goto("/workbench");
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
    await context.close();
  });
});

test.describe("Public navigation — Learn retired from top nav", () => {
  // Owner instruction (2026-09-13): Learn is no longer promoted as part
  // of the recruiter-facing product. The /learn page itself still
  // exists (not deleted) but must not be linked from Workbench/
  // Dashboard/Usage's top navigation.
  test("Workbench, Dashboard and Usage top nav no longer link to /learn", async ({ page }) => {
    for (const path of ["/workbench", "/dashboard", "/usage"]) {
      await page.goto(path);
      await expect(page.locator(".top-nav a[href=\"/learn\"]")).toHaveCount(0);
    }
  });

  test("/learn itself still loads (source preserved, not deleted)", async ({ page }) => {
    const response = await page.goto("/learn");
    expect(response.status()).toBe(200);
  });
});
