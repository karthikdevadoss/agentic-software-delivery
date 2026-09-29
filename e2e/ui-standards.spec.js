// Sprint 15 (Owner's screenshot review, 2026-09-29). The guards that were
// missing when a broken navigation, an inconsistent type scale and 55% dead
// margin all reached the Owner through a 240/240 green production run.
//
// Every check here is written to FAIL against production as it stands. That is
// deliberate: a guard nobody has seen go red is not a guard.

const { test, expect } = require("@playwright/test");

const VIEWPORTS = [
  ["desktop-1920", 1920, 1080],
  ["desktop-1440", 1440, 900],
  ["laptop-1280", 1280, 900],
  ["tablet", 768, 1024],
  ["mobile", 390, 844],
];

const PUBLIC_PAGES = [
  ["home", "/"],
  ["case-study", "/case-study/durable-agent"],
  ["workbench", "/workbench"],
  ["triage", "/triage"],
  ["ask-codebase", "/ask-codebase"],
  ["showcase", "/showcase/senior-java-ai-transformation"],
  ["usage", "/usage"],
  ["standing-interview", "/standing-interview"],
  ["dashboard", "/dashboard"],
];

// --- the agreed standard, in one place -------------------------------------
// 1200px shell: research puts the readable container for a 1920 screen at
// 1140-1280. Prose inside it is capped separately at ~68ch.
const SHELL_MAX = 1200;
const SHELL_TOLERANCE = 40;      // pages may differ slightly, not structurally
const MIN_LEGIBLE_PX = 12;       // nothing smaller may carry real text
const BODY_PX = 17;              // one body size across the public surface

// Most of these pages paint their real content from an API call, so a fixed
// sleep is a race, not a wait. It lost that race once already: the h1-size
// check passed alone and failed inside a 4-worker run, because a page was
// still showing its "loading…" placeholder when it was measured. A guard that
// reports a defect that is not there costs exactly as much trust as one that
// misses a defect that is.
async function settle(page) {
  // Wait for the CONDITION, not for a duration: the h1 must exist and carry
  // real text before anything is measured off it. A fixed 2.5s sleep lost this
  // race once already -- the h1-size check passed alone and failed inside a
  // 4-worker run because a page was still showing its "loading…" placeholder.
  //
  // networkidle was tried here and removed: it added ~1.5s per page, which
  // pushed the 9-page loops from 12s to 28s -- under the 30s default alone,
  // over it under parallel load. It turned a flake into a timeout rather than
  // fixing it. The h1 condition is what these tests actually depend on.
  await page
    .waitForFunction(() => {
      const h1 = document.querySelector("h1");
      if (!h1) return false;
      const text = (h1.textContent || "").trim();
      if (!text || /loading/i.test(text)) return false;
      // The h1 alone is NOT enough, and assuming it was hid a real defect.
      // These pages paint their body from an API call, and the small text
      // lives in the DATA -- a "Known Cost Total" label at 10.88px and a
      // "PRODUCTION ACTIVE" badge at 11.2px both passed the 12px floor check
      // because neither existed yet at the moment it looked. Wait for the
      // main region to stop saying "loading" too.
      const main = document.querySelector("main");
      if (!main) return true;
      // Anywhere in main, not just at the end. Anchoring this to the end of
      // the text was the second version of this bug: the loading paragraph
      // has link rows after it, so "ends with loading" was already false on
      // the first paint and the wait returned immediately.
      return !/loading/i.test(main.textContent || "");
    }, null, { timeout: 10000 })
    .catch(() => {});
  // Then let the API-driven content actually arrive. networkidle is what
  // found the sub-12px labels that the h1 condition alone missed; it costs
  // ~1.5s a page, which is why the nine-page loops get their own timeout.
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(400);
}

// The loops below visit all nine public pages inside a single test, because
// the thing being asserted is CONSISTENCY ACROSS pages -- which cannot be
// checked one page at a time. Nine navigations do not fit the single-page
// default, and raising this is honest about what the test does rather than
// making the test do less.
const MULTI_PAGE_TIMEOUT_MS = 120_000;

test.describe("UI standard: the navigation shares its column with the content", () => {
  for (const [vpName, width, height] of VIEWPORTS) {
    for (const [name, route] of PUBLIC_PAGES) {
      test(`${name} nav aligns with content at ${vpName}`, async ({ page }) => {
        await page.setViewportSize({ width, height });
        await page.goto(route);
        await settle(page);
        const navLeft = await page.locator("#top-nav a").first()
          .evaluate((el) => el.getBoundingClientRect().left);
        const contentLeft = await page.locator("h1").first()
          .evaluate((el) => el.getBoundingClientRect().left);
        expect(Math.abs(navLeft - contentLeft),
          `${name}: nav starts at ${Math.round(navLeft)}px, content at ${Math.round(contentLeft)}px`)
          .toBeLessThanOrEqual(2);
      });
    }
  }
});

test.describe("UI standard: one content column across the whole site", () => {
  test("every public page uses the same shell width at 1920", async ({ page }) => {
    test.setTimeout(MULTI_PAGE_TIMEOUT_MS);
    await page.setViewportSize({ width: 1920, height: 1080 });
    const widths = {};
    for (const [name, route] of PUBLIC_PAGES) {
      await page.goto(route);
      await settle(page);
      widths[name] = await page.evaluate(() => {
        const h1 = document.querySelector("h1");
        let el = h1, best = 0;
        while (el && el !== document.body) {
          const w = el.getBoundingClientRect().width;
          if (w > best && w <= window.innerWidth) best = w;
          el = el.parentElement;
        }
        return Math.round(best);
      });
    }
    const values = Object.values(widths);
    const spread = Math.max(...values) - Math.min(...values);
    expect(spread,
      `content column differs across pages, so the layout jumps when you navigate: ${JSON.stringify(widths)}`)
      .toBeLessThanOrEqual(SHELL_TOLERANCE);
    for (const [name, w] of Object.entries(widths)) {
      expect(Math.abs(w - SHELL_MAX),
        `${name} column is ${w}px, target ${SHELL_MAX}px`).toBeLessThanOrEqual(SHELL_TOLERANCE * 2);
    }
  });
});

