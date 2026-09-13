// RELIABILITY/CORRECTION PHASE (2026-09-13) — Layer 9 REAL BROWSER E2E.
//
// This spec exercises the ACTUAL public Workbench journey end to end,
// FOR REAL: open Workbench -> submit a real supported requirement ->
// observe status progression -> wait for genuine COMPLETED -> fetch the
// real production Customer App and confirm the exact requested change ->
// reset -> confirm canonical state is genuinely restored.
//
// This is deliberately NOT part of the default `npx playwright test` run
// — it performs a REAL git clone + commit + push attempt + Railway
// deploy + a second deploy for reset against REAL production every time
// it runs (multiple real Railway builds, each taking 1-5+ minutes). Per
// this task's own explicit cost/token-economics guidance ("a smaller
// representative subset performs real production deployments" rather
// than running the full expensive matrix on every regular test pass),
// this file is skipped unless explicitly requested.
//
// Run deliberately (against the real live production URL):
//   RUN_REAL_ACCEPTANCE=1 PLAYWRIGHT_BASE_URL=https://agentic-platform-backend-production.up.railway.app npx playwright test e2e/workbench-real-acceptance.spec.js --timeout=900000
//
// Or against a local dev server pointed at real production Railway (the
// isolated clone/deploy always targets the real Customer App regardless
// of where the platform-backend itself is running):
//   RUN_REAL_ACCEPTANCE=1 npx playwright test e2e/workbench-real-acceptance.spec.js --timeout=900000

const { test, expect } = require("@playwright/test");

test.skip(!process.env.RUN_REAL_ACCEPTANCE, "Real production acceptance run — set RUN_REAL_ACCEPTANCE=1 to run deliberately (see file header)");

const CUSTOMER_APP_URL = "https://agentic-delivery-customer-app-production.up.railway.app/";

async function fetchCustomerAppFooter(request) {
  const resp = await request.get(`${CUSTOMER_APP_URL}?cb=${Date.now()}`);
  const html = await resp.text();
  const match = html.match(/<footer class="app-footer">([^<]*)<\/footer>/);
  return match ? match[1] : null;
}

test.describe("Workbench — REAL production acceptance journey (Layer 9)", () => {
  test("submit a real supported requirement, verify production, then reset", async ({ page, request }) => {
    test.setTimeout(15 * 60 * 1000);

    const uniqueValue = `Real acceptance run ${new Date().toISOString()}`;
    const requirement = `Change the footer text to "${uniqueValue}"`;

    // 1. Open Workbench.
    await page.goto("/workbench");
    await expect(page.getByRole("heading", { name: /Workbench/ })).toBeVisible();

    // 2. Enter the real supported requirement.
    await page.locator("#requirement-input").fill(requirement);

    // 3. Submit.
    await page.locator("#submit-btn").click();

    // 4. Observe status progression — the run-status panel appears and a
    // real run ID is assigned. Real UI finding from this task's first
    // live run: the panel becomes visible slightly BEFORE #rs-runid is
    // populated (the panel is shown, then the POST /api/trainer/runs
    // response arrives and sets the text) — wait for the actual value,
    // don't assume it's synchronously present the instant the panel
    // appears.
    await expect(page.locator("#run-status-panel")).toBeVisible({ timeout: 15000 });
    await expect(page.locator("#rs-runid")).toHaveText(/^trainer-/, { timeout: 10000 });
    const runId = await page.locator("#rs-runid").textContent();

    // 5. Wait for genuine terminal completion (COMPLETED, not a fabricated
    // intermediate state) — polling the real backend directly as the
    // authoritative source, independent of the SSE/UI rendering.
    let finalStatus = null;
    for (let i = 0; i < 90; i++) {
      const runResp = await request.get(`/api/runs/${runId}`);
      const runBody = await runResp.json();
      if (["COMPLETED", "FAILED", "NO_CHANGE_NEEDED", "DEPLOYMENT_STATUS_UNKNOWN"].includes(runBody.status)) {
        finalStatus = runBody.status;
        break;
      }
      await page.waitForTimeout(10000);
    }
    expect(finalStatus).toBe("COMPLETED");

    // 6. Verify evidence shown in the UI itself.
    await expect(page.locator("#result-banner")).toContainText(/COMPLETED|VERIFIED/i);

    // 7 & 8. Independently fetch the REAL production Customer App and
    // confirm the exact requested change — never trust the run's own
    // self-report as sufficient.
    const liveFooter = await fetchCustomerAppFooter(request);
    expect(liveFooter).toBe(uniqueValue);

    // 9. Reset.
    await page.locator("#reset-demo-btn").click();
    let resetStatus = null;
    for (let i = 0; i < 60; i++) {
      const statusResp = await request.get("/api/trainer/reset");
      const statusBody = await statusResp.json();
      if (statusBody.status !== "running") {
        resetStatus = statusBody.status;
        break;
      }
      await page.waitForTimeout(10000);
    }
    expect(resetStatus).toBe("completed");

    // 10. Independently confirm canonical state is genuinely restored.
    const restoredFooter = await fetchCustomerAppFooter(request);
    expect(restoredFooter).toBe("Powered by Agentic Delivery");
  });
});
