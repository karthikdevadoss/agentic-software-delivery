// Real-browser coverage for the /eval dashboard. Expected values are read from
// the same published JSON the page renders (never hard-coded), so this proves
// the page shows what was published -- and that when the JSON is missing it
// shows no numbers rather than invented ones.
//
// Screenshots: set EVAL_SCREENSHOT_DIR=docs/eval-dashboard to write them.

const { test, expect } = require("@playwright/test");
const path = require("path");

const SUITES = ["retrieval", "routing", "security-routing", "agent-decision", "permission", "self-eval", "injection"];
const fmt = (n) => (typeof n === "number" ? n.toFixed(3) : "n/a");

async function published(request) {
  const results = await (await request.get("/eval-results.json")).json();
  const index = await (await request.get("/eval-history/index.json")).json();
  return { results, index };
}

test.describe("/eval dashboard", () => {
  test("every suite card shows score, threshold, pass/fail, dataset hash, commit and run time from the published JSON", async ({ page, request }) => {
    const errors = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    const { results } = await published(request);
    await page.goto("/eval");
    await expect(page.locator(".suite-card")).toHaveCount(SUITES.length);
    for (const key of SUITES) {
      const s = results.suites.find((x) => x.key === key);
      expect(s, `suite ${key} published`).toBeTruthy();
      const card = page.locator(`.suite-card[data-suite="${key}"]`);
      await expect(card.locator('[data-field="score"]')).toHaveText(fmt(s.score));
      await expect(card.locator('[data-field="threshold"]')).toContainText(fmt(s.threshold));
      await expect(card.locator('[data-field="status"]')).toHaveText(s.passed ? "PASS" : "FAIL");
      await expect(card.locator('[data-field="dataset-hash"]')).toContainText(s.dataset_hash.slice(0, 12));
      await expect(card.locator('[data-field="commit"]')).toContainText(s.commit_sha.slice(0, 7));
      await expect(card.locator('[data-field="run-time"]')).toContainText(s.run_at.slice(0, 10));
    }
    // retrieval carries its second gated metric on the same card
    await expect(page.locator('.suite-card[data-suite="retrieval"] [data-metric="mrr"]')).toBeVisible();
    expect(errors).toEqual([]);
  });

  test("history table has one row per committed record and each suite has a trend line", async ({ page, request }) => {
    const { index } = await published(request);
    expect(index.entries.length).toBeGreaterThanOrEqual(3);
    await page.goto("/eval");
    await expect(page.locator("#history tbody tr")).toHaveCount(index.entries.length);
    for (const key of SUITES) {
      const svg = page.locator(`svg.trend[data-trend="${key}"]`);
      await expect(svg).toBeVisible();
      const pts = index.entries.filter((e) => e.suites.some((s) => s.key === key && typeof s.score === "number")).length;
      await expect(svg).toHaveAttribute("data-points", String(pts));
      await expect(svg.locator("circle")).toHaveCount(pts);
    }
    // newest first; the record link resolves
    const firstFile = await page.locator("#history tbody tr").first().getAttribute("data-history-file");
    expect(firstFile).toBe(index.entries[index.entries.length - 1].file);
    const rec = await request.get(`/eval-history/${firstFile}`);
    expect(rec.ok()).toBeTruthy();
  });

  test("how-to-reproduce box shows the command and the published reproducibility hash", async ({ page, request }) => {
    const { results } = await published(request);
    await page.goto("/eval");
    const box = page.locator("#reproduce");
    await expect(box).toContainText("python eval_runner.py all");
    await expect(box.locator('[data-field="repro-hash"]')).toHaveText(results.reproducibility.inputs_hash);
    await expect(box).toContainText("exits 1 if any threshold is missed");
  });

  test("honesty text is kept", async ({ page }) => {
    await page.goto("/eval");
    await expect(page.getByText("Misses are shown, not hidden")).toBeVisible();
    await expect(page.getByText(/zero tolerance/i).first()).toBeVisible();
    await expect(page.getByText(/CI pipeline is configured to run/)).toBeVisible();
    await expect(page.getByText(/not a fresh run/)).toBeVisible();
    await expect(page.getByText(/Six cases is a small set/)).toBeVisible();
    await expect(page.getByText(/Not covered by the hash/)).toBeVisible();
  });

  test("if eval-results.json fails to load, no numbers are shown", async ({ page }) => {
    await page.route("**/eval-results.json", (r) => r.abort());
    await page.goto("/eval");
    await expect(page.getByText(/No numbers are shown rather than invented ones/)).toBeVisible();
    await expect(page.locator(".suite-card")).toHaveCount(0);
    await expect(page.locator(".m-score")).toHaveCount(0);
  });

  test("if history is missing the cards still render and history says so", async ({ page }) => {
    await page.route("**/eval-history/index.json", (r) => r.fulfill({ status: 404, body: "" }));
    await page.goto("/eval");
    await expect(page.locator(".suite-card")).toHaveCount(SUITES.length);
    await expect(page.locator("#history")).toContainText("No history records were published");
    await expect(page.locator("svg.trend")).toHaveCount(0);
  });

  test("phone width has no horizontal page overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/eval");
    await expect(page.locator(".suite-card")).toHaveCount(SUITES.length);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });

  test("screenshots", async ({ page }) => {
    const dir = process.env.EVAL_SCREENSHOT_DIR;
    test.skip(!dir, "set EVAL_SCREENSHOT_DIR to write screenshots");
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/eval");
    await expect(page.locator("#history tbody tr").first()).toBeVisible();
    await page.screenshot({ path: path.join(dir, "eval-desktop-full.png"), fullPage: true });
    await page.locator("#suites").screenshot({ path: path.join(dir, "eval-suite-cards.png") });
    await page.locator("#history").screenshot({ path: path.join(dir, "eval-history-trends.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/eval");
    await expect(page.locator("#history tbody tr").first()).toBeVisible();
    await page.screenshot({ path: path.join(dir, "eval-mobile-full.png"), fullPage: true });
  });
});
