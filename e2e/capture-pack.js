// Deterministic screenshot + geometry capture for Owner review. Zero model
// calls, zero state mutation.
//
//   node e2e/capture-pack.js --out visual-audit-sprint17-before \
//        --base https://agentic-platform-backend-production.up.railway.app
//   node e2e/capture-pack.js --out visual-audit-sprint17-after \
//        --base http://127.0.0.1:8420
//
// WHAT IT IS AND WHY IT IS NOT A PLAYWRIGHT SPEC
// A spec asserts. This captures. Mixing the two produces a pack that stops
// halfway through on the first assertion failure, which is precisely the wrong
// behaviour for an artefact whose job is to show the Owner every page including
// the broken ones. So this records facts and never fails on what it finds:
// overflow, console errors and a missing primary control are DATA here, and the
// assertions about them live in e2e/ui-standards.spec.js and
// e2e/mobile-overflow.spec.js where a failure is meaningful.
//
// SAFETY, because the BEFORE pack points at real production:
//   * GET/render only. It never clicks, types, submits or authenticates.
//   * It never touches a model-backed control -- no Standing Interview
//     question, no Triage diagnosis, no Workbench requirement, no reset.
//   * Nothing is injected to make a page look better: no cosmetic CSS, no
//     hidden elements, no cropping. fullPage: true, warts included.
//
// DETERMINISTIC SETTLING, not a sleep-and-hope. It waits for networkidle, then
// for document.fonts.ready, then for two consecutive animation frames with an
// unchanged scrollHeight -- so a late-rendering chart or a fetched ledger has
// actually landed before the shutter. A fixed timeout would capture a different
// page on a slow run than on a fast one, and a visual pack whose content depends
// on machine load is not a baseline.

const fs = require("fs");
const path = require("path");
const { chromium } = require("@playwright/test");

const PAGES = [
  ["home", "/"],
  ["workbench", "/workbench"],
  ["triage", "/triage"],
  ["ask-codebase", "/ask-codebase"],
  ["showcase", "/showcase/senior-java-ai-transformation"],
  ["usage", "/usage"],
  ["standing-interview", "/standing-interview"],
  ["case-study", "/case-study/durable-agent"],
  // Sprint 18: the evidence index. It is the sprint's main new surface and
  // the deepest page a technical interviewer reaches, so it is captured at
  // both widths rather than reviewed by description.
  ["proof", "/proof"],
  ["article", "/article/evaluating-the-evaluator"],
  // Not primary recruiter navigation, and captured anyway: it is cheap, it is
  // reachable by URL, and the generic overflow/console data is worth having.
  ["dashboard", "/dashboard"],
];

const VIEWPORTS = [
  { label: "desktop-1920", width: 1920, height: 1080, screenshot: true },
  // 1920x940 exists to measure the first screen on a real laptop where browser
  // chrome eats ~140px. No screenshot -- the geometry is the point, and a second
  // near-identical desktop image per page would triple the pack for nothing.
  { label: "firstscreen-1920x940", width: 1920, height: 940, screenshot: false },
  { label: "mobile-390", width: 390, height: 844, screenshot: true },
];

// Candidate selectors for "the primary next action", most specific first. Its Y
// coordinate is the number the first-screen work is actually about, so it is
// measured rather than eyeballed from a screenshot.
const PRIMARY_CONTROL_SELECTORS = [
  "[data-primary-action]",
  "main form textarea",
  "main form input[type=text]",
  "main form button[type=submit]",
  "main textarea",
  "main input[type=search]",
  "main a.cta, main .cta a, main a.btn-primary",
  "main button",
  "main a",
];

// A third-party font or tracker request on a public page load is a real finding
// (BL-C5). Legitimate same-origin API calls are not, and external links that
// merely exist are not either -- only what the page actually FETCHES counts.
const FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"];
const TRACKER_HOSTS = [
  "google-analytics.com", "googletagmanager.com", "analytics.google.com",
  "doubleclick.net", "facebook.net", "connect.facebook.com",
  "hotjar.com", "segment.io", "segment.com", "mixpanel.com",
  "amplitude.com", "sentry.io", "clarity.ms", "plausible.io",
  "posthog.com", "fullstory.com", "intercom.io", "newrelic.com",
];

function parseArgs() {
  const args = process.argv.slice(2);
  const get = (flag, fallback) => {
    const i = args.indexOf(flag);
    return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
  };
  return {
    out: get("--out", "visual-audit-pack"),
    base: (get("--base", "http://127.0.0.1:8420") || "").replace(/\/$/, ""),
    label: get("--label", ""),
  };
}

async function settle(page) {
  try {
    await page.waitForLoadState("networkidle", { timeout: 20000 });
  } catch {
    // A page that never reaches networkidle (a long-poll, an SSE stream) is not
    // a failure to record -- carry on and let the height check settle it.
  }
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  let last = -1;
  for (let i = 0; i < 25; i++) {
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    if (h === last) return;
    last = h;
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    await page.waitForTimeout(120);
  }
}

