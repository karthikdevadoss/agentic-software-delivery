// Sprint 14: real-browser coverage for the recruiter-facing home page ("/")
// and the durable-agent case study. This is the spec the release standard
// leans on -- "tests are green" must not be able to coexist with a visibly
// broken first screen, so this asserts rendered layout and interaction, not
// just HTTP 200.
//
// Viewports are the three the release contract requires: desktop 1280x900,
// tablet 768x1024, mobile 390x844.

const { test, expect } = require("@playwright/test");

// Sprint 14 correction (Owner, 2026-09-29): DESKTOP IS THE PRIMARY TARGET and
// 1280 is not desktop -- it is a small laptop. The Owner's own bug report came
// from 1920x1080, a width this matrix never tested, which is exactly why a
// broken navigation on /standing-interview reached him rather than a test.
// 1920 now leads the list; 1280 is kept because it is a real laptop size.
const VIEWPORTS = [
  ["desktop-1920", 1920, 1080],
  ["desktop-1440", 1440, 900],
  ["laptop-1280", 1280, 900],
  ["tablet", 768, 1024],
  ["mobile", 390, 844],
];

// Sprint 18 inserted "Evidence" (the /proof evidence index) directly after
// Home. It belongs in the canonical nav rather than only on the home page,
// because its purpose is to be reachable from wherever a visitor is standing
// when a claim makes them want to check it.
const CANONICAL_NAV = ["Home", "Evidence", "Workbench", "Triage", "Ask Codebase", "Showcase", "Usage"];

// Sprint 18: read from the registry that generates the rows, rather than
// restating a number the registry already owns. yaml is not a dependency of
// this project's node side, so the two values are parsed with a narrow regex
// over the committed file and asserted non-trivial below -- a parse that
// silently yielded 0 or an empty list would make these tests pass vacuously.
const fs = require("fs");
const path = require("path");
const SURFACE_YAML = fs.readFileSync(
  path.join(__dirname, "..", "docs", "PUBLIC_PROOF_SURFACE.yaml"), "utf8");
const PRIMARY_COUNT = (SURFACE_YAML.match(/^\s*tier:\s*PRIMARY\s*$/gm) || []).length;
// Scoped to the status_vocabulary block. The first version of this matched
// every 4-space `label:` in the file and so collected SEVEN labels -- the four
// statuses plus the three audience labels, which sit at the same indent under
// `audiences:`. The membership test below would still have passed with the
// wrong seven, which is precisely why the parse guard exists.
const STATUS_BLOCK = SURFACE_YAML.slice(
  SURFACE_YAML.indexOf("status_vocabulary:"),
  SURFACE_YAML.indexOf("status_requires:"));
const PUBLIC_STATUS_LABELS = (STATUS_BLOCK.match(/^\s{4}label:\s*(.+)$/gm) || [])
  .map((line) => line.replace(/^\s{4}label:\s*/, "").trim());

test.describe("Sprint 18 registry parse (guards the tests above from passing vacuously)", () => {
  test("the registry really was parsed", () => {
    expect(PRIMARY_COUNT).toBeGreaterThanOrEqual(5);
    expect(PRIMARY_COUNT).toBeLessThanOrEqual(7);
    expect(PUBLIC_STATUS_LABELS).toContain("Live");
    expect(PUBLIC_STATUS_LABELS).toContain("Experimental / paused");
    expect(PUBLIC_STATUS_LABELS.length).toBe(4);
  });
});

