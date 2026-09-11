// Smallest robust Playwright Test setup for this project (Phase 2:
// "Owner manual review should verify product quality, not discover basic
// deterministic defects"). Usable in three modes:
//
//   1. Local, against a freshly-started dev server (default):
//        npx playwright test
//      Playwright itself starts `python agent/web_server.py` and waits
//      for it to answer before running -- no manual server juggling.
//
//   2. Local, against a server you already have running:
//        PLAYWRIGHT_BASE_URL=http://127.0.0.1:8420 npx playwright test
//
//   3. Read-only smoke verification against production:
//        PLAYWRIGHT_BASE_URL=https://agentic-platform-backend-production.up.railway.app npx playwright test
//      (webServer auto-start is skipped whenever PLAYWRIGHT_BASE_URL is
//      set, so this never touches the local dev server or port 8420.)
//
// Uses resilient locators (role/text/test-id) and Playwright's built-in
// auto-waiting + web-first assertions throughout -- no arbitrary sleeps,
// no brittle DOM-position CSS/XPath chains. See official Playwright docs
// (playwright.dev/docs/best-practices, docs/locators) for the guidance
// this setup follows.

const { defineConfig, devices } = require("@playwright/test");

const EXTERNAL_BASE_URL = process.env.PLAYWRIGHT_BASE_URL;
const baseURL = EXTERNAL_BASE_URL || "http://127.0.0.1:8420";

module.exports = defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  // Only auto-manage a local server when no external base URL was given
  // -- a production smoke run must never start/stop anything local.
  webServer: EXTERNAL_BASE_URL
    ? undefined
    : {
        command: "python agent/web_server.py",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 30_000,
      },
});
