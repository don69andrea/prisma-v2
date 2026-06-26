import { test, expect } from '@playwright/test';

test.describe('Crypto Dashboard', () => {
  test('overview page loads with disclaimer', async ({ page }) => {
    await page.route('**/api/v1/crypto/signals', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });
    await page.route('**/api/v1/crypto/fear-greed', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ value: 50, label: 'Neutral', timestamp: '1700000000' }) });
    });
    await page.goto('/crypto');
    await expect(page.getByText(/keine Anlageberatung/i)).toBeVisible({ timeout: 15000 });
  });

  test('navigation has Krypto link', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Krypto' })).toBeVisible();
  });

  test('coin detail page has tabs', async ({ page }) => {
    await page.goto('/crypto/btc');
    await expect(page.getByText('Übersicht & Erklärung')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Chart & Indikatoren')).toBeVisible();
  });
});
