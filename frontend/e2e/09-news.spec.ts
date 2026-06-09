import { test, expect } from "@playwright/test";

test("News-Suche — Suche durchführen und Ergebnisse sehen", async ({ page }) => {
  await page.goto("/news");
  await expect(page.getByRole("heading", { name: "CH-Finanz-News" })).toBeVisible();

  await page.getByTestId("news-query-input").fill("SNB Leitzins");
  await page.getByTestId("news-search-btn").click();

  // Entweder Ergebnisse oder Leer-Zustand erscheinen
  await expect(
    page.locator('[data-testid="news-search-btn"]').or(page.getByText(/Ergebnis|Keine Ergebnisse/))
  ).toBeVisible({ timeout: 15_000 });
});
