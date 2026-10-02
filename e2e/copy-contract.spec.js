// Sprint 17, BL-C1 / BL-C9. Deterministic coverage for the public claims that
// would cost a job if they were wrong.
//
// WHY A COPY TEST IS NOT A SILLY IDEA HERE. These are not style preferences.
// Each assertion below protects a statement whose failure mode is a recruiter or
// a hiring manager drawing a false conclusion about what this system does or
// whose work it is:
//
//   * that the AI platform is Karthik's own system and not an employer's product
//   * that no language model in this system grants itself write permission
//   * that a bounded auto-approved path genuinely exists, so the site does not
//     overclaim human oversight either
//   * that the candidate is named on the surface that speaks in his voice
//   * that the telemetry page's figures are this platform's own spend
//
// WHAT THESE ASSERT, AND WHAT THEY DELIBERATELY DO NOT. They check MEANING, via
// the presence or absence of load-bearing phrases -- never exact wording. A test
// pinned to a whole sentence fails on every edit and gets deleted within two
// sprints, which is worse than no test. So: the words that carry the claim are
// required, and the words that would carry a FALSE claim are forbidden.
//
// The full source audit these are derived from is docs/SPRINT17_APPROVAL_STORY.md,
// with file and line references for every statement.

const { test, expect } = require("@playwright/test");

