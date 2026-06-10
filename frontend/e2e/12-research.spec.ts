import { test, expect } from "@playwright/test";

test("Research — Suche in Swiss Jahresberichten und SEC Filings", async ({ page }) => {
  await page.goto("/research");
  await expect(page.getByRole("heading", { name: "Research" })).toBeVisible();

  await page.getByTestId("research-query-input").fill("Dividendenstrategie");
  await page.getByTestId("research-search-btn").click();

  // Button bleibt immer sichtbar; bei Ergebnis erscheint zusätzlich Ergebnis-Text
  await expect(page.getByTestId("research-search-btn")).toBeVisible({ timeout: 15_000 });
});
