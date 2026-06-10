import { test, expect } from "@playwright/test";

test("VIAC Fonds-Vergleich berechnen und Metriken anzeigen", async ({ page }) => {
  await page.goto("/fonds");
  await expect(page.getByRole("heading", { name: "VIAC Fonds-Vergleich" })).toBeVisible();

  // Fonds-Dropdown laden und ersten Fonds auswählen
  const select = page.locator("select").first();
  await expect(select).not.toBeDisabled({ timeout: 10_000 });
  await select.selectOption({ index: 1 }); // erstes echtes Item (nicht Placeholder)

  // Vergleich starten
  await page.getByRole("button", { name: /Vergleichen/i }).click();

  // Metrik-Vergleich erscheint
  await expect(page.getByText("Erw. Rendite p.a.").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Mein Portfolio").first()).toBeVisible();
  await expect(page.getByText(/Historische Performance/).first()).toBeVisible(); // Disclaimer
});
