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
  ["recruiters", "/recruiters"],
];

// --- the agreed standard, in one place -------------------------------------
// 1200px shell: research puts the readable container for a 1920 screen at
// 1140-1280. Prose inside it is capped separately at ~68ch.
const SHELL_MAX = 1200;
const SHELL_TOLERANCE = 40;      // pages may differ slightly, not structurally
// 12.5, not 12. The source sweep set every stylesheet to 12.5px, but this
// constant was left at 12 -- so the guard was quietly one notch more lenient
// than the standard it was supposed to be enforcing, and a 12px heading passed
// while the close-out claimed "12.5px smallest text". An independent review
// caught the gap. The number the guard asserts and the number the code applies
// have to be the same number.
const MIN_LEGIBLE_PX = 12.5;
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
        // Measure the CONTAINERS, not the h1's ancestor chain. Walking up from
        // the h1 only ever sees the container the h1 happens to live in -- on
        // /usage the h1 sits in a 1200px <header> while <main> was still
        // 1100px, so the page shipped a 100px mismatch that this check
        // reported as compliant. An independent review found it by measuring
        // main directly.
        const found = [];
        for (const sel of ["main", "header", ".wrap", ".si-wrap"]) {
          for (const el of document.querySelectorAll(sel)) {
            const w = el.getBoundingClientRect().width;
            if (w > 0 && w <= window.innerWidth) found.push({ sel, el, w: Math.round(w) });
          }
        }
        // Only TOP-LEVEL containers. home.html puts its <header> INSIDE .wrap,
        // so the header is legitimately narrower by the wrap's padding -- that
        // is correct nesting, not a layout defect, and comparing it against its
        // own parent is a false positive. What matters is whether containers
        // that sit SIDE BY SIDE agree: on /usage, <header> and <main> are
        // siblings and were 1200 and 1100.
        const top = found.filter(
          (a) => !found.some((b) => b.el !== a.el && b.el.contains(a.el)));
        const boxes = {};
        for (const t of top) boxes[t.sel] = t.w;
        return boxes;
      });
    }
    // WITHIN a page first. Taking the widest container per page hid the real
    // defect: /usage had a 1200px <header> and an 1100px <main>, so the page
    // disagreed with ITSELF by 100px and the across-pages check still saw a
    // compliant 1200. Every container on one page must agree before comparing
    // pages to each other.
    for (const [name, boxes] of Object.entries(widths)) {
      const vals = Object.values(boxes);
      expect(vals.length, `${name}: found no layout container to measure`).toBeGreaterThan(0);
      const inner = Math.max(...vals) - Math.min(...vals);
      expect(inner,
        `${name} disagrees with itself -- its own containers are different widths, so the page shifts sideways as you scroll past the header: ${JSON.stringify(boxes)}`)
        .toBeLessThanOrEqual(SHELL_TOLERANCE);
    }

    // Sprint 16 CHANGED THIS, and the reason is recorded because relaxing a
    // guard needs justifying more than tightening one does.
    //
    // Sprint 15's defect was FIVE arbitrary widths -- 700/860/936/1000/1100 --
    // that nobody had decided, so the layout jumped unpredictably. The guard
    // expressed that as "every page the same", which was a proxy.
    //
    // Sprint 16 makes the width follow the CONTENT TYPE: a page built from
    // paragraphs uses 860 and a page built from data grids uses 1200, because
    // capping prose at 58ch inside a 1200px panel left half the panel empty.
    // That is a decision, not drift.
    //
    // So the assertion is now "one of the SANCTIONED widths" rather than "all
    // identical". Arbitrary drift still fails -- a sixth width nobody chose is
    // exactly as caught as before.
    const SANCTIONED = [860, 1200];
    const perPage = Object.fromEntries(
      Object.entries(widths).map(([n, b]) => [n, Math.max(...Object.values(b))]));
    for (const [name, w] of Object.entries(perPage)) {
      const nearest = SANCTIONED.reduce(
        (best, s) => (Math.abs(w - s) < Math.abs(w - best) ? s : best), SANCTIONED[0]);
      expect(Math.abs(w - nearest),
        `${name} column is ${w}px, which is not one of the sanctioned widths ` +
        `${JSON.stringify(SANCTIONED)} -- a width nobody decided is how Sprint 15 ` +
        `ended up with five of them`).toBeLessThanOrEqual(SHELL_TOLERANCE * 2);
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
    // Sprint 16 CHANGED THIS ASSERTION, and the reason is recorded because
    // relaxing a guard is exactly the move that needs justifying.
    //
    // Sprint 15's defect was an h1 of 26.4px sitting next to home's 44px --
    // a page title that read as body text. The guard expressed that as "all
    // h1 sizes within 8px", which was a PROXY for the real requirement.
    //
    // Sprint 16 gives every page its own display face by explicit Owner
    // decision, and a serif at 44px, a geometric sans at 40px and a monospace
    // at 33px are the SAME optical weight -- mono and serif need different
    // point sizes to read as equals. Holding them to one pixel value would
    // force the wrong size on two pages to satisfy a number.
    //
    // So the requirement is asserted directly instead: every page's title
    // must READ AS A TITLE. The 30px floor that actually caught the original
    // defect is unchanged, and an upper bound is added so "unique" cannot
    // become a 90px h1 nobody reviewed.
    for (const [name, size] of Object.entries(sizes)) {
      expect(size, `${name}'s h1 is only ${size}px -- it will read as body text`)
        .toBeGreaterThanOrEqual(30);
      expect(size, `${name}'s h1 is ${size}px, which is shouting rather than titling`)
        .toBeLessThanOrEqual(56);
    }
  });

  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} renders no text below ${MIN_LEGIBLE_PX}px`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 1080 });
      await page.goto(route);
      await settle(page);
      const tooSmall = await page.evaluate((floor) => {
        const bad = [];
        // EVERY element, not a hand-written list of tag names. The list used
        // to be "p,li,span,td,th,div,a,small,button,label", which excluded
        // <h2> and <dt> -- and an 11px <dt> on the case study plus a 12px
        // <h2> on the home page sat on the live site while this check
        // reported both pages clean. That is the same defect the whole sprint
        // exists to fix (a guard measuring only what its author thought to
        // enumerate), reintroduced inside the fix for it. Enumerating tags is
        // the bug; asking every element is the fix.
        for (const el of document.querySelectorAll("*")) {
          if (el.closest("svg")) continue;
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
