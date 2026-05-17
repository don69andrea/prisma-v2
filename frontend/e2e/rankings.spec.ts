import { test, expect } from '@playwright/test';

import { createTestUniverse } from './fixtures';

test.describe('PRISMA E2E', () => {
  test('1. Startseite lädt und zeigt Navigation', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/PRISMA|Dashboard/);
    await expect(page.getByRole('link', { name: /Universen/i })).toBeVisible();
  });

  test('2. Universe-Flow: neues Universum anlegen', async ({ page }) => {
    await page.goto('/universes');
    await page.getByRole('link', { name: /Neues Universum/i }).click();
    await expect(page).toHaveURL(/\/universes\/new/);

    const suffix = Date.now();
    await page.getByLabel('Name').fill(`e2e-flow-${suffix}`);
    await page.getByLabel('Region').fill('US');
    await page.getByLabel(/Ticker/i).fill('AAPL, MSFT');
    await page.getByRole('button', { name: /Universum anlegen/i }).click();

    await expect(page).toHaveURL(/\/universes$/);
    await expect(page.getByText(`e2e-flow-${suffix}`)).toBeVisible({ timeout: 10_000 });
  });

  test('3. Ranking-Flow: Run starten und Ergebnis-Tabelle sehen', async ({ page }) => {
    const universe = await createTestUniverse(`run-${Date.now()}`);

    await page.goto('/rankings');
    await expect(page.getByRole('heading', { name: /Ranking starten/i })).toBeVisible();

    await page.getByLabel('Universe').selectOption(universe.id);
    await page.getByRole('button', { name: /Run starten/i }).click();

    await expect(page).toHaveURL(/\/rankings\/[0-9a-f-]+$/, { timeout: 90_000 });
    await expect(page.getByRole('heading', { name: /Ranking-Ergebnis/i })).toBeVisible();

    // Mindestens eine Datenzeile (Header + ≥1 Body-Row)
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 60_000 });
    expect(await rows.count()).toBeGreaterThanOrEqual(1);

    // Erste Ticker-Spalte enthält einen unserer Test-Tickers
    const firstTickerCell = page.locator('tbody tr td.font-mono').first();
    await expect(firstTickerCell).toHaveText(/^(AAPL|MSFT|GOOGL)$/);
  });
});
