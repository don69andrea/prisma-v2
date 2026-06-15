import { test, expect } from '@playwright/test';

test.describe('Krypto-Seite', () => {
  test('Seite lädt und zeigt Header', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByRole('heading', { name: 'Krypto.' })).toBeVisible();
  });

  test('Fear & Greed Bereich ist sichtbar', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByText('Crypto Fear & Greed Index')).toBeVisible();
  });

  test('Disclaimer ist immer sichtbar', async ({ page }) => {
    await page.goto('/crypto');
    await expect(page.getByText(/Kein 3a-Instrument/)).toBeVisible();
  });

  test('Nav-Link Krypto. ist in ANALYSIEREN sichtbar', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('link', { name: 'Krypto.' })).toBeVisible();
  });

  test('Nav-Link führt zu /crypto', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Krypto.' }).click();
    await expect(page).toHaveURL('/crypto');
  });
});
