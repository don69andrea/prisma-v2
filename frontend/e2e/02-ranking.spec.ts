import { test, expect } from "./fixtures";

test("Ranking-Lauf starten und Tabelle mit 5 Zeilen anzeigen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Unique name prevents 500 on Playwright retry (universe already exists)
  const universeName = `E2E Ranking Test ${Date.now()}`;

  // Setup: create universe via API
  const universeResp = await request.post(`${apiBase}/api/v1/universes`, {
    data: {
      name: universeName,
      region: "US",
      tickers: ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
    },
  });
  expect(universeResp.ok()).toBeTruthy();
  const universe = await universeResp.json();

  await page.addInitScript(() => {
    localStorage.setItem('prisma-mode', 'pro');
  });

  await page.goto("/rankings");

  // Select universe from dropdown and start run
  await page.locator("#universe").selectOption(universe.id);
  await page.getByRole("button", { name: /Analyse starten/i }).click();

  // Should navigate to the run detail page
  await expect(page).toHaveURL(/\/rankings\/[0-9a-f-]+$/, { timeout: 90_000 });

  // Verify exactly 5 rows in tbody
  const rows = page.locator("tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 60_000 });
  await expect(rows).toHaveCount(5);
});
