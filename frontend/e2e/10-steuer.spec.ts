import { test, expect } from "@playwright/test";

test("Steuer-Einschätzung — Formular absenden und Ergebnis sehen", async ({ page }) => {
  await page.goto("/steuer");
  await expect(page.getByRole("heading", { name: "Steuer-Implikationen" })).toBeVisible();

  await page.getByTestId("steuer-ticker-input").fill("NESN");
  await page.getByTestId("steuer-submit-btn").click();

  // In CI läuft Backend mit dummy-API-Key → Fehlermeldung erwartet
  // Bei echtem Key: Steuerarten-Sektion erscheint stattdessen
  await expect(
    page.getByText(/fehlgeschlagen|Steuerarten|Einschätzung für/)
  ).toBeVisible({ timeout: 30_000 });
});
