// Sprint 17, BL-C6 and BL-R1. Properties that must hold at every width the site
// is actually opened at.
//
// THE DEFECT THIS EXISTS FOR, measured not assumed. The BEFORE capture against
// real production (visual-audit-sprint17-before/manifest.json, 2026-09-30) found
// /showcase at 390px with scrollWidth 435 against clientWidth 390. Walking every
// element and comparing scrollWidth to clientWidth -- rather than reading the
// page and guessing -- found the mechanism:
//
//   ul.sc-talking-points li   scrollWidth 335, clientWidth 260   (+75)
//   div.sc-det-evidence       scrollWidth 267, clientWidth 260   (+7)
//                             "Evidence: docs/ai/AI_ENGINEERING_QUALITY_LEDGER.yaml"
//   div.goal (on /usage)      scrollWidth 274, clientWidth 229   (+45)
//
// Every one is one mechanism: a token with no break opportunity -- a repository
// path, a SCREAMING_SNAKE identifier, a hash, a run id -- inside a container
// narrower than the token. So the fix in agent/web/style.css is set once, on
// body, and inherited; and this spec asserts the PROPERTY at four widths rather
// than asserting that one path on one page is fine.
//
// WHY 1px OF TOLERANCE. Sub-pixel layout rounding makes an exactly-fitting page
// report scrollWidth one greater than clientWidth on some zoom levels. A
// zero-tolerance assertion here would flake for a reason that is not a defect.
// 1px is rounding; 10px is a bug.

const { test, expect } = require("@playwright/test");

const PUBLIC_PAGES = [
  ["home", "/"],
  ["workbench", "/workbench"],
  ["triage", "/triage"],
  ["ask-codebase", "/ask-codebase"],
  ["showcase", "/showcase/senior-java-ai-transformation"],
  ["usage", "/usage"],
  ["standing-interview", "/standing-interview"],
  ["case-study", "/case-study/durable-agent"],
  // Not primary recruiter navigation and included anyway: it is reachable by
  // URL, the check is cheap, and the brief asked for it explicitly.
  ["dashboard", "/dashboard"],
];

// 390 is the iPhone width the Owner's own screenshots use. 768 is a tablet and
// the width most single-column breakpoints trigger at. 1280 is the commonest
// laptop. 1920 is what the Owner actually works on.
const WIDTHS = [390, 768, 1280, 1920];

async function settle(page) {
  try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch { /* long-poll pages never idle */ }
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  let last = -1;
  for (let i = 0; i < 15; i++) {
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    if (h === last) return;
    last = h;
    await page.waitForTimeout(120);
  }
}

// Returns the DEEPEST elements whose own content overflows their own box, so a
// failure message names the culprit instead of naming <html>.
async function overflowCulprits(page) {
  return page.evaluate(() => {
    const cw = document.documentElement.clientWidth;
    const out = [];
    for (const el of document.querySelectorAll("*")) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      if (["HTML", "BODY"].includes(el.tagName)) continue;
      const st = getComputedStyle(el);
      // An element allowed to scroll inside its own box (a table, a pre, a
      // deliberate .table-scroll) is not a page-overflow defect.
      if (st.overflowX === "auto" || st.overflowX === "scroll") continue;
      const contentOverflow = el.scrollWidth - el.clientWidth;
      const pastEdge = Math.round(r.right) - cw;
      if (contentOverflow > 1 || pastEdge > 1) {
        out.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className || "").toString().slice(0, 60),
          contentOverflow, pastEdge,
          text: (el.innerText || "").trim().replace(/\s+/g, " ").slice(0, 90),
        });
      }
    }
    return out;
  });
}

