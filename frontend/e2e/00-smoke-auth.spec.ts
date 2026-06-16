import { test, expect } from "@playwright/test";

// Regression-Test für den Vorfall vom 16.06.2026: frontend/.env.local fehlte,
// NEXT_PUBLIC_API_KEY war undefined, jeder Request ging ohne X-API-Key raus.
// ApiStatusBadge zeigte trotzdem grün, weil sie nur /health pingte (ungeschützt).
// Dieser Test prüft den tatsächlichen Datenpfad: echte Inhalte sichtbar UND
// keine 401-Responses von der API — beides hätte den Vorfall sofort gefangen.

test("Stocks-Liste lädt echte Daten ohne 401 von der API", async ({ page }) => {
  const unauthorized: string[] = [];
  page.on("response", (res) => {
    if (res.url().includes("/api/v1/") && res.status() === 401) {
      unauthorized.push(res.url());
    }
  });

  await page.goto("/stocks");

  // Mindestens eine Aktien-Zeile muss real gerendert werden — kein leerer/Error-State.
  await expect(page.locator('[data-testid^="stock-row-"]').first()).toBeVisible({
    timeout: 15_000,
  });

  expect(unauthorized).toEqual([]);
});

test("Dashboard lädt Decisions/Universes ohne 401 von der API", async ({ page }) => {
  const unauthorized: string[] = [];
  page.on("response", (res) => {
    if (res.url().includes("/api/v1/") && res.status() === 401) {
      unauthorized.push(res.url());
    }
  });

  await page.goto("/dashboard");
  await page.waitForLoadState("networkidle");

  expect(unauthorized).toEqual([]);
});
