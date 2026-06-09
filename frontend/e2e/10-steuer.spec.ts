import { test, expect } from "@playwright/test";

test("Steuer-Einschätzung — Formular absenden und Ergebnis sehen", async ({ page }) => {
  await page.goto("/steuer");
  await expect(page.getByRole("heading", { name: "Steuer-Implikationen" })).toBeVisible();

  await page.getByTestId("steuer-ticker-input").fill("NESN");
  await page.getByTestId("steuer-submit-btn").click();

  // Entweder Ergebnis oder Fehlermeldung erscheinen
  await expect(
    page.getByText(/Verrechnungssteuer|Keine Steuerberatung|fehlgeschlagen/)
  ).toBeVisible({ timeout: 30_000 });
});
