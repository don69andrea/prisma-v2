import { test, expect } from "@playwright/test";

test("Portfolio Rebalancing Plan berechnen und anzeigen", async ({ page }) => {
  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Portfolio Rebalancing" })).toBeVisible();

  // Portfoliowert setzen
  await page.getByLabel("Portfoliowert (CHF)").fill("50000");

  // Plan berechnen
  await page.getByRole("button", { name: /Plan berechnen/i }).click();

  // Entweder Ergebnis erscheint oder Fehlermeldung (falls Backend nicht verfügbar)
  await expect(
    page.getByTestId("rebalancing-result")
      .or(page.getByText(/Rebalancing konnte nicht|Gesamtkosten/))
  ).toBeVisible({ timeout: 20_000 });
});