test.describe("Home page — identity and claims", () => {
  test("the first screen names the person, the role and the separation", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toHaveText("Karthikeyan Devadoss");
    await expect(page.locator(".role")).toContainText("Java, Spring & Agentic AI");
    await expect(page.locator(".meta")).toContainText("Berlin");
    // The NRG separation is the single most important truthfulness sentence
    // on the page: the platform must never read as an employer's product.
    await expect(page.locator(".sep")).toContainText("not an NRG product");
  });

  test("exactly three proof cards, each with a working destination", async ({ page }) => {
    await page.goto("/");
    const cards = page.locator(".pcard");
    await expect(cards).toHaveCount(3);
    await expect(cards.nth(0).locator("h2")).toContainText("cannot approve its own writes");
    await expect(cards.nth(1).locator("h2")).toContainText("survives a crash");
    await expect(cards.nth(2).locator("h2")).toContainText("measured, not assumed");
    for (let i = 0; i < 3; i++) {
      const href = await cards.nth(i).locator("a.go").getAttribute("href");
      expect(href, `proof card ${i + 1} must have a real destination`).toBeTruthy();
      expect(href).not.toBe("#");
    }
  });

  // Sprint 18: the count was hardcoded at 6 here and at 6 again in
  // agent/test_public_surface_gate.py. Both now read PRIMARY_COUNT from
  // docs/PUBLIC_PROOF_SURFACE.yaml, because the rows are generated from that
  // registry by agent/build_proof_surface.py -- a contract stated in three
  // places is a contract that drifts in two of them.
  test("the evidence rows match the registry, each with a status, a limitation and a link",
    async ({ page }) => {
      await page.goto("/");
      const rows = page.locator(".erow");
      await expect(rows).toHaveCount(PRIMARY_COUNT);
      const count = await rows.count();
      for (let i = 0; i < count; i++) {
        await expect(rows.nth(i).locator(".estat")).not.toBeEmpty();
        // Sprint 18's new contract: every claim carries its own boundary,
        // beside the claim rather than in a disclaimer nobody reaches.
        await expect(rows.nth(i).locator(".elimit")).not.toBeEmpty();
        await expect(rows.nth(i).locator(".side a").first()).toBeVisible();
      }
    });

  test("every status label is one of the four published values", async ({ page }) => {
    await page.goto("/");
    const labels = await page.locator(".erow .estat").allTextContents();
    expect(labels.length).toBe(PRIMARY_COUNT);
    for (const label of labels) {
      expect(PUBLIC_STATUS_LABELS, `unknown status label ${label.trim()}`)
        .toContain(label.trim());
    }
  });

  test("the paused experiment is not presented as live", async ({ page }) => {
    await page.goto("/");
    const row = page.locator(".erow").filter({ hasText: "An experiment that failed its own test" });
    await expect(row).toHaveCount(1);
    await expect(row.locator(".estat")).toHaveText("Experimental / paused");
    await expect(row).toContainText("unproven");
  });

  test("MCP is not presented as a hosted production service", async ({ page }) => {
    // Sprint 18 merged the standalone MCP row into the retrieval capability the
    // registry already bundles it with (rag-mcp-embeddings), so this no longer
    // looks for a row titled "MCP server". It asserts the property that
    // actually matters and survives the row being reorganised.
    await page.goto("/");
    const row = page.locator(".erow").filter({ hasText: "Model Context Protocol" });
    await expect(row).toHaveCount(1);
    await expect(row.locator(".estat")).not.toHaveText("Live");
    await expect(row).toContainText("runs locally");
  });

  test("scope boundaries are present and neutrally worded", async ({ page }) => {
    await page.goto("/");
    const scope = page.locator(".scope");
    await expect(scope).toBeVisible();
    await expect(scope).toContainText("one model provider");
    await expect(scope).toContainText("managed vector database");
    await expect(scope).toContainText("future work");
  });

  test("employers are exactly the three approved, with no dates", async ({ page }) => {
    await page.goto("/");
    const emp = page.locator(".emp");
    await expect(emp).toContainText("NRG Energy");
    await expect(emp).toContainText("Blue Cross Blue Shield Association");
    await expect(emp).toContainText("Marsh");
    await expect(emp).not.toContainText("Northern Trust");
    // no year ranges anywhere in the background block
    await expect(page.locator(".bg")).not.toHaveText(/\b(19|20)\d{2}\b/);
  });

  test("footer cookie wording is precise and makes no legal conclusion", async ({ page }) => {
    await page.goto("/");
    const footer = page.locator("footer");
    await expect(footer).toContainText("sets no cookies and uses no analytics or third-party trackers");
    await expect(footer).not.toContainText("Impressum");
  });
});

