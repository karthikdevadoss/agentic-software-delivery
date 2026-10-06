// Sprint 16. The Owner opened the site Sprint 15 had just verified 67/67 and
// said "None of the pages looks good in browser. so bad."
//
// He was right, and every one of those 67 guards was also right. They measure
// CORRECTNESS -- alignment, font sizes, a legibility floor, overflow. None of
// them measures whether a page is readable or balanced. A page can be
// perfectly aligned, perfectly consistent, and still be unpleasant to look at.
//
// These guards cover the properties in docs/DESIGN_DEFECTS_2026-09-30.md that
// are genuinely measurable. They do NOT cover DD6 (flat visual hierarchy),
// which is real and which no assertion will catch -- that one needs a human
// looking at a screenshot, and pretending otherwise is how Sprint 15 shipped.

const { test, expect } = require("@playwright/test");

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
  ["interviewer", "/interviewer"],
];

// Typographic research is unusually settled here: the comfortable line length
// is 50-75 characters, with 66 the commonly cited optimum. Past roughly 90 the
// eye loses its place returning to the next line. Measured on production
// 2026-09-30: dashboard, usage, workbench, triage and ask-codebase were all
// rendering paragraphs at 172 characters -- 2.6x the optimum -- and 53
// paragraphs sitewide exceeded 90.
const MAX_LINE_CHARS = 75;

// The header block and the content below it should be close to the same width.
// Measured 2026-09-30: six pages had a 587px header above 1136px content, a
// ratio of 1.94, so the top of the page was half the width of the bottom.
const MAX_HEADER_BODY_RATIO = 1.4;   // 1.94 was the defect; 1.26 on a
                                     // prose page is normal, not one

const MULTI_PAGE_TIMEOUT_MS = 120_000;

async function settle(page) {
  await page
    .waitForFunction(() => {
      const h1 = document.querySelector("h1");
      if (!h1) return false;
      const text = (h1.textContent || "").trim();
      if (!text || /loading/i.test(text)) return false;
      const main = document.querySelector("main");
      return !main || !/loading/i.test(main.textContent || "");
    }, null, { timeout: 10000 })
    .catch(() => {});
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(400);
}

test.describe("Design standard: text is readable", () => {
  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} keeps every paragraph inside the reading measure`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 940 });
      await page.goto(route);
      await settle(page);

      const long = await page.evaluate((maxChars) => {
        const bad = [];
        for (const el of document.querySelectorAll("p,li,dd,blockquote")) {
          if (el.children.length) continue;               // leaf text only
          const text = (el.textContent || "").trim();
          if (text.length < 40) continue;                 // not a paragraph
          const rects = el.getClientRects();
          if (!rects.length) continue;
          // ACTUAL characters per line, not an estimate from width.
          //
          // The first version divided the rendered width by fs*0.5, assuming
          // an average glyph advance. That is font-dependent, and it broke the
          // moment real webfonts loaded: Inter is narrower than the previous
          // system stack, so the same 68ch column measured 86 "characters"
          // while rendering fewer than before. The estimator moved, the page
          // did not.
          //
          // Dividing the text length by the number of rendered LINES is exact
          // and font-independent: it is what the reader actually sees.
          const cs = getComputedStyle(el);
          const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.5;
          const lines = Math.max(1, Math.round(el.getBoundingClientRect().height / lh));
          const chars = Math.round(text.length / lines);
          if (chars > maxChars) {
            bad.push(`${chars} chars: "${text.slice(0, 55)}..."`);
          }
        }
        return [...new Set(bad)].slice(0, 6);
      }, MAX_LINE_CHARS);

      expect(long,
        `${name} renders paragraphs wider than ${MAX_LINE_CHARS} characters. The ` +
        `readable band is 50-75 (66 optimal); past ~90 the eye loses its place ` +
        `returning to the next line`).toEqual([]);
    });
  }
});

test.describe("Design standard: the page is balanced", () => {
  test("the header block is not far narrower than the content below it", async ({ page }) => {
    test.setTimeout(MULTI_PAGE_TIMEOUT_MS);
    await page.setViewportSize({ width: 1920, height: 940 });
    const offenders = [];

    for (const [name, route] of PUBLIC_PAGES) {
      await page.goto(route);
      await settle(page);
      const m = await page.evaluate(() => {
        // TEXT measure, not block width. The first version of this guard
        // compared the <header> block against the panels and passed on every
        // page -- because the <h1> block is already full width, so the ratio
        // was 1.00 while the page visibly had a 587px paragraph above 1136px
        // content. The block was never the thing the eye reacts to; the line
        // of text inside it is.
        const measure = (root, sel) => {
          let widest = 0;
          for (const el of root.querySelectorAll(sel)) {
            if (el.children.length) continue;
            const t = (el.textContent || "").trim();
            if (t.length < 40) continue;          // not a real line of prose
            const r = el.getClientRects();
            if (r.length) widest = Math.max(widest, Math.round(r[0].width));
          }
          return widest;
        };
        const h = document.querySelector("header, .wrap > header");
        const header = h ? measure(h, "p") : 0;
        let body = 0;
        for (const el of document.querySelectorAll("main, .wrap")) {
          body = Math.max(body, measure(el, "p,li"));
        }
        return { header, body };
      });
      if (!m.header || !m.body) continue;      // page has no such structure
      const ratio = m.body / m.header;
      if (ratio > MAX_HEADER_BODY_RATIO) {
        offenders.push(`${name}: header ${m.header}px vs body ${m.body}px (ratio ${ratio.toFixed(2)})`);
      }
    }

    expect(offenders,
      `the top of these pages is much narrower than the bottom, so the eye reads a ` +
      `narrow column that abruptly becomes a wide one:\n  ${offenders.join("\n  ")}`)
      .toEqual([]);
  });
});

test.describe("Design standard: nothing reads as a bug", () => {
  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} does not repeat a link next to itself`, async ({ page }) => {
      await page.setViewportSize({ width: 1920, height: 940 });
      await page.goto(route);
      await settle(page);
      const dups = await page.evaluate(() => {
        const out = [];
        const as = [...document.querySelectorAll("a")];
        for (let i = 1; i < as.length; i++) {
          const a = as[i].textContent.trim();
          const b = as[i - 1].textContent.trim();
          if (a && a === b && as[i].parentElement === as[i - 1].parentElement) out.push(a);
        }
        return [...new Set(out)];
      });
      expect(dups,
        `${name} renders the same link immediately next to itself. Whatever the ` +
        `data reason, it reads as a bug`).toEqual([]);
    });
  }
});
