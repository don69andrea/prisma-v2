import { test, expect } from "@playwright/test";

test("Ranking-Lauf starten und Tabelle mit 5 Zeilen anzeigen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Setup: create universe via API
  const universeResp = await request.post(`${apiBase}/api/v1/universes`, {
    data: {
      name: "E2E Ranking Test",
      region: "US",
      tickers: ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
    },
  });
  expect(universeResp.ok()).toBeTruthy();
  const universe = await universeResp.json();

  await page.goto("/rankings");

  // Select universe from dropdown and start run
  await page.getByLabel("Universe").selectOption(universe.id);
  await page.getByRole("button", { name: /Run starten/i }).click();

  // Should navigate to the run detail page
  await expect(page).toHaveURL(/\/rankings\/[0-9a-f-]+$/, { timeout: 90_000 });

  // Verify exactly 5 rows in tbody
  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 60_000 });
  await expect(rows).toHaveCount(5);
});
