import { test, expect } from '@playwright/test';

import { createTestUniverse } from './fixtures';

test.describe('PRISMA E2E', () => {
  test('1. Startseite lädt und zeigt Navigation', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/PRISMA|Dashboard/);
    // Navigation includes both existing and new links
    await expect(page.getByRole('link', { name: /Rankings/i })).toBeVisible();
    // /discover ("Mein Universum") and /start ("Start") were added to nav
    await expect(page.getByRole('link', { name: /Mein Universum/i })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Start', exact: true })).toBeVisible();
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

    // Dialog erscheint — "Nein" klicken, um zur Universum-Liste zurückzukehren
    await page.getByRole('button', { name: /Nein/i }).click();

    await expect(page).toHaveURL(/\/universes$/);
    await expect(page.getByText(`e2e-flow-${suffix}`)).toBeVisible({ timeout: 10_000 });
  });

  test('4. Dashboard: Seite lädt und Tabelle/Empty-State rendert', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('prisma-mode', 'pro');
    });
    await page.goto('/dashboard');
    await expect(page).toHaveTitle(/Dashboard/);
    await expect(page.getByRole('heading', { name: 'Dashboard.' })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Top Signale heute\./i)).toBeVisible({ timeout: 10_000 });
  });

  test('4. Rankings: Sortierung + CSV-Export', async ({ page }) => {
    const universe = await createTestUniverse(`sort-${Date.now()}`);

    await page.addInitScript(() => {
      localStorage.setItem('prisma-mode', 'pro');
    });

    await page.goto('/rankings');
    await page.locator('#universe').selectOption(universe.id);
    await page.getByRole('button', { name: /Analyse starten/i }).click();

    await expect(page).toHaveURL(/\/rankings\/[0-9a-f-]+$/, { timeout: 90_000 });

    // Wait for table to render
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 60_000 });

    // Avg header starts without active sort
    const avgHeader = page.getByRole('columnheader', { name: /Avg/ });
    await expect(avgHeader).toHaveAttribute('aria-sort', 'none');

    // First click → ascending
    await avgHeader.click();
    await expect(avgHeader).toHaveAttribute('aria-sort', 'ascending');

    // Second click → descending
    await avgHeader.click();
    await expect(avgHeader).toHaveAttribute('aria-sort', 'descending');

    // CSV export triggers download
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: /CSV exportieren/i }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('rankings.csv');
  });

  test('3. Ranking-Flow: Run starten und Ergebnis-Tabelle sehen', async ({ page }) => {
    const universe = await createTestUniverse(`run-${Date.now()}`);

    await page.addInitScript(() => {
      localStorage.setItem('prisma-mode', 'pro');
    });

    await page.goto('/rankings');
    await expect(page.getByRole('heading', { name: /Rankings/i })).toBeVisible();

    await page.locator('#universe').selectOption(universe.id);
    await page.getByRole('button', { name: /Analyse starten/i }).click();

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
