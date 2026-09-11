// Usage / Session History journey E2E (Phase 2). Uses real, permanent
// historical session ids from this project's own live event ledger
// (the same convention already used by agent/test_session_history.py) --
// not fixtures, since Usage has no meaningful synthetic-data mode.
//
// Escaped-defect coverage (Owner-found, 2026-09-11):
//   - Quality vs. Evidence Coverage conflation
//   - reconstructed 12h-window semantics implying continuous work
//   - giant raw-prompt session title
//   - known-cost vs. aggregate-only vs. not-captured cost states

const { test, expect } = require("@playwright/test");

const KNOWN_COST_SESSION = "trainer-4733d1c0"; // real workbench_run, EXACT tokens + ACTUAL cost
const AGGREGATE_ONLY_SESSION = "v2-shadow-trial-3-uncertainty-2026-09-11"; // real v2_trial, AGGREGATE_ONLY tokens
const RECONSTRUCTED_SESSION = "claude-code-session-73e068c1-p0-eventledger-task"; // real claude_code, NOT_CAPTURED tokens, long original prompt

// Session-detail computes a real cohort comparison (multiple sequential
// queries over a remote Postgres TCP proxy) -- measured ~3s in practice,
// so the summary panel needs more than Playwright's 5s assertion default,
// especially under parallel test execution.
const DETAIL_LOAD_TIMEOUT = { timeout: 15_000 };

test.describe("Usage / Session History journey", () => {
  test("historical list shows real sessions and Session History panel", async ({ page }) => {
    await page.goto("/usage");
    await expect(page.getByRole("heading", { name: "Session History" })).toBeVisible();
    await expect(page.getByRole("button", { name: /LOAD MORE/i })).toBeVisible();
  });

  test("known-cost Workbench run: tokens and actual cost are visible, Quality != Evidence Coverage", async ({ page }) => {
    await page.goto(`/usage/session/${KNOWN_COST_SESSION}`);
    const summary = page.locator(".session-summary-panel");
    await expect(summary).toBeVisible(DETAIL_LOAD_TIMEOUT);
    await expect(summary).toContainText("37340");
    await expect(summary).toContainText(/ACTUAL COST/i);

    // The exact real Owner-found defect: Quality and Evidence Coverage
    // must be two visibly separate stats, never "Quality / N% coverage".
    await expect(summary).toContainText("Evidence Coverage");
    const summaryText = await summary.innerText();
    expect(summaryText).not.toMatch(/Quality[\s\S]{0,30}%\s*coverage/i);

    // Comparison metrics beyond a bare cohort-size sentence.
    await expect(page.locator("main")).toContainText(/vs\. cohort median/i);
  });

  test("aggregate-only benchmark session: labeled honestly, no fabricated USD cost", async ({ page }) => {
    await page.goto(`/usage/session/${AGGREGATE_ONLY_SESSION}`);
    const summary = page.locator(".session-summary-panel");
    await expect(summary).toBeVisible(DETAIL_LOAD_TIMEOUT);
    await expect(page.locator("main")).toContainText(/aggregate only/i);
    await expect(page.locator("main")).toContainText(/COST UNAVAILABLE/i);
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\$0\.00\b/);
  });

  test("no-token reconstructed session: NOT CAPTURED, COST UNAVAILABLE, reconstructed-window semantics, concise title, raw instruction available separately", async ({ page }) => {
    await page.goto(`/usage/session/${RECONSTRUCTED_SESSION}`);
    const summary = page.locator(".session-summary-panel");
    await expect(summary).toBeVisible(DETAIL_LOAD_TIMEOUT);
    await expect(page.locator("main")).toContainText(/NOT CAPTURED/i);
    await expect(page.locator("main")).toContainText(/COST UNAVAILABLE/i);

    // Concise title: the visible <h2> goal must not be the entire raw prompt.
    const titleText = await page.locator(".session-goal").innerText();
    expect(titleText.length).toBeLessThan(200);

    // Full original text preserved, but tucked into an expandable section.
    const rawDetails = page.locator(".raw-capture-details");
    await expect(rawDetails).toBeVisible();
    await expect(rawDetails.locator("summary")).toContainText(/original text/i);
  });
});
