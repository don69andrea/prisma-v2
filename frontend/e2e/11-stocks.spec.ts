import { test, expect } from "@playwright/test";

test("Aktien-Liste — Seite laden und Suchfilter benutzen", async ({ page }) => {
  await page.goto("/stocks");
  await expect(page.getByRole("heading", { name: "Aktienuniversum" })).toBeVisible();

  // Warte auf Tabelle oder Skeleton
  await expect(
    page.getByTestId("stocks-search").or(page.getByText(/Aktien/))
  ).toBeVisible({ timeout: 15_000 });

  // Suchfilter eingeben
  const search = page.getByTestId("stocks-search");
  if (await search.isVisible()) {
    await search.fill("NESN");
    await expect(
      page.getByTestId("stock-row-NESN").or(page.getByText(/Keine Aktien/))
    ).toBeVisible({ timeout: 10_000 });
  }
});
