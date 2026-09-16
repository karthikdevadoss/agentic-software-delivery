// Real-browser coverage for the Interview Walkthrough section on the
// existing Role Showcase page (/showcase/senior-java-ai-transformation).
// Renders live docs/INTERVIEW_WALKTHROUGH.yaml data (fetched from
// GET /api/interview-walkthrough) -- this spec proves the actual rendered
// DOM, not just that the JSON parses (agent/test_interview_walkthrough_data.py
// already covers the data/link-integrity layer).

const { test, expect } = require("@playwright/test");

const SHOWCASE_PATH = "/showcase/senior-java-ai-transformation";

test.describe("Interview Walkthrough (Role Showcase)", () => {
  test("renders all three paths as tabs, Senior Java active by default", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const tabs = page.locator(".sc-path-tab");
    await expect(tabs).toHaveCount(3);
    await expect(tabs.nth(0)).toHaveText("Senior Java / Backend Engineering");
    await expect(tabs.nth(1)).toHaveText("System Design / Production Engineering");
    await expect(tabs.nth(2)).toHaveText("AI-Assisted Software Engineering");
    await expect(tabs.nth(0)).toHaveClass(/active/);
  });

  test("switching tabs shows a different path's stories without navigation", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    await expect(page.getByText("A Green H2 Suite, Then a Real Production 500 on Postgres")).toBeVisible();

    await page.locator(".sc-path-tab", { hasText: "AI-Assisted Software Engineering" }).click();
    await expect(page.getByText("A Green H2 Suite, Then a Real Production 500 on Postgres")).toBeHidden();
    await expect(page.getByText("Requirement to Verified Production")).toBeVisible();
    // A predicate, not a RegExp built from a string -- the path is a
    // fixed constant here, so no dynamic pattern construction is needed
    // at all (CodeQL js/incomplete-sanitization: the prior
    // .replace(/\//g, "\\/") only escaped slashes, not every regex
    // metacharacter -- not exploitable here since SHOWCASE_PATH is
    // hardcoded, but the fix is to not build a RegExp from a string in
    // the first place, not to escape it more carefully).
    await expect(page).toHaveURL((url) => url.pathname === SHOWCASE_PATH);
  });

  test("a featured story expands to show the full structured breakdown and How to Explain section", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const story = page.locator(".sc-story-featured", { hasText: "A Green H2 Suite" });
    await story.locator("summary").click();
    await expect(story.getByText("Business problem")).toBeVisible();
    await expect(story.getByText("Failure mode")).toBeVisible();
    await expect(story.getByText("How to explain this in an interview")).toBeVisible();
    // Scoped to the <dt> labels specifically -- "VERIFICATION" also
    // legitimately appears as a Title Case field label ("Verification")
    // elsewhere in the same story, and getByText matches case-insensitively.
    const howToTerms = story.locator(".sc-how-to-grid dt");
    await expect(howToTerms).toContainText(["WHY", "WHAT", "HOW", "TRADEOFF", "FAILURE", "VERIFICATION"]);
  });

  test("a featured story shows real 'At 10x scale' system-design content", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const story = page.locator(".sc-story-featured", { hasText: "A Green H2 Suite" });
    await story.locator("summary").click();
    await expect(story.getByText("At 10x scale")).toBeVisible();
    await expect(story.getByText(/full-text search|GIN|trigram/)).toBeVisible();
  });

  test("a Fix commit evidence item is a real, clickable GitHub commit link", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const story = page.locator(".sc-story-featured", { hasText: "A Green H2 Suite" });
    await story.locator("summary").click();
    const commitLink = story.getByRole("link", { name: "Fix commit 9f35f27" });
    await expect(commitLink).toHaveAttribute(
      "href",
      "https://github.com/karthikdevadoss/agentic-software-delivery/commit/9f35f27"
    );
  });

  test("a featured story with a live demo shows a LIVE DEMO badge and a working link", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const story = page.locator(".sc-story-featured", { hasText: "A Green H2 Suite" });
    await expect(story.locator(".sc-live-badge")).toHaveText("LIVE DEMO");
    await story.locator("summary").click();
    const demoLink = story.getByRole("link", { name: /Reproduce this exact historical defect live/ });
    await expect(demoLink).toHaveAttribute(
      "href",
      "https://agentic-platform-backend-production.up.railway.app/triage/scenario-c"
    );
  });

  test("compact (non-featured) stories link to their real full write-up on GitHub", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const compact = page.locator(".sc-story-compact", { hasText: "USER/ADMIN RBAC + Workspace Isolation" });
    await expect(compact).toBeVisible();
    const link = compact.getByRole("link", { name: "Full write-up" });
    await expect(link).toHaveAttribute(
      "href",
      "https://github.com/karthikdevadoss/agentic-software-delivery/blob/master/docs/interview-scenarios/01-rbac-and-workspace-isolation.md"
    );
  });

  test("the deterministic-vs-LLM panel renders with real content", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    await expect(page.getByText("What's deliberately deterministic vs. LLM-driven")).toBeVisible();
    await expect(page.getByText("Human approval boundary")).toBeVisible();
  });

  test("Start here links point to real, registered app routes", async ({ page }) => {
    await page.goto(SHOWCASE_PATH);
    const startLink = page.getByRole("link", { name: /Start here: Senior Java/ });
    await expect(startLink).toHaveAttribute("href", "/dashboard");
    await startLink.click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("Role Showcase page still renders without the walkthrough section blocking anything if the API is unavailable", async ({ page }) => {
    // Regression guard for the try/catch around the walkthrough fetch in
    // showcase.js -- the primary showcase content must never depend on it.
    await page.route("**/api/interview-walkthrough", (route) => route.abort());
    await page.goto(SHOWCASE_PATH);
    await expect(page.locator("#sc-title")).toContainText("Senior Java Backend");
    await expect(page.getByText("START THE LIVE DEMO")).toBeVisible();
  });
});
