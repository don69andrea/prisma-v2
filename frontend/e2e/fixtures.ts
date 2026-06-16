const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';

// Gegen Instanzen mit gesetztem API_KEY ist /api/v1/universes (wie alle anderen
// Router) global per X-API-Key geschuetzt. Ohne diesen Header schlaegt das
// Fixture-Setup mit 401 fehl, bevor der eigentliche Testfall geprueft wird.
// Ist PLAYWRIGHT_API_KEY nicht gesetzt (z.B. lokale/CI-Umgebungen ohne
// Auth-Enforcement), wird kein Header gesendet.
const API_KEY = process.env.PLAYWRIGHT_API_KEY;

function authHeaders(): Record<string, string> {
  return API_KEY ? { 'X-API-Key': API_KEY } : {};
}

export interface Universe {
  id: string;
  name: string;
  region: string;
  tickers: string[];
}

export async function createTestUniverse(suffix: string): Promise<Universe> {
  const response = await fetch(`${API_BASE}/api/v1/universes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
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
