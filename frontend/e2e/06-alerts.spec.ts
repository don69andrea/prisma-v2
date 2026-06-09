import { test, expect } from "@playwright/test";

test("Alert anlegen, in Liste sehen und löschen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Cleanup: alle bestehenden Alerts löschen um Datenverschmutzung zu verhindern
  const listResp = await request.get(`${apiBase}/api/v1/alerts`);
  expect(listResp.ok()).toBeTruthy();
  const listData = await listResp.json() as { alerts: Array<{ id: string }> };
  for (const alert of listData.alerts) {
    await request.delete(`${apiBase}/api/v1/alerts/${alert.id}`);
  }

  // Eindeutige E-Mail pro Test-Run verwenden
  const uniqueEmail = `test-${Date.now()}@example.com`;

  // Alerts-Page öffnen
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts" })).toBeVisible();

  // Alert anlegen
  await page.getByPlaceholder("NESN").fill("NOVN");
  await page.getByLabel("Threshold (%)").fill("10");
  await page.locator('select').filter({ hasText: "Kursänderung" }).selectOption("PRICE_CHANGE");
  await page.locator('select').filter({ hasText: "E-Mail" }).selectOption("EMAIL");
  await page.getByPlaceholder("name@example.com").fill(uniqueEmail);
  await page.getByRole("button", { name: /Alert anlegen/i }).click();

  // Alert erscheint in der Liste
  await expect(page.getByText("NOVN")).toBeVisible({ timeout: 10_000 });

  // Alert löschen (Bestätigung)
  await page.getByRole("button", { name: /Alert löschen/i }).first().click();
  await page.getByRole("button", { name: /^Löschen$/ }).click();

  // Alert aus Liste verschwunden (nur noch der soeben gelöschte)
  await expect(page.getByText(uniqueEmail)).not.toBeVisible({ timeout: 5_000 });
});
