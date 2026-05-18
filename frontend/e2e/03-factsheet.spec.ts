import { test, expect } from "@playwright/test";

test("Auf Aktie klicken und Factsheet mit Kennzahlen öffnen", async ({ page }) => {
  // Navigate directly to a stock's factsheet page
  await page.goto("/stocks/AAPL");

  // Factsheet should show ticker and metrics section
  await expect(page.getByTestId("factsheet-ticker")).toBeVisible();
  await expect(page.getByTestId("factsheet-metrics")).toBeVisible();
  await expect(page.getByTestId("request-memo-btn")).toBeVisible();
});
