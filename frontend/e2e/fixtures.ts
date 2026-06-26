import { test as base, expect, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'fs';

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';

function getAuthToken(): string | undefined {
  try {
    const state = JSON.parse(readFileSync('e2e/.auth-state.json', 'utf-8')) as {
      origins?: Array<{ localStorage?: Array<{ name: string; value: string }> }>;
    };
    return state.origins?.[0]?.localStorage?.find((e) => e.name === 'prisma_token')?.value;
  } catch {
    return undefined;
  }
}

// Extends the built-in `request` fixture to include the JWT Bearer token
// so API calls from E2E tests are authenticated without manual header setup.
export const test = base.extend<{ request: APIRequestContext }>({
  request: async ({ playwright }, use) => {
    const token = getAuthToken();
    const ctx = await playwright.request.newContext({
      extraHTTPHeaders: token ? { Authorization: `Bearer ${token}` } : {},
    });
    await use(ctx);
    await ctx.dispose();
  },
});

export { expect };

export interface Universe {
  id: string;
  name: string;
  region: string;
  tickers: string[];
}

export async function createTestUniverse(suffix: string): Promise<Universe> {
  const token = getAuthToken();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}/api/v1/universes`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      name: `e2e-test-${suffix}`,
      region: 'US',
      tickers: ['AAPL', 'MSFT', 'GOOGL'],
    }),
  });
  if (!response.ok) {
    throw new Error(`Universe-Setup fehlgeschlagen: ${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<Universe>;
}