for (const width of WIDTHS) {
  test.describe(`at ${width}px`, () => {
    test.use({ viewport: { width, height: width < 500 ? 844 : 1080 } });

    for (const [name, route] of PUBLIC_PAGES) {
      test(`${name} does not scroll horizontally`, async ({ page }) => {
        await page.goto(route, { waitUntil: "domcontentloaded" });
        await settle(page);
        const { scrollWidth, clientWidth } = await page.evaluate(() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }));
        if (scrollWidth > clientWidth + 1) {
          const culprits = await overflowCulprits(page);
          const detail = culprits.slice(0, 8).map(
            (c) => `    <${c.tag} class="${c.cls}"> content +${c.contentOverflow}px, ` +
                   `right edge +${c.pastEdge}px :: ${c.text}`
          ).join("\n");
          throw new Error(
            `${name} at ${width}px: scrollWidth ${scrollWidth} > clientWidth ${clientWidth}.\n` +
            `Deepest overflowing element(s):\n${detail || "    (none found -- look at negative margins or a fixed-width child)"}\n` +
            `This is almost always an unbreakable token (a path, a hash, an identifier). ` +
            `The site-wide fix is body { overflow-wrap: anywhere } in agent/web/style.css; ` +
            `if a new page does not load that sheet it needs its own copy.`
          );
        }
        expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
      });

      test(`${name} has no console error or uncaught page error`, async ({ page }) => {
        const consoleErrors = [];
        const pageErrors = [];
        page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
        page.on("pageerror", (e) => pageErrors.push(String(e)));
        await page.goto(route, { waitUntil: "domcontentloaded" });
        await settle(page);
        expect(pageErrors, `${name} at ${width}px threw: ${pageErrors.join(" | ")}`).toEqual([]);
        expect(consoleErrors, `${name} at ${width}px logged: ${consoleErrors.join(" | ")}`).toEqual([]);
      });
    }
  });
}

test.describe("Accessible names, at the narrowest width", () => {
  // Checked once rather than per width: an accessible name does not change with
  // the viewport, and running it four times would quadruple the cost for
  // identical results. 390 is chosen because that is where a control is most
  // likely to be icon-only.
  test.use({ viewport: { width: 390, height: 844 } });

  for (const [name, route] of PUBLIC_PAGES) {
    test(`${name} has no visible interactive control without an accessible name`, async ({ page }) => {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await settle(page);
      const nameless = await page.evaluate(() => {
        const out = [];
        for (const el of document.querySelectorAll("a, button, input, select, textarea")) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 && r.height === 0) continue;
          if (getComputedStyle(el).visibility === "hidden") continue;
          if (el.type === "hidden") continue;
          // Inside a COLLAPSED <details>. Showcase uses disclosure widgets for
          // its per-story evidence, and Chromium still reports a non-zero
          // bounding rect for their contents while refusing to render them.
          // Those controls are legitimately not exposed until the reader opens
          // the disclosure, so they are not this assertion's business.
          //
          // This was a real FALSE POSITIVE from this guard's first run: it named
          // seven Showcase links -- "Quality Ledger entry AEQ-012", "Full
          // write-up", "Fix commit 9f35f27" -- as unlabelled. Every one has
          // perfectly good link text. The cause was reading `innerText`, which
          // is layout-dependent and returns "" for an unrendered element; the
          // accessible name comes from text CONTENT, not from rendered text. I
          // checked before changing the page, which is the only reason seven
          // correctly-written links did not get pointless aria-labels bolted on.
          const closedDetails = el.closest("details:not([open])");
          if (closedDetails) continue;
          const accessible = (
            el.textContent || el.getAttribute("aria-label") || el.getAttribute("title") ||
            el.getAttribute("alt") || el.getAttribute("placeholder") || ""
          ).trim();
          const labelled = el.id && document.querySelector(`label[for="${el.id}"]`);
          const wrapped = el.closest("label");
          if (!accessible && !labelled && !wrapped) {
            out.push(`<${el.tagName.toLowerCase()} class="${(el.className || "").toString().slice(0, 40)}">`);
          }
        }
        return out;
      });
      expect(
        nameless,
        `${name}: ${nameless.length} visible control(s) a screen reader would announce ` +
        `as unlabelled: ${nameless.join(", ")}`
      ).toEqual([]);
    });
  }
});