async function measure(page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
  }));
  overflow.overflows = overflow.scrollWidth > overflow.clientWidth + 1;

  let primary = null;
  for (const selector of PRIMARY_CONTROL_SELECTORS) {
    const found = await page.evaluate((sel) => {
      const els = Array.from(document.querySelectorAll(sel));
      for (const el of els) {
        const r = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        if (r.width < 24 || r.height < 16) continue;
        if (style.visibility === "hidden" || style.display === "none") continue;
        if (parseFloat(style.opacity || "1") < 0.1) continue;
        return {
          selector: sel,
          text: (el.innerText || el.getAttribute("placeholder") || el.getAttribute("aria-label") || "").trim().slice(0, 80),
          y: Math.round(r.top + window.scrollY),
          height: Math.round(r.height),
        };
      }
      return null;
    }, selector);
    if (found) { primary = found; break; }
  }

  // Elements with no accessible name are a real recruiter-visible defect on a
  // screen reader and a cheap thing to count while the page is already open.
  const emptyAccessibleNames = await page.evaluate(() => {
    const interactive = Array.from(document.querySelectorAll("a, button, input, select, textarea"));
    return interactive.filter((el) => {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) return false;
      const name = (el.innerText || el.getAttribute("aria-label") ||
                    el.getAttribute("title") || el.getAttribute("alt") ||
                    el.getAttribute("placeholder") || "").trim();
      return name === "";
    }).length;
  });

  return { overflow, primary, emptyAccessibleNames };
}

(async () => {
  const { out, base, label } = parseArgs();
  const outDir = path.resolve(out);
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const records = [];

  for (const viewport of VIEWPORTS) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 1,
      // A real recruiter's browser. Not a mobile UA string on the 390 pass --
      // the site has no UA-dependent behaviour and pretending otherwise would
      // capture a page nobody actually sees.
    });

    for (const [name, route] of PAGES) {
      const page = await context.newPage();
      const consoleErrors = [];
      const pageErrors = [];
      const thirdParty = { fonts: [], trackers: [], other: [], sameOrigin: 0 };

      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 300));
      });
      page.on("pageerror", (err) => pageErrors.push(String(err).slice(0, 300)));
      page.on("request", (req) => {
        const url = req.url();
        try {
          const host = new URL(url).host;
          if (url.startsWith(base) || host === new URL(base).host) { thirdParty.sameOrigin++; return; }
          if (FONT_HOSTS.some((h) => host.includes(h))) { thirdParty.fonts.push(url.slice(0, 160)); return; }
          if (TRACKER_HOSTS.some((h) => host.includes(h))) { thirdParty.trackers.push(url.slice(0, 160)); return; }
          thirdParty.other.push(url.slice(0, 160));
        } catch { /* a data: or blob: URL is not a network request */ }
      });

      const url = base + route;
      let status = null;
      let navError = "";
      try {
        const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
        status = resp ? resp.status() : null;
        await settle(page);
      } catch (err) {
        navError = String(err).slice(0, 300);
      }

      let metrics = { overflow: null, primary: null, emptyAccessibleNames: null };
      let file = null;
      if (!navError) {
        metrics = await measure(page);
        if (viewport.screenshot) {
          file = `${viewport.label}-${name}.png`;
          await page.screenshot({ path: path.join(outDir, file), fullPage: true });
        }
      }

      records.push({
        page: name, route, url, viewport: viewport.label,
        width: viewport.width, height: viewport.height,
        status, navError, file,
        overflow: metrics.overflow,
        primaryControl: metrics.primary,
        emptyAccessibleNames: metrics.emptyAccessibleNames,
        consoleErrors, pageErrors,
        thirdPartyFontRequests: thirdParty.fonts,
        trackerRequests: thirdParty.trackers,
        otherThirdPartyRequests: thirdParty.other,
        sameOriginRequests: thirdParty.sameOrigin,
      });

      const flag = navError ? "NAV-ERR"
        : metrics.overflow && metrics.overflow.overflows ? "OVERFLOW"
        : thirdParty.fonts.length ? "3P-FONT" : "ok";
      console.log(
        `${viewport.label.padEnd(22)} ${name.padEnd(20)} ${String(status).padEnd(5)} ` +
        `${flag.padEnd(9)} y=${metrics.primary ? metrics.primary.y : "-"} ` +
        `consoleErr=${consoleErrors.length} 3pFont=${thirdParty.fonts.length}`
      );
      await page.close();
    }
    await context.close();
  }

  await browser.close();

  const manifest = {
    captured_utc: new Date().toISOString(),
    label,
    base_url: base,
    pages: PAGES.map(([n, r]) => ({ name: n, route: r })),
    viewports: VIEWPORTS,
    interaction: "GET/render only. No click, type, submit, auth or model-backed control was touched.",
    model_calls: 0,
    records,
  };
  fs.writeFileSync(path.join(outDir, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log(`\nwrote ${records.length} records and ${records.filter((r) => r.file).length} screenshots to ${outDir}`);
})();