test.describe("Home page — navigation and links", () => {
  test("canonical nav renders in the exact contracted order", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#top-nav a")).not.toHaveCount(0);
    const labels = await page.locator("#top-nav a").allTextContents();
    const visible = labels.map((l) => l.trim()).filter(Boolean);
    // Standing Interview is gated on its corpus endpoint and may legitimately
    // be absent; the unconditional six must be present, in order.
    const withoutGated = visible.filter((l) => l !== "Standing Interview");
    expect(withoutGated).toEqual(CANONICAL_NAV);
  });

  test("Home is marked as the current page on /", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#top-nav a strong")).toHaveText("Home");
  });

  test("no public page links to Learn or JD Match", async ({ page }) => {
    for (const path of ["/", "/workbench", "/usage", "/triage", "/ask-codebase", "/case-study/durable-agent"]) {
      await page.goto(path);
      await expect(page.locator('a[href^="/learn"]'), `${path} must not link to Learn`).toHaveCount(0);
      await expect(page.locator('a[href^="/jd-match"]'), `${path} must not link to JD Match`).toHaveCount(0);
    }
  });

  test("every internal link on the home page resolves", async ({ page, request }) => {
    await page.goto("/");
    const hrefs = await page.locator('a[href^="/"]').evaluateAll((as) =>
      [...new Set(as.map((a) => a.getAttribute("href")))]);
    for (const href of hrefs) {
      const target = href.split("#")[0] || "/";
      const r = await request.get(target);
      expect(r.status(), `${href} should not be broken`).toBeLessThan(400);
    }
  });

  test("Learn and JD Match return 404 publicly", async ({ request }) => {
    for (const path of ["/learn", "/jd-match", "/api/jd-match/sample", "/api/learn/tree"]) {
      const r = await request.get(path);
      expect(r.status(), `${path} must be 404`).toBe(404);
    }
  });

  test("Dashboard is out of nav but still reachable from Usage", async ({ page }) => {
    // Usage renders its Dashboard deep link client-side once its data has
    // loaded, so the assertion has to wait for render rather than read the
    // initial DOM -- the first version of this test read too early and failed
    // against a page that was actually correct.
    await page.goto("/usage");
    await expect(page.locator('#top-nav a[href="/dashboard"]')).toHaveCount(0);
    await expect(page.locator('a[href="/dashboard"]').first()).toBeVisible({ timeout: 30_000 });
  });

  test("browser Back returns to the home page", async ({ page }) => {
    await page.goto("/");
    await page.locator('.tiles a[href="/workbench"]').click();
    await expect(page).toHaveURL(/\/workbench$/);
    await page.goBack();
    await expect(page.locator("h1")).toHaveText("Karthikeyan Devadoss");
  });
});

