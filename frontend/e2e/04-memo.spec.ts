import { test, expect } from "@playwright/test";

const FIXTURE_MEMO = {
  id: "00000000-0000-0000-0000-000000000099",
  stock_id: "11111111-1111-1111-1111-111111111111",
  model_run_id: "00000000-0000-0000-0000-000000000001",
  language: "de",
  one_liner:
    "AAPL ist ein führendes Technologieunternehmen mit starker Marktposition.",
  ranking_interpretation:
    "Die fundamentalen Kennzahlen zeigen solide Profitabilität und stabiles Wachstum.",
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: [],
  key_risks: [],
  confidence: "high",
  model_version: "claude-sonnet-4-6",
  created_at: new Date().toISOString(),
  is_error: false,
};

test("Memo anfordern und Research-Memo anzeigen", async ({ page, request }) => {
  const apiBase = process.env.PLAYWRIGHT_API_URL ?? "http://localhost:8000";

  // Mock memo generation endpoint — avoids LLM cost in CI
  await page.route("**/api/v1/memos/generate", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FIXTURE_MEMO),
    });
  });

  // Setup: universe + run via API
  const universeResp = await request.post(`${apiBase}/api/v1/universes`, {
    data: { name: "E2E Memo", tickers: ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"] },
  });
  const universe = await universeResp.json();
  const runResp = await request.post(`${apiBase}/api/v1/runs`, {
    data: { universe_id: universe.id },
  });
  const run = await runResp.json();

  // Navigate directly to AAPL factsheet
  await page.goto(`/stocks/AAPL?run_id=${run.id}`);
  await expect(page.getByTestId("factsheet-ticker")).toBeVisible();

  // Click "Memo anfordern"
  await page.getByTestId("request-memo-btn").click();

  // Memo card should appear with content
  await expect(page.getByTestId("memo-card")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByTestId("memo-content")).toContainText("AAPL");
});
