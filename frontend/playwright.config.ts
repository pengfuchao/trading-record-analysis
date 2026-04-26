import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E smoke test configuration.
 *
 * Tests are in frontend/e2e/.  They mock all backend API calls via
 * page.route() so no real backend is required — the Next.js dev server
 * is the only dependency.
 *
 * Run locally:  npm run test:e2e
 * Interactive:  npm run test:e2e:ui
 * CI:           set CI=true and run npm run test:e2e
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 8_000 },
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    // Start Next.js dev server with a placeholder API URL.
    // All requests to that URL are intercepted by page.route() in tests —
    // no real backend is needed.
    command: "NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_URL: "http://localhost:8000",
    },
  },
});
