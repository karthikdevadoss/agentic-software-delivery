// Sprint 14: real-browser coverage for the recruiter-facing home page ("/")
// and the durable-agent case study. This is the spec the release standard
// leans on -- "tests are green" must not be able to coexist with a visibly
// broken first screen, so this asserts rendered layout and interaction, not
// just HTTP 200.
//
// Viewports are the three the release contract requires: desktop 1280x900,
// tablet 768x1024, mobile 390x844.

const { test, expect } = require("@playwright/test");

const VIEWPORTS = [
  ["desktop", 1280, 900],
  ["tablet", 768, 1024],
  ["mobile", 390, 844],
];

const CANONICAL_NAV = ["Home", "Workbench", "Triage", "Ask Codebase", "Showcase", "Usage"];

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

  test("exactly six evidence rows, each with a status and an evidence link", async ({ page }) => {
    await page.goto("/");
    const rows = page.locator(".erow");
    await expect(rows).toHaveCount(6);
    const count = await rows.count();
    for (let i = 0; i < count; i++) {
      await expect(rows.nth(i).locator(".estat")).not.toBeEmpty();
      await expect(rows.nth(i).locator(".side a")).toHaveCount(1);
    }
  });

  test("the MCP row does not claim production", async ({ page }) => {
    await page.goto("/");
    const mcp = page.locator(".erow").filter({ hasText: "MCP server" });
    await expect(mcp).toHaveCount(1);
    await expect(mcp.locator(".estat")).toHaveText("Implemented and tested");
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
  for (const [vpName, width, height] of VIEWPORTS) {
    for (const [pageName, route, firstSelector] of [
      ["home", "/", "h1"],
      ["case study", "/case-study/durable-agent", "h1"],
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
    await expect(page.locator(".erow")).toHaveCount(6);
    await ctx.close();
  });
});
