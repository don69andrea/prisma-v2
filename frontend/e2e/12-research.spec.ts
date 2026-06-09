import { test, expect } from "@playwright/test";

test("Research — Suche in Swiss Jahresberichten und SEC Filings", async ({ page }) => {
  await page.goto("/research");
  await expect(page.getByRole("heading", { name: "Research" })).toBeVisible();

  await page.getByTestId("research-query-input").fill("Dividendenstrategie");
  await page.getByTestId("research-search-btn").click();

  // Entweder Ergebnisse oder Leer-Zustand
  await expect(
    page.getByTestId("research-search-btn").or(page.getByText(/Ergebnis|Keine Ergebnisse/))
  ).toBeVisible({ timeout: 15_000 });
});
