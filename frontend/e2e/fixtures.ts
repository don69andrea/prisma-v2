const API_BASE = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';

export interface Universe {
  id: string;
  name: string;
  region: string;
  tickers: string[];
}

export async function createTestUniverse(suffix: string): Promise<Universe> {
  const response = await fetch(`${API_BASE}/api/v1/universes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: `e2e-test-${suffix}`,
      region: 'US',
      tickers: ['AAPL', 'MSFT', 'GOOGL'],
    }),
  });
  if (!response.ok) {
    throw new Error(`Universe-Setup fehlgeschlagen: ${response.status} ${await response.text()}`);
  }
  return response.json();
}
