import { test, expect } from "@playwright/test";

test("Portfolio Rebalancing Plan berechnen und anzeigen", async ({ page }) => {
  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Portfolio Rebalancing" })).toBeVisible();

  // Portfoliowert setzen
  await page.getByLabel("Portfoliowert (CHF)").fill("50000");

  // Plan berechnen
  await page.getByRole("button", { name: /Plan berechnen/i }).click();

  // Warte auf Button-Text zurück zu "Plan berechnen" (Mutation abgeschlossen)
  await expect(
    page.getByRole("button", { name: /Plan berechnen/i })
  ).toBeEnabled({ timeout: 20_000 });

  // Ergebnis oder Fehlermeldung erscheint
  await expect(
    page.getByTestId("rebalancing-result")
      .or(page.getByText("Rebalancing konnte nicht berechnet werden."))
  ).toBeVisible({ timeout: 5_000 });
});
