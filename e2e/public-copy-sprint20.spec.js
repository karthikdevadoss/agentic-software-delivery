// Sprint 20 (2026-10-05): copy a hiring manager reads. Written BEFORE the change.
//
//   BL-167  the home page explains the Standing Interview before the click
//   BL-101  the Workbench says which stages are decided by code and which a
//           model proposes, and gives a plain-English summary line
//   BL-103  the three Triage scenarios are told as one story, and what the
//           model does and does not read is stated
//   BL-106  the Showcase interview grid uses readable labels, not bare tokens
//   BL-157  the Dashboard is scoped as the full inventory, written for engineers
//
// Nothing here changes the Workbench auto behaviour or the Triage approval; two
// of the tests pin that those surfaces still say what they said.

const { test, expect } = require("@playwright/test");

async function bodyText(page, route) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  return page.locator("body").innerText();
}

test.describe("Home explains the Standing Interview (BL-167)", () => {
  test("a first-time visitor can tell what it is before clicking", async ({ page }) => {
    const body = await bodyText(page, "/");
    expect(body).toMatch(/Standing Interview/);
    expect(body).toMatch(/ask .{0,80}(interview )?question/i);
    expect(body).toMatch(/written record|recorded engineering knowledge/i);
    const link = page.locator("main a[href='/standing-interview']");
    await expect(link).toHaveCount(1);
  });

  test("still exactly three proof cards: the explainer is not a fourth card", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".proof .pcard")).toHaveCount(3);
  });
});

test.describe("Workbench stage labels (BL-101)", () => {
  test("the page says which stages code decides and which a model proposes", async ({ page }) => {
    const body = await bodyText(page, "/workbench");
    expect(body).toMatch(/decided by (deterministic )?code/i);
    expect(body).toMatch(/proposed by (a|the) model/i);
    expect(body).toMatch(/AI QA/);
  });

  test("the served script no longer carries the tier wording", async ({ request }) => {
    const resp = await request.get("/workbench.js");
    expect(resp.ok()).toBe(true);
    expect(await resp.text()).not.toMatch(/preview tier/i);
  });

  test("the auto path wording is untouched", async ({ page }) => {
    const body = await bodyText(page, "/workbench");
    expect(body).toMatch(/deterministic policy/i);
    expect(body).toMatch(/automatic|automatically/i);
    expect(body).not.toMatch(/no human approval needed/i);
  });
});

test.describe("Triage is one story (BL-103)", () => {
  const SCENARIOS = [
    ["/triage", "A"],
    ["/triage/scenario-b", "B"],
    ["/triage/scenario-c", "C"],
  ];
  for (const [route, letter] of SCENARIOS) {
    test(`${route} says why there are three scenarios and names the other two`, async ({ page }) => {
      const body = await bodyText(page, route);
      expect(body).toMatch(/why three scenarios/i);
      for (const other of ["A", "B", "C"].filter((x) => x !== letter)) {
        expect(body, `${route} must point at scenario ${other}`).toMatch(new RegExp(`Scenario ${other}`));
      }
    });

    test(`${route} states what the model reads and that the fix still waits for approval`, async ({ page }) => {
      const body = await bodyText(page, route);
      expect(body).toMatch(/never reads a ticket/i);
      expect(body).toMatch(/reproduction/i);
      // The approval step is a later panel, hidden until the run reaches it,
      // so it is checked in the page source rather than the visible text.
      const html = await page.content();
      expect(html).toContain("Human Approval Required");
      await expect(page.locator("#approve-btn")).toHaveCount(1);
    });
  }
});

test.describe("Showcase labels are readable (BL-106)", () => {
  test("the interview grid labels are phrases, not bare uppercase tokens", async ({ page }) => {
    await page.goto("/showcase/senior-java-ai-transformation");
    const dts = page.locator(".sc-how-to-grid dt");
    // The grid lives inside a collapsed story, so count and text, not visibility.
    await expect(dts).not.toHaveCount(0, { timeout: 15_000 });
    const labels = await dts.allTextContents();
    expect(labels.length).toBeGreaterThan(0);
    for (const label of labels) {
      expect(label, `label ${JSON.stringify(label)} is a bare token`).not.toMatch(/^[A-Z]+$/);
      expect(label.trim().split(/\s+/).length).toBeGreaterThanOrEqual(2);
    }
  });
});

test.describe("Dashboard is scoped (BL-157)", () => {
  test("the first screen says what the page is and who it is for", async ({ page }) => {
    const body = await bodyText(page, "/dashboard");
    expect(body).toMatch(/full (evidence )?inventory/i);
    expect(body).toMatch(/written for engineers/i);
    expect(body).toMatch(/start (at|on|with) (the )?Home|Home page/i);
  });
});

// Flow 5 (2026-10-05): the first screen names the three public operations, and
// the Workbench says before any click that a submission can deploy to the demo.
test.describe("First screen operations and the deploy warning", () => {
  test("the home header names the Workbench, Ask the Codebase and Triage", async ({ page }) => {
    await page.goto("/");
    const ops = page.locator("header p.ops");
    await expect(ops).toBeVisible();
    for (const name of ["Workbench", "Ask the Codebase", "Triage"]) {
      await expect(ops).toContainText(name);
    }
  });

  test("the Workbench says a submission can deploy to the demo app before the click", async ({ page }) => {
    await page.goto("/workbench");
    const panel = page.locator("#requirement-panel");
    await expect(panel).toContainText(/deploy\w* to the (live )?demo app/i);
    await expect(panel).toContainText(/no further (click|approval)/i);
  });
});
