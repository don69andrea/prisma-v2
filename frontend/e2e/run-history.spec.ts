import { test, expect } from './fixtures';

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';

test.describe('Run-History', () => {
  test('list, select two, compare', async ({ page, request }) => {
    // Precondition: ≥2 completed runs in DB
    const runsRes = await request.get(`${API_BASE}/api/v1/runs?limit=10`);
    if (!runsRes.ok()) {
      test.skip(true, `Backend API returned ${runsRes.status()}, cannot verify precondition.`);
      return;
    }
    const runs: Array<{ id: string; status: string; universe_name: string }> = await runsRes.json();
    const completed = runs.filter((r) => r.status === 'completed');

    if (completed.length < 2) {
      test.skip(true, `Need ≥2 completed runs in DB, found ${completed.length}. Start runs via UI first.`);
      return;
    }

    // 1. Navigate to /rankings (Pro mode required for run-history component)
    await page.addInitScript(() => {
      localStorage.setItem('prisma-mode', 'pro');
    });
    await page.goto('/rankings');

    // 2. "Vergangene Runs" section visible
    await expect(page.getByText('Vergangene Runs')).toBeVisible({ timeout: 15_000 });

    // 3. Wait for run list to load — React Query populates runsQuery.data async.
    // Any checkbox appearing (even disabled) proves the list has rendered.
    // Without this, selectOption runs on an empty list → filter shows 0 rows.
    await expect(page.locator('input[type="checkbox"]').first()).toBeVisible({ timeout: 20_000 });

    // 4. Filter by completed status — newest runs may be pending/running (disabled checkboxes)
    await page.locator('[data-testid="run-history-status-filter"]').selectOption('completed');

    // 5. Click first 2 enabled checkboxes
    const enabledCheckboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await expect(enabledCheckboxes.first()).toBeVisible({ timeout: 15_000 });
    await enabledCheckboxes.nth(0).check();
    await enabledCheckboxes.nth(1).check();

    // 6. "Vergleichen" button now enabled
    const compareBtn = page.getByRole('button', { name: /vergleichen/i });
    await expect(compareBtn).toBeEnabled();
    await compareBtn.click();

    // 7. URL matches compare-page format
    await expect(page).toHaveURL(/\/rankings\/compare\?a=[0-9a-f-]+&b=[0-9a-f-]+/, { timeout: 10_000 });

    // 8. Both run headers visible
    await expect(page.getByText('Run A', { exact: true })).toBeVisible();
    await expect(page.getByText('Run B', { exact: true })).toBeVisible();

    // 9. Either a comparison table OR the "no common stocks" warning is visible
    const hasTable = await page.locator('table tbody tr').first().isVisible().catch(() => false);
    const hasWarning = await page.getByText(/keine gemeinsamen Stocks/i).isVisible().catch(() => false);
    expect(hasTable || hasWarning).toBeTruthy();
  });
});
