import { test, expect } from "./fixtures";

test("Alert anlegen, in Liste sehen und löschen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Set Pro mode so full create form is available
  await page.addInitScript(() => {
    localStorage.setItem('prisma-mode', 'pro');
  });

  // Cleanup: alle bestehenden Alerts löschen
  const listResp = await request.get(`${apiBase}/api/v1/alerts`);
  expect(listResp.ok()).toBeTruthy();
  const listData = await listResp.json() as { alerts: Array<{ id: string }> };
  for (const alert of listData.alerts) {
    await request.delete(`${apiBase}/api/v1/alerts/${alert.id}`);
  }

  // Alerts-Page öffnen
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: /Alerts/i })).toBeVisible();

  // Alert-Formular öffnen (Pro-Modus: erst Button klicken)
  await page.getByRole("button", { name: /Alert erstellen/i }).click();

  // Alert anlegen
  await page.getByPlaceholder("NESN").fill("NOVN");
  await page.getByLabel("Threshold (%)").fill("10");
  await page.locator('select').filter({ hasText: "Kursänderung" }).selectOption("PRICE_CHANGE");
  await page.locator('select').filter({ hasText: "E-Mail" }).selectOption("EMAIL");
  await page.getByPlaceholder("name@example.com").fill(`test-${Date.now()}@example.com`);
  await page.getByRole("button", { name: /Alert anlegen/i }).click();

  // Alert erscheint in der Liste
  await expect(page.getByText("NOVN")).toBeVisible({ timeout: 10_000 });

  // Alert löschen
  await page.getByRole("button", { name: /Alert löschen/i }).first().click();

  // Liste ist wieder leer
  await expect(
    page.getByText("Keine Kursalarme gesetzt")
  ).toBeVisible({ timeout: 10_000 });
});
