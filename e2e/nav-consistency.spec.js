// Public engineering navigation consistency (real production defect,
// found and fixed same-day as this spec: "Role Showcase" was completely
// absent from all 6 core engineering pages -- each page hand-copied its
// own independently-drifting <nav> block. Root cause + architectural fix:
// agent/web/nav.js is now the ONE canonical source every page renders
// from (see docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml AEQ-024).
//
// General invariant this spec proves in a real browser (rendered DOM,
// not raw HTML source -- e2e/link-integrity.spec.js and
// agent/test_nav_frontend.js already cover the static-source layer):
// EVERY recruiter-facing engineering surface must render the SAME
// canonical set of intended public engineering destinations; only
// current-page state (bold/marked) may differ.

const { test, expect } = require("@playwright/test");

// Automation Sprint 4 (Owner decision): Showcase and Usage left the nav, For
// Recruiters joined. The pages stay in PAGES below: reachable directly, and
// still rendering the same nav as everything else.
const CANONICAL_LABELS = ["Home", "Workbench", "Triage", "Ask Codebase", "For Recruiters", "Interviewer Brief"];
const REMOVED_LABELS = ["Showcase", "Usage"];

// Sprint 14: Learn left public navigation entirely (Owner decision), so the
// per-page hiding rule no longer applies to any destination. The set is kept
// empty rather than deleted so the mechanism stays visible to the next reader.
const PAGES_WHERE_LEARN_IS_HIDDEN = new Set();

const PAGES = [
  "/",
  "/workbench",
  "/triage",
  "/triage/scenario-b",
  "/triage/scenario-c",
  "/usage",
  "/ask-codebase",
  "/case-study/durable-agent",
  "/showcase/senior-java-ai-transformation",
  "/recruiters",
  "/interviewer",
];

async function visibleNavLabels(page) {
  const nav = page.locator("#top-nav");
  await expect(nav.locator("a")).not.toHaveCount(0, { timeout: 10_000 });
  return nav.locator("a").allTextContents();
}

test.describe("Public navigation consistency", () => {
  for (const path of PAGES) {
    const learnHidden = PAGES_WHERE_LEARN_IS_HIDDEN.has(path);
    const expectedLabels = learnHidden ? CANONICAL_LABELS.filter((l) => l !== "Learn") : CANONICAL_LABELS;

    test(`${path} renders all ${expectedLabels.length} canonical destinations, including For Recruiters`, async ({ page }) => {
      await page.goto(path);
      const labels = await visibleNavLabels(page);
      for (const expected of expectedLabels) {
        expect(labels, `${path}'s nav must include "${expected}"`).toContain(expected);
      }
      if (learnHidden) {
        expect(labels, `${path}'s nav must NOT include "Learn" (Owner instruction 2026-09-13)`).not.toContain("Learn");
      }
      for (const removed of REMOVED_LABELS) {
        expect(labels, `${path}'s nav must NOT include "${removed}" (Automation Sprint 4)`).not.toContain(removed);
      }
      // A real, clickable, visible link -- not merely text.
      await expect(page.locator("#top-nav a", { hasText: "For Recruiters" }))
        .toHaveAttribute("href", "/recruiters");
      await expect(page.locator("#top-nav a", { hasText: "Interviewer Brief" }))
        .toHaveAttribute("href", "/interviewer");
    });

    test(`${path} nav is identical after a hard reload (direct navigation vs. in-app state)`, async ({ page }) => {
      await page.goto(path);
      const before = (await visibleNavLabels(page)).slice().sort();
      await page.reload();
      const after = (await visibleNavLabels(page)).slice().sort();
      expect(after, `${path}'s nav must not change after a hard reload`).toEqual(before);
    });
  }

  test("real browser journey: Showcase (direct) -> Workbench -> Triage -> Home -> For Recruiters, the nav never changes", async ({ page }) => {
    // Showcase and Usage are no longer in the nav but must stay reachable
    // directly, and render the same nav as every other page.
    await page.goto("/showcase/senior-java-ai-transformation");
    await expect(page.locator("#top-nav a", { hasText: "For Recruiters" })).toBeVisible();
    await expect(page.locator("#top-nav a", { hasText: "Showcase" })).toHaveCount(0);

    await page.getByRole("link", { name: "Workbench", exact: true }).click();
    await expect(page).toHaveURL(/\/workbench$/);
    await expect(page.locator("#top-nav a", { hasText: "For Recruiters" })).toBeVisible();

    await page.getByRole("link", { name: "Triage", exact: true }).click();
    await expect(page).toHaveURL(/\/triage$/);
    await expect(page.locator("#top-nav a", { hasText: "For Recruiters" })).toBeVisible();

    await page.getByRole("link", { name: "Home", exact: true }).click();
    await expect(page).toHaveURL(/\/$/);

    await page.locator("#top-nav").getByRole("link", { name: "For Recruiters", exact: true }).click();
    await expect(page).toHaveURL(/\/recruiters$/);
    await expect(page.locator("#top-nav a strong", { hasText: "For Recruiters" })).toBeVisible();

    await page.locator("#top-nav").getByRole("link", { name: "Interviewer Brief", exact: true }).click();
    await expect(page).toHaveURL(/\/interviewer$/);
    await expect(page.locator("#top-nav a strong", { hasText: "Interviewer Brief" })).toBeVisible();
  });

  test("Showcase and Usage stay reachable by direct link", async ({ request }) => {
    for (const path of ["/showcase/senior-java-ai-transformation", "/usage"]) {
      const r = await request.get(path);
      expect(r.status(), `${path} must still be served`).toBe(200);
    }
  });
});
