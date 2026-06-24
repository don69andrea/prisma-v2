import { test, expect } from '@playwright/test';

test.describe('Crypto Dashboard', () => {
  test('overview page loads with disclaimer', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByText(/kein Anlagerat/i)).toBeVisible({ timeout: 15000 });
  });

  test('navigation has Krypto-Signale link', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Krypto-Signale' })).toBeVisible();
  });

  test('coin detail page has tabs', async ({ page }) => {
    await page.goto('/crypto/btc');
    await expect(page.getByText('Übersicht & Erklärung')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Chart & Indikatoren')).toBeVisible();
  });
});