test.describe("UI standard: type is consistent and legible", () => {
  test("body size is the same on every public page", async ({ page }) => {
    test.setTimeout(MULTI_PAGE_TIMEOUT_MS);
    await page.setViewportSize({ width: 1920, height: 1080 });
    const sizes = {};
    for (const [name, route] of PUBLIC_PAGES) {
      await page.goto(route);
      await settle(page);
      sizes[name] = await page.evaluate(() => getComputedStyle(document.body).fontSize);
    }
    const unique = [...new Set(Object.values(sizes))];
    expect(unique.length, `body font differs across pages: ${JSON.stringify(sizes)}`).toBe(1);
    expect(parseFloat(unique[0])).toBe(BODY_PX);
  });

  test("the page title is a title on every page, not body text", async ({ page }) => {
    test.setTimeout(MULTI_PAGE_TIMEOUT_MS);
    await page.setViewportSize({ width: 1920, height: 1080 });
    const sizes = {};
    for (const [name, route] of PUBLIC_PAGES) {
      await page.goto(route);
      await settle(page);
      sizes[name] = await page.locator("h1").first()
        .evaluate((el) => Math.round(parseFloat(getComputedStyle(el).fontSize)));
    }
    const values = Object.values(sizes);
    const spread = Math.max(...values) - Math.min(...values);
    expect(spread, `h1 size varies by ${spread}px across pages: ${JSON.stringify(sizes)}`)
      .toBeLessThanOrEqual(8);
    for (const [name, s] of Object.entries(sizes)) {
      expect(s, `${name}'s h1 is only ${s}px`).toBeGreaterThanOrEqual(30);
    }
  });

  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} renders no text below ${MIN_LEGIBLE_PX}px`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto(route);
      await settle(page);
      const tooSmall = await page.evaluate((floor) => {
        const bad = [];
        for (const el of document.querySelectorAll("p,li,span,td,th,div,a,small,button,label")) {
          const text = (el.textContent || "").trim();
          if (!text || text.length < 6 || el.children.length) continue;
          const r = el.getBoundingClientRect();
          if (r.width < 1 || r.height < 1) continue;
          const fs = parseFloat(getComputedStyle(el).fontSize);
          if (fs < floor) bad.push(`${fs}px "${text.slice(0, 30)}"`);
        }
        return [...new Set(bad)].slice(0, 6);
      }, MIN_LEGIBLE_PX);
      expect(tooSmall, `${name} has text below ${MIN_LEGIBLE_PX}px`).toEqual([]);
    });
  }
});

test.describe("UI standard: the important part is visible without scrolling", () => {
  // 1920x1080 is the SCREEN. A real browser spends ~140px of it on tabs, the
  // address bar and the bookmarks strip, so the usable viewport is ~940px.
  // Testing the full 1080 quietly flatters the layout: the Owner's own
  // screenshot shows the proof cards jammed against the bottom edge, while a
  // 1080-tall test called them "above the fold".
  test("home shows the name, the role and all three proof cards above a REAL browser fold", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 940 });
    await page.goto("/");
    await settle(page);
    const above = await page.evaluate(() => {
      const inFold = (sel) => {
        const el = document.querySelector(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return r.top >= 0 && r.bottom <= window.innerHeight;
      };
      const cards = [...document.querySelectorAll(".pcard")].map((c) => {
        const r = c.getBoundingClientRect();
        return { top: Math.round(r.top), bottom: Math.round(r.bottom) };
      });
      return { h1: inFold("h1"), role: inFold(".role"), cards, vh: window.innerHeight };
    });
    expect(above.h1, "the name must be above the fold").toBe(true);
    expect(above.role, "the role line must be above the fold").toBe(true);
    expect(above.cards.length).toBe(3);
    for (const [i, c] of above.cards.entries()) {
      expect(c.bottom,
        `proof card ${i + 1} ends at ${c.bottom}px but the fold is ${above.vh}px -- 57% of desktop visitors never scroll, so they would never see the argument`)
        .toBeLessThanOrEqual(above.vh);
    }
  });

  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} puts something meaningful in the first screen`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 940 });
      await page.goto(route);
      await settle(page);
      const fold = await page.evaluate(() => {
        let chars = 0, interactive = 0;
        for (const el of document.querySelectorAll("h1,h2,h3,p,li")) {
          const r = el.getBoundingClientRect();
          if (r.top >= 0 && r.top < window.innerHeight && r.height > 0) {
            chars += (el.textContent || "").trim().length;
          }
        }
        for (const el of document.querySelectorAll("a,button,input,textarea")) {
          const r = el.getBoundingClientRect();
          if (r.top >= 0 && r.top < window.innerHeight && r.width > 0 && !el.closest("#top-nav")) interactive++;
        }
        return { chars, interactive };
      });
      expect(fold.chars,
        `${name} shows only ${fold.chars} characters of content above the fold`).toBeGreaterThan(220);
      expect(fold.interactive,
        `${name} offers nothing to click above the fold except the nav`).toBeGreaterThan(0);
    });
  }
});
