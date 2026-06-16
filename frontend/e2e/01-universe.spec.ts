import { test, expect } from "@playwright/test";

test("Universum mit 5 Ticker-Symbolen erstellen", async ({ page }) => {
  await page.goto("/universes/new");

  // Eindeutiger Name pro Lauf: ix_universes_name ist UNIQUE, ein fixer Name
  // kollidiert bei lokalen Wiederholungsläufen mit der vorherigen Zeile.
  const universeName = `E2E Test Universum ${Date.now()}`;

  // Fill universe name
  await page.getByLabel("Name").fill(universeName);

  // Fill region
  await page.getByLabel("Region").fill("US");

  // Fill tickers as comma-separated list
  await page.getByLabel("Ticker (kommagetrennt)").fill("AAPL, GOOGL, MSFT, AMZN, TSLA");

  // Submit form
  await page.getByRole("button", { name: /Universum anlegen/i }).click();

  // Dialog erscheint — "Nein" klicken, um zur Universum-Liste zurückzukehren
  await page.getByRole("button", { name: /Nein/i }).click();

  // Should redirect back to universes list
  await expect(page).toHaveURL(/\/universes$/, { timeout: 15_000 });
});
