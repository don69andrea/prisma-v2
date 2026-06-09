import { test, expect } from "@playwright/test";

test("Alert anlegen, in Liste sehen und löschen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Setup: sicherstellen dass keine Alerts aus früheren Runs stören
  const listResp = await request.get(`${apiBase}/api/v1/alerts`);
  expect(listResp.ok()).toBeTruthy();

  // Alerts-Page öffnen
  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts" })).toBeVisible();

  // Alert anlegen
  await page.getByPlaceholder("NESN").fill("NOVN");
  await page.getByLabel("Threshold (%)").fill("10");
  await page.locator('select').filter({ hasText: "Kursänderung" }).selectOption("PRICE_CHANGE");
  await page.locator('select').filter({ hasText: "E-Mail" }).selectOption("EMAIL");
  await page.getByPlaceholder("name@example.com").fill("test@example.com");
  await page.getByRole("button", { name: /Alert anlegen/i }).click();

  // Alert erscheint in der Liste
  await expect(page.getByText("NOVN")).toBeVisible({ timeout: 10_000 });

  // Alert löschen (Bestätigung)
  await page.getByRole("button", { name: /Trash/i }).first().click();
  await page.getByRole("button", { name: /Löschen/i }).click();

  // Alert aus Liste verschwunden
  await expect(page.getByText("test@example.com")).not.toBeVisible({ timeout: 5_000 });
});
