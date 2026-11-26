#!/usr/bin/env node
// Record the silent, captioned walkthrough embedded on /kraken (2026-11-26).
//
// It drives a real browser through the public demo: the /kraken map, the
// tour's Ask the Codebase answer, the recorded Workbench run, and the
// prompt-injection suite on /eval. Every page is the real site: nothing is
// mocked, and nothing calls a model (Ask the Codebase is retrieval only; the
// Workbench run is the recorded one). Captions are overlaid during recording.
//
// Run against a local server (python agent/web_server.py) or the live site:
//   node scripts/record_walkthrough.js [baseURL] [runBaseURL, default the live site]
// Output: agent/web/media/walkthrough.webm (+ walkthrough-poster.png, needs ffmpeg)
const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const BASE = (process.argv[2] || "http://127.0.0.1:8420").replace(/\/$/, "");
// The recorded Workbench run lives in the production event ledger, so step 3
// always reads it from the live site (a local server without the ledger has none).
const RUN_BASE = (process.argv[3] || "https://agentic.karthikdevadoss.com").replace(/\/$/, "");
const OUT_DIR = path.join(__dirname, "..", "agent", "web", "media");
const SIZE = { width: 1280, height: 720 };

async function caption(page, text) {
  await page.evaluate((t) => {
    let el = document.getElementById("__wt_caption");
    if (!el) {
      el = document.createElement("div");
      el.id = "__wt_caption";
      el.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);max-width:1000px;" +
        "background:rgba(15,20,25,0.92);color:#fff;font:600 20px/1.4 system-ui,sans-serif;" +
        "padding:12px 20px;border-radius:10px;z-index:2147483647;text-align:center;box-shadow:0 4px 18px rgba(0,0,0,.35)";
      document.body.appendChild(el);
    }
    el.textContent = t;
  }, text);
}

async function glide(page, toY, ms = 2500) {
  await page.evaluate(async ({ toY, ms }) => {
    const from = window.scrollY, steps = Math.max(1, Math.round(ms / 40));
    for (let i = 1; i <= steps; i++) {
      window.scrollTo(0, from + ((toY - from) * i) / steps);
      await new Promise((r) => setTimeout(r, 40));
    }
  }, { toY, ms });
}

const yOf = (page, sel) => page.locator(sel).first().evaluate((el) => el.getBoundingClientRect().top + window.scrollY - 90);

(async () => {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: SIZE, recordVideo: { dir: OUT_DIR, size: SIZE } });
  const page = await context.newPage();

  // 1. The Kraken map.
  await page.goto(`${BASE}/kraken`, { waitUntil: "networkidle" });
  await caption(page, "A live AI platform, mapped to Kraken AI Foundations: Access, Context, Enablement, Governance");
  await page.waitForTimeout(3500);
  await glide(page, await yOf(page, "#tour"), 1500);
  await caption(page, "Three things to try in 60 seconds. All free, all instant.");
  await page.waitForTimeout(3000);

  // 2. Ask the Codebase via the tour's deep link.
  await page.locator(".kr-tour li").first().locator("a").click();
  await page.waitForSelector(".ac-evidence-card", { timeout: 20000 });
  await caption(page, "Ask the Codebase: retrieval over the real repository, with sources. No model call.");
  await page.waitForTimeout(2500);
  await glide(page, await yOf(page, ".ac-evidence-card"), 2000);
  await page.waitForTimeout(3000);

  // 3. The recorded Workbench run.
  await page.goto(`${RUN_BASE}/workbench`, { waitUntil: "networkidle" });
  const runLink = page.locator("#verified-run-link");
  await runLink.waitFor({ state: "visible", timeout: 20000 });
  const runHref = await runLink.getAttribute("href");
  if (!runHref || !runHref.startsWith("/usage/session/")) throw new Error(`no recorded run link (got ${runHref})`);
  await page.goto(RUN_BASE + runHref, { waitUntil: "networkidle" });
  await page.locator("text=VERIFIED PRODUCTION RUN").first().waitFor({ timeout: 20000 });
  await caption(page, "A recorded production run: the agent proposed one exact change and waited for a person");
  await page.waitForTimeout(3500);
  await glide(page, 700, 3000);
  await caption(page, "Approved content only, bound by hash. Then applied, committed, deployed and verified in production.");
  await page.waitForTimeout(2500);
  await glide(page, 1500, 3000);
  await page.waitForTimeout(2000);

  // 4. The eval gate and the prompt-injection red team.
  await page.goto(`${BASE}/eval`, { waitUntil: "networkidle" });
  await caption(page, "Seven eval suites with written thresholds. CI fails the build if a score drops.");
  await page.waitForTimeout(3000);
  const card = page.locator(".suite-card").last();
  await card.scrollIntoViewIfNeeded();
  await glide(page, (await card.evaluate((el) => el.getBoundingClientRect().top + window.scrollY)) - 200, 1500);
  await caption(page, "Suite 7: ten prompt-injection attacks against the real write boundary. All blocked.");
  await page.waitForTimeout(4500);

  const video = page.video();
  await context.close();
  const raw = await video.path();
  fs.renameSync(raw, path.join(OUT_DIR, "walkthrough.webm"));
  await browser.close();
  // Poster = a frame of the opening /kraken screen, not the last frame.
  require("child_process").execFileSync("ffmpeg", ["-loglevel", "error", "-y", "-ss", "2.5", "-i",
    path.join(OUT_DIR, "walkthrough.webm"), "-frames:v", "1", path.join(OUT_DIR, "walkthrough-poster.png")]);
  console.log("wrote agent/web/media/walkthrough.webm and walkthrough-poster.png");
})();
