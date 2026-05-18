import { test, expect } from "@playwright/test";

test("Universum mit 5 Ticker-Symbolen erstellen", async ({ page }) => {
  await page.goto("/universes/new");

  // Fill universe name
  await page.getByLabel("Name").fill("E2E Test Universum");

  // Fill region
  await page.getByLabel("Region").fill("US");

  // Fill tickers as comma-separated list
  await page.getByLabel("Ticker (kommagetrennt)").fill("AAPL, GOOGL, MSFT, AMZN, TSLA");

  // Submit form
  await page.getByRole("button", { name: /Universum anlegen/i }).click();

  // Should redirect back to universes list
  await expect(page).toHaveURL(/\/universes$/, { timeout: 15_000 });
});
