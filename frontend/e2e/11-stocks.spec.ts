import { test, expect } from "@playwright/test";

test("Aktien-Liste — Seite laden und Suchfilter benutzen", async ({ page }) => {
  await page.goto("/stocks");
  await expect(page.getByRole("heading", { name: "Aktienuniversum" })).toBeVisible();

  // Warte bis Suchfeld sichtbar (Seite vollständig geladen)
  await expect(page.getByTestId("stocks-search")).toBeVisible({ timeout: 15_000 });

  // Suchfilter eingeben
  await page.getByTestId("stocks-search").fill("NESN");
  await expect(
    page.getByTestId("stock-row-NESN").or(page.getByText("Keine Aktien entsprechen den Filterkriterien."))
  ).toBeVisible({ timeout: 10_000 });
});
