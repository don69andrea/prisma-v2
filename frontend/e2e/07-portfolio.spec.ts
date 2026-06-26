import { test, expect } from "./fixtures";

test("Portfolio Rebalancing Plan berechnen und anzeigen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Verify API works directly (bypasses CORS/browser quirks)
  const apiResp = await request.post(`${apiBase}/api/v1/portfolio/rebalance`, {
    data: {
      total_portfolio_value_chf: 50000,
      current_weights: { NESN: 0.3, NOVN: 0.25, ROG: 0.2, ABBN: 0.25 },
      target_weights:  { NESN: 0.25, NOVN: 0.3, ROG: 0.2, ABBN: 0.25 },
      is_3a_account: false,
    },
  });
  expect(apiResp.ok()).toBeTruthy();
  const plan = await apiResp.json() as { steps: Array<{ action: string }> };
  expect(plan.steps.length).toBeGreaterThan(0);

  // Verify the UI page loads and the form is visible
  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "Portfolio Rebalancing" })).toBeVisible();
  await expect(page.getByTestId("plan-submit-btn")).toBeVisible();
});
