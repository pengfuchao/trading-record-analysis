/**
 * Smoke tests — golden-path E2E coverage for the trading journal frontend.
 *
 * Strategy:
 *   All backend API calls are intercepted by page.route() before they hit
 *   the network.  This means tests run without a real backend and produce
 *   stable, repeatable results in CI.
 *
 *   The mocked state is: no accounts exist (GET /accounts returns []).
 *   This exercises the "empty / unauthenticated" state of every page — the
 *   minimum bar that each page must clear without crashing.
 *
 * What these tests protect:
 *   - Pages render without JS runtime errors
 *   - Navigation (sidebar links) changes the URL and loads the target page
 *   - Empty / no-account states show a usable message rather than a blank/broken UI
 *   - The onboarding "Create your first account" form appears on the dashboard
 */

import { test, expect, type Page } from "@playwright/test";

const API = "http://localhost:8000";

// ── API mock helpers ──────────────────────────────────────────────────────────

/** Mock the accounts list to return an empty array (no accounts configured). */
async function mockEmptyAccounts(page: Page) {
  await page.route(`${API}/api/v1/accounts`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "[]",
    })
  );
  // Catch-all: any other API call returns 404 so SWR doesn't hang
  await page.route(`${API}/api/v1/**`, (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "not found" }),
    })
  );
  await page.route(`${API}/health`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    })
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

test.describe("Page loads — no crash", () => {
  test.beforeEach(async ({ page }) => {
    await mockEmptyAccounts(page);
  });

  test("dashboard renders onboarding form when no accounts exist", async ({ page }) => {
    await page.goto("/dashboard");
    // CreateAccountCard is shown when accounts list is empty
    await expect(page.getByText("Create your first account")).toBeVisible();
  });

  test("trade log renders without crash", async ({ page }) => {
    await page.goto("/trades");
    await expect(page.getByRole("heading", { name: "Trade Log" })).toBeVisible();
  });

  test("MT5 sync page shows select-account prompt", async ({ page }) => {
    await page.goto("/mt5-sync");
    await expect(page.getByText(/select an account/i)).toBeVisible();
  });

  test("AI Coach page renders without crash", async ({ page }) => {
    await page.goto("/coaching");
    await expect(page.getByRole("heading", { name: /AI Coach/i })).toBeVisible();
  });

  test("Import page renders without crash", async ({ page }) => {
    await page.goto("/import");
    await expect(page.getByRole("heading", { name: /Import/i })).toBeVisible();
  });
});

test.describe("Sidebar navigation", () => {
  test.beforeEach(async ({ page }) => {
    await mockEmptyAccounts(page);
  });

  test("sidebar contains all main navigation links", async ({ page }) => {
    await page.goto("/dashboard");
    const expectedLinks = [
      "Dashboard",
      "Trade Log",
      "Trade Plans",
      "Setups",
      "Daily Plans",
      "AI Coach",
      "Import",
      "MT5 Sync",
    ];
    for (const label of expectedLinks) {
      await expect(page.getByRole("link", { name: label })).toBeVisible();
    }
  });

  test("navigate from dashboard to trade log", async ({ page }) => {
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Trade Log" }).click();
    await expect(page).toHaveURL(/\/trades/);
    await expect(page.getByRole("heading", { name: "Trade Log" })).toBeVisible();
  });

  test("navigate from trade log to MT5 sync", async ({ page }) => {
    await page.goto("/trades");
    await page.getByRole("link", { name: "MT5 Sync" }).click();
    await expect(page).toHaveURL(/\/mt5-sync/);
    await expect(page.getByText(/MT5 Live Sync/i)).toBeVisible();
  });
});