test.describe("Durable-agent case study", () => {
  test("renders completely and carries its honest limits", async ({ page }) => {
    await page.goto("/case-study/durable-agent");
    await expect(page.locator("h1")).toContainText("halfway through an AI-written change");
    await expect(page.locator(".banner div")).toHaveCount(3);
    const caveat = page.locator(".caveat");
    await expect(caveat).toBeVisible();
    await expect(caveat).toContainText("not an employer production system");
    await expect(caveat).toContainText("triggered by hand");
  });

  test("carries no mockup label and returns to home", async ({ page }) => {
    await page.goto("/case-study/durable-agent");
    await expect(page.locator("body")).not.toContainText(/MOCKUP/i);
    await page.locator(".back a").click();
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe("Layout, accessibility and browser quality", () => {
  for (const [name, width, height] of VIEWPORTS) {
    for (const path of ["/", "/case-study/durable-agent"]) {
      test(`${path} at ${name} (${width}x${height}): no overflow, no console errors`, async ({ page }) => {
        const consoleErrors = [];
        const pageErrors = [];
        page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
        page.on("pageerror", (e) => pageErrors.push(String(e)));

        await page.setViewportSize({ width, height });
        await page.goto(path);
        await page.waitForTimeout(1200);   // let nav.js render

        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
        expect(overflow, `${path} scrolls sideways at ${name}`).toBe(false);

        // nothing important may be pushed off-screen
        const offscreen = await page.evaluate((w) => {
          const bad = [];
          for (const el of document.querySelectorAll("a, button, h1, h2, .pcard, .tile, .erow")) {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && (r.right > w + 1 || r.left < -1)) bad.push(el.className || el.tagName);
          }
          return bad;
        }, width);
        expect(offscreen, `elements off-screen at ${name}: ${offscreen.join(", ")}`).toEqual([]);

        expect(consoleErrors, `console errors on ${path} at ${name}`).toEqual([]);
        expect(pageErrors, `page errors on ${path} at ${name}`).toEqual([]);
      });
    }
  }

  // REGRESSION: found by visual screenshot inspection on 2026-09-29, missed by
  // every DOM/overflow assertion in this file. The nav lived in a wrapper with
  // its own horizontal padding, so it started 22px to the LEFT of the content
  // column -- a visibly crooked menu that no "does the element exist" check
  // can see. Alignment is now asserted numerically.
  // WIDENED after the Owner's 2026-09-29 bug report: this was checking two
  // pages. /standing-interview's nav spans the full viewport and sits at x=0
  // with "Home" clipped at the edge, 596px away from its own content -- and no
  // test looked. Every public page is checked now, at every viewport.
  for (const [vpName, width, height] of VIEWPORTS) {
    for (const [pageName, route, firstSelector] of [
      ["home", "/", "h1"],
      ["case study", "/case-study/durable-agent", "h1"],
      ["workbench", "/workbench", "h1"],
      ["triage", "/triage", "h1"],
      ["ask codebase", "/ask-codebase", "h1"],
      ["showcase", "/showcase/senior-java-ai-transformation", "h1"],
      ["usage", "/usage", "h1"],
      ["standing interview", "/standing-interview", "h1"],
      ["dashboard", "/dashboard", "h1"],
    ]) {
      test(`${pageName} nav aligns with the content column at ${vpName}`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await page.goto(route);
        await page.waitForTimeout(1200);
        const navLeft = await page.locator("#top-nav a").first().evaluate(
          (el) => el.getBoundingClientRect().left);
        const contentLeft = await page.locator(firstSelector).first().evaluate(
          (el) => el.getBoundingClientRect().left);
        expect(Math.abs(navLeft - contentLeft),
          `nav starts at ${navLeft}px but content starts at ${contentLeft}px`).toBeLessThanOrEqual(2);
      });
    }
  }

  // REGRESSION: /usage and /dashboard scrolled horizontally because a wide
  // .cap-table dragged the whole document sideways. Measured against
  // production 2026-09-29 (usage at 390px; dashboard at all three widths).
  // Usage is a canonical nav destination, so this was recruiter-visible.
  for (const [vpName, width, height] of VIEWPORTS) {
    for (const route of ["/usage", "/dashboard"]) {
      test(`${route} does not scroll sideways at ${vpName}`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await page.goto(route);
        await page.waitForTimeout(3000);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
        expect(overflow, `${route} scrolls sideways at ${vpName}`).toBe(false);
      });
    }
  }

  test("heading order on the home page is semantic", async ({ page }) => {
    await page.goto("/");
    const levels = await page.locator("h1, h2, h3").evaluateAll(
      (els) => els.map((e) => Number(e.tagName.slice(1))));
    expect(levels[0]).toBe(1);
    expect(levels.filter((l) => l === 1)).toHaveLength(1);
    for (let i = 1; i < levels.length; i++) {
      expect(levels[i] - levels[i - 1], `heading level jumps at index ${i}`).toBeLessThanOrEqual(1);
    }
  });

  test("every link has an accessible name", async ({ page }) => {
    await page.goto("/");
    const unnamed = await page.locator("a").evaluateAll((as) =>
      as.filter((a) => !(a.textContent || "").trim() && !a.getAttribute("aria-label")).length);
    expect(unnamed).toBe(0);
  });

  test("keyboard focus is visible and reaches the primary CTA", async ({ page }) => {
    await page.goto("/");
    await page.waitForTimeout(1000);
    const cta = page.locator('.bottom a.btn');
    await cta.focus();
    await expect(cta).toBeFocused();
    const outline = await cta.evaluate((el) => getComputedStyle(el).outlineStyle);
    expect(outline).not.toBe("none");
  });

  test("the page does not depend on JavaScript for its content", async ({ browser }) => {
    // nav.js renders the menu, but the claims themselves must be in the HTML.
    const ctx = await browser.newContext({ javaScriptEnabled: false });
    const page = await ctx.newPage();
    await page.goto("/");
    await expect(page.locator("h1")).toHaveText("Karthikeyan Devadoss");
    await expect(page.locator(".pcard")).toHaveCount(3);
    await expect(page.locator(".erow")).toHaveCount(PRIMARY_COUNT);
    await ctx.close();
  });
});