async function text(page, route) {
  await page.goto(route, { waitUntil: "domcontentloaded" });
  try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch { /* ignore */ }
  // Some pages render their body from JS; give the fetch a beat to land.
  await page.waitForTimeout(600);
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

test.describe("Home: whose platform this is", () => {
  test("says the AI platform is his own system, not an employer's product", async ({ page }) => {
    const body = await text(page, "/");
    // The real risk: a reader concluding Karthik is showing an NRG Energy
    // product, which would be both false and a professional problem.
    expect(
      /my own system, not an NRG product/i.test(body),
      "Home must state that the AI platform is his own system and not an NRG " +
      "product. A recruiter who reads NRG Energy and an AI platform on one page " +
      "and is not told which is which will guess, and the wrong guess is worse " +
      "than either truth."
    ).toBe(true);
  });

  test("names the candidate and the hybrid role", async ({ page }) => {
    const body = await text(page, "/");
    expect(body).toContain("Karthikeyan Devadoss");
    expect(/Senior Backend \/ Software Engineer/i.test(body)).toBe(true);
    // The locked positioning: enterprise backend AND agentic AI, not a pivot
    // away from Java and not an ML-research claim.
    expect(/Java/i.test(body)).toBe(true);
    expect(/Agentic AI/i.test(body)).toBe(true);
  });

  test("surfaces the enterprise employers without implying they own the platform", async ({ page }) => {
    const body = await text(page, "/");
    for (const employer of ["NRG Energy", "Blue Cross Blue Shield Association", "Marsh"]) {
      expect(body, `${employer} should be visible as backend credibility`).toContain(employer);
    }
    expect(
      /(NRG|Blue Cross|Marsh)('s)? (AI|Agentic) platform/i.test(body),
      "no phrasing may attribute this Agentic AI platform to an employer"
    ).toBe(false);
  });

  test("keeps PostgreSQL in the skills", async ({ page }) => {
    // Locked by the brief. It was at risk during the Sprint 16 copy passes and
    // is a real, named part of the stack.
    const body = await text(page, "/");
    expect(/PostgreSQL/i.test(body)).toBe(true);
  });
});

test.describe("The one approval story, told the same way on both pages", () => {
  // The real invariant, read out of risk_policy.py, write_tools.py,
  // demo_catalogue.py and web_server.py: no MODEL authorizes anything;
  // DETERMINISTIC POLICY authorizes a narrow pre-declared band. Both halves have
  // to survive, because dropping either one produces a different false claim.

  test("Home still says the agent cannot approve its own writes", async ({ page }) => {
    const body = await text(page, "/");
    expect(/cannot approve its own writes/i.test(body)).toBe(true);
  });

  test("Home names what holds the authority instead of only what does not", async ({ page }) => {
    const body = await text(page, "/");
    expect(
      /(deterministic|denylist|whitelist|contract|plain Python)/i.test(body),
      "the claim has to be checkable: say WHAT decides, not only that the model does not"
    ).toBe(true);
  });

  test("Workbench never implies the model grants itself permission", async ({ page }) => {
    const body = await text(page, "/workbench");
    // The exact phrase that was there before Sprint 17 and the readings it
    // invited. "no human approval needed" on its own, with nothing saying what
    // DID approve it, reads as the model deciding.
    const forbidden = [
      /no human approval needed/i,
      /the (model|agent|AI|LLM) (decides|determines|judges) (whether|if) it is safe/i,
      /the (model|agent|AI|LLM) approves/i,
      /self-approv/i,
    ];
    for (const pattern of forbidden) {
      expect(
        pattern.test(body),
        `Workbench copy matched ${pattern}, which implies the model authorized ` +
        `itself. It does not: agent/risk_policy.py and agent/demo_catalogue.py ` +
        `import no model client. See docs/SPRINT17_APPROVAL_STORY.md.`
      ).toBe(false);
    }
  });

  test("Workbench says deterministic policy is what authorizes", async ({ page }) => {
    const body = await text(page, "/workbench");
    expect(
      /deterministic/i.test(body),
      "the truthful claim -- deterministic policy, not the model -- must be present"
    ).toBe(true);
  });

  test("Workbench does not overclaim human oversight either", async ({ page }) => {
    // The opposite error, and just as wrong: the bounded auto path is real, and
    // claiming every change needs a human would be a false modesty that a
    // technical interviewer would catch in one question.
    const body = await text(page, "/workbench");
    expect(
      /every (change|write|requirement) requires (a )?human/i.test(body),
      "a bounded auto-approved path genuinely exists (agent/web_server.py's " +
      "_run_trainer_thread commits, pushes and deploys with no approval event). " +
      "Claiming otherwise is also a false claim."
    ).toBe(false);
    expect(
      /automatic|automatically/i.test(body),
      "the auto path is real and should be stated"
    ).toBe(true);
  });

  test('Workbench no longer claims a "preview tier" the code does not define', async ({ page }) => {
    const body = await text(page, "/workbench");
    expect(
      /preview tier/i.test(body),
      "nothing in the code defines a tier system, so a reader asking 'what are " +
      "the other tiers?' gets no answer. See the open note in " +
      "docs/OWNER_DECISIONS_PENDING.md."
    ).toBe(false);
  });
});

test.describe("Environment label", () => {
  test("Workbench names the target environment truthfully and not as NRG", async ({ page }) => {
    const body = await text(page, "/workbench");
    expect(
      /Live demo app \(not NRG\)/i.test(body),
      "the target app's environment label must say what it is. It was " +
      '"Production Demo", two words that contradict each other.'
    ).toBe(true);
  });
});

test.describe("Standing Interview identity", () => {
  test("the candidate is named on the page that speaks in his voice", async ({ page }) => {
    const body = await text(page, "/standing-interview");
    expect(
      body,
      "a recruiter could open the one surface that answers interview questions " +
      "in the first person and never learn whose interview it was"
    ).toContain("Karthikeyan Devadoss");
  });

  test("it states that answers are grounded and that it admits missing evidence", async ({ page }) => {
    const body = await text(page, "/standing-interview");
    expect(/recorded engineering knowledge|written record/i.test(body)).toBe(true);
    expect(
      /(says so|tells you|say so).{0,60}(instead|rather)/i.test(body),
      "the page must say it declines rather than inventing when the record is " +
      "silent -- that honesty is the product, not a caveat"
    ).toBe(true);
  });
});

test.describe("Usage: whose telemetry", () => {
  test("says the figures are this platform's own spend, not NRG's", async ({ page }) => {
    const body = await text(page, "/usage");
    expect(/not NRG|not any employer/i.test(body)).toBe(true);
    expect(/this platform's own metered spend/i.test(body)).toBe(true);
  });

  test("the Workbench cost section still names its own scope", async ({ page }) => {
    // The 2026-09-18 cost incident: a reader took a Workbench-only figure for
    // the platform's total AI spend. Both halves of the fix are asserted here as
    // well as in agent/test_usage_frontend.js, because the harness tests the
    // renderer and this tests the real rendered page.
    const body = await text(page, "/usage");
    expect(/Workbench Delivery Efficiency/i.test(body)).toBe(true);
    expect(/does NOT include Claude Code/i.test(body)).toBe(true);
  });
});

test.describe("Navigation: what is and is not public", () => {
  const PUBLIC = ["/", "/workbench", "/triage", "/ask-codebase",
                  "/showcase/senior-java-ai-transformation", "/usage",
                  "/standing-interview", "/case-study/durable-agent"];

  for (const route of PUBLIC) {
    test(`${route} keeps Dashboard out of primary navigation`, async ({ page }) => {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(400);
      const navDashboard = await page.locator('nav.top-nav a[href="/dashboard"]').count();
      expect(
        navDashboard,
        "Dashboard is deliberately not primary public navigation. Its URL stays " +
        "reachable as deep technical evidence; the nav entry does not come back."
      ).toBe(0);
    });

    test(`${route} keeps Learn and JD Match out of primary navigation`, async ({ page }) => {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(400);
      for (const hidden of ["/learn", "/jd-match"]) {
        const count = await page.locator(`nav.top-nav a[href="${hidden}"]`).count();
        expect(count, `${hidden} is a private surface and must not appear in public nav`).toBe(0);
      }
    });
  }

  test("Usage does not offer Dashboard as a first-screen action", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto("/usage", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    const aboveFold = await page.evaluate(() =>
      Array.from(document.querySelectorAll('a[href="/dashboard"]'))
        .filter((a) => a.getBoundingClientRect().top + window.scrollY < 1000).length);
    expect(
      aboveFold,
      "offering Dashboard as a first-screen action re-adds exactly the route the " +
      "navigation deliberately removes. It stays linked further down the page."
    ).toBe(0);
  });
});
