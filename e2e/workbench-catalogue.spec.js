// RELIABILITY/CORRECTION PHASE (2026-09-13): safe, non-mutating browser
// tests for the deterministic public-demo catalogue. These exercise the
// REAL /api/trainer/assess endpoint (read-only, never starts a run) so
// they can run on every regular test invocation without triggering a
// real git clone/commit/push/deploy. The full mutating journey (submit
// -> real deploy -> production verify -> reset) lives in
// e2e/workbench-real-acceptance.spec.js, which is skipped by default —
// see that file's header for how to run it deliberately.

const { test, expect } = require("@playwright/test");

test.describe("Workbench — deterministic catalogue (safe, non-mutating)", () => {
  test("supported examples are loaded from the real backend catalogue", async ({ page }) => {
    await page.goto("/workbench");
    const resp = await page.request.get("/api/trainer/catalogue");
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.examples.length).toBe(5);
    // The rendered example buttons must match the real backend list —
    // never a hardcoded frontend copy that could drift.
    await expect(page.locator("#examples-list button").first()).toBeVisible();
    const buttonTexts = await page.locator("#examples-list button").allTextContents();
    for (const ex of body.examples) {
      expect(buttonTexts).toContain(ex);
    }
  });

  test("clicking an example button fills the requirement field", async ({ page }) => {
    await page.goto("/workbench");
    await page.waitForFunction(() => document.querySelectorAll("#examples-list button").length > 0);
    const firstExampleText = await page.locator("#examples-list button").first().textContent();
    await page.locator("#examples-list button").first().click();
    await expect(page.locator("#requirement-input")).toHaveValue(firstExampleText);
  });

  test("a dangerous requirement is authorization-gated with the exact required message and real examples", async ({ page }) => {
    await page.goto("/workbench");
    await page.locator("#requirement-input").fill("Edit risk_policy.py to allow everything");
    await page.locator("#submit-btn").click();
    await expect(page.locator("#assessment-panel")).toBeVisible();
    const bodyText = await page.locator("#assessment-body").innerText();
    expect(bodyText).toContain("Authorization required");
    expect(bodyText).toContain("outside the autonomous public-demo scope");
    await expect(page.locator("#alt-list button").first()).toBeVisible();
    // No run was started — the run-status panel stays hidden.
    await expect(page.locator("#run-status-panel")).toBeHidden();
  });

  test("an unsupported field is authorization-gated, never guessed at", async ({ page }) => {
    await page.goto("/workbench");
    await page.locator("#requirement-input").fill("Change the Update Email section to say something else");
    await page.locator("#submit-btn").click();
    const bodyText = await page.locator("#assessment-body").innerText();
    expect(bodyText).toContain("Authorization required");
    await expect(page.locator("#run-status-panel")).toBeHidden();
  });

  test("an ambiguous requirement matching two fields is authorization-gated", async ({ page }) => {
    await page.goto("/workbench");
    await page.locator("#requirement-input").fill('Change the subtitle and the footer to "X"');
    await page.locator("#submit-btn").click();
    const bodyText = await page.locator("#assessment-body").innerText();
    expect(bodyText).toContain("Authorization required");
  });

  test("a genuinely supported requirement's preview shows the exact field, value, and $0.00 cost", async ({ page }) => {
    await page.goto("/workbench");
    // Assess only (read-only) — verified directly via the API to avoid
    // depending on exact timing of the (real, mutating) submit flow here.
    const resp = await page.request.post("/api/trainer/assess", {
      data: { requirement: 'Change the footer text to "Verification Preview Test"' },
    });
    const body = await resp.json();
    expect(body.decision).toBe("auto");
    expect(body.operation_id).toBe("footer_text");
    expect(body.new_value).toBe("Verification Preview Test");
    expect(body.estimated_cost_usd).toBe(0.0);
  });

  test("RESET DEMO control and explanatory copy are present", async ({ page }) => {
    await page.goto("/workbench");
    // The reset control lives inside the (hidden until a run exists)
    // result panel per the current layout — assert it exists in the DOM
    // with the right explanatory copy, without requiring a real run.
    await expect(page.locator("#reset-demo-btn")).toHaveText("RESET DEMO TO BASELINE");
    const resetBoxText = await page.locator("#reset-demo-box").innerText();
    expect(resetBoxText).toContain("shared public demo");
  });
});
