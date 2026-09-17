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

const CANONICAL_LABELS = ["Workbench", "Triage", "Dashboard", "Usage", "Learn", "Role Showcase"];

// AEQ-027 (2026-09-17): Learn is deliberately hidden on these 3 pages
// only, per the real, dated Owner instruction (2026-09-13, see
// e2e/profile.spec.js) that predates AEQ-024's nav unification and was
// never reconciled with it -- see agent/web/nav.js's `hiddenOn`.
const PAGES_WHERE_LEARN_IS_HIDDEN = new Set(["/workbench", "/dashboard", "/usage"]);

const PAGES = [
  "/workbench",
  "/triage",
  "/triage/scenario-b",
  "/triage/scenario-c",
  "/dashboard",
  "/usage",
  "/learn",
  "/showcase/senior-java-ai-transformation",
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

    test(`${path} renders all ${expectedLabels.length} canonical destinations, including Role Showcase`, async ({ page }) => {
      await page.goto(path);
      const labels = await visibleNavLabels(page);
      for (const expected of expectedLabels) {
        expect(labels, `${path}'s nav must include "${expected}"`).toContain(expected);
      }
      if (learnHidden) {
        expect(labels, `${path}'s nav must NOT include "Learn" (Owner instruction 2026-09-13)`).not.toContain("Learn");
      }
      // The actual originally-reported symptom: Role Showcase specifically
      // must be a real, clickable, visible link -- not merely text.
      await expect(page.locator("#top-nav a", { hasText: "Role Showcase" }))
        .toHaveAttribute("href", "/showcase/senior-java-ai-transformation");
    });

    test(`${path} nav is identical after a hard reload (direct navigation vs. in-app state)`, async ({ page }) => {
      await page.goto(path);
      const before = (await visibleNavLabels(page)).slice().sort();
      await page.reload();
      const after = (await visibleNavLabels(page)).slice().sort();
      expect(after, `${path}'s nav must not change after a hard reload`).toEqual(before);
    });
  }

  test("real browser journey: Role Showcase -> Workbench -> Usage -> Triage -> Dashboard -> Role Showcase, Role Showcase never disappears", async ({ page }) => {
    await page.goto("/showcase/senior-java-ai-transformation");
    // Current page is still a real <a> (bolded via <strong>), matching the
    // original hardcoded pages' own design (e.g. <a href="/workbench">
    // <strong>Workbench</strong></a>) -- nav.js preserves this, it doesn't
    // remove the self-link.
    await expect(page.locator("#top-nav a", { hasText: "Role Showcase" })).toBeVisible();
    await expect(page.locator("#top-nav a strong", { hasText: "Role Showcase" })).toBeVisible();

    await page.getByRole("link", { name: "Workbench", exact: true }).click();
    await expect(page).toHaveURL(/\/workbench$/);
    await expect(page.locator("#top-nav a", { hasText: "Role Showcase" })).toBeVisible();

    await page.getByRole("link", { name: "Usage", exact: true }).click();
    await expect(page).toHaveURL(/\/usage$/);
    await expect(page.locator("#top-nav a", { hasText: "Role Showcase" })).toBeVisible();

    await page.getByRole("link", { name: "Triage", exact: true }).click();
    await expect(page).toHaveURL(/\/triage$/);
    await expect(page.locator("#top-nav a", { hasText: "Role Showcase" })).toBeVisible();

    await page.getByRole("link", { name: "Dashboard", exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.locator("#top-nav a", { hasText: "Role Showcase" })).toBeVisible();

    await page.getByRole("link", { name: "Role Showcase", exact: true }).click();
    await expect(page).toHaveURL(/\/showcase\/senior-java-ai-transformation$/);
  });
});
