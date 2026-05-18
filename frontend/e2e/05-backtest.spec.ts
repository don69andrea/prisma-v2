import { test, expect } from "@playwright/test";

test("Backtest starten und Chart mit 3 Kurven anzeigen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Setup: universe + ranking run via API
  const universeResp = await request.post(`${apiBase}/api/v1/universes`, {
    data: { name: "E2E Backtest", region: "US", tickers: ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"] },
  });
  const universe = await universeResp.json();
  const runResp = await request.post(`${apiBase}/api/v1/runs`, {
    data: { universe_id: universe.id },
  });
  const run = await runResp.json();

  // Navigate to backtest page with run_id
  await page.goto(`/backtest?run_id=${run.id}`);

  // Set dates within stub provider range (last ~2 years from today 2026-05-17)
  await page.getByTestId("backtest-start-date").fill("2025-01-01");
  await page.getByTestId("backtest-end-date").fill("2025-12-31");
  await page.getByTestId("backtest-top-n").fill("3");

  // Start backtest
  await page.getByTestId("start-backtest-btn").click();

  // Chart with 3 curves should appear
  const chart = page.getByTestId("backtest-chart");
  await expect(chart).toBeVisible({ timeout: 60_000 });

  // Verify 3 legend labels are rendered
  await expect(chart.getByText("PRISMA")).toBeVisible();
  await expect(chart.getByText("Universum")).toBeVisible();
  await expect(chart.getByText("Benchmark")).toBeVisible();
});
