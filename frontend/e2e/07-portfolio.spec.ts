import { test, expect } from "@playwright/test";

test("Portfolio Rebalancing Plan berechnen und anzeigen", async ({ page }) => {
  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Portfolio Rebalancing" })).toBeVisible();

  // Portfoliowert setzen
  await page.getByLabel("Portfoliowert (CHF)").fill("50000");

  // Plan berechnen
  await page.getByRole("button", { name: /Plan berechnen/i }).click();

  // Ergebnistabelle erscheint (mit vorausgefüllten Demo-Positionen)
  await expect(page.getByText("Gesamtkosten")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/BUY|SELL|HOLD/)).toBeVisible();
});
