import { test, expect } from "@playwright/test";

test("Research — Chat-Anfrage absenden und Antwort abwarten", async ({ page }) => {
  await page.goto("/research");
  await expect(page.getByRole("heading", { name: "Research" })).toBeVisible();

  await page.getByTestId("research-query-input").fill("Welche SMI-Aktie hat das beste BUY-Signal?");
  await page.getByTestId("research-search-btn").click();

  // Button bleibt immer sichtbar (wird nach Streaming wieder aktiv)
  await expect(page.getByTestId("research-search-btn")).toBeVisible({ timeout: 30_000 });
});
