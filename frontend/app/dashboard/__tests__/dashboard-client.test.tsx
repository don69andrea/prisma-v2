import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

import { DashboardClient } from '../dashboard-client';
import * as runsApi from '@/lib/api/runs';
import * as stocksApi from '@/lib/api/stocks';
import * as universesApi from '@/lib/api/universes';

function wrap(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('DashboardClient — StatsCards-Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders StatsCards with derived stats above runs table', async () => {
    vi.spyOn(runsApi, 'listRuns').mockResolvedValue([
      {
        id: '11111111-1111-1111-1111-111111111111',
        status: 'completed',
        universe_id: 'uni-1',
        created_at: '2026-05-28T10:00:00Z',
      },
    ]);
    vi.spyOn(universesApi, 'listUniverses').mockResolvedValue({
      items: [
        { id: 'uni-1', name: 'Demo-US-5', region: 'US', tickers: ['AAPL', 'MSFT'] },
      ],
      total: 1,
    });
    vi.spyOn(stocksApi, 'listStocks').mockResolvedValue({
      items: Array.from({ length: 5 }, (_, i) => ({
        id: `stock-${i}`,
        ticker: `T${i}`,
        name: `Test ${i}`,
        isin: null,
        sector: null,
        country: null,
        currency: 'USD',
      })),
      total: 5,
    });
    vi.spyOn(runsApi, 'getRankings').mockResolvedValue([
      {
        stock_id: 'stock-1',
        ticker: 'NVDA',
        total_rank: 1,
        weighted_avg: 1.5,
        is_sweet_spot: true,
        per_model_ranks: {},
      } as any,
    ]);

    wrap(<DashboardClient />);
    await waitFor(() => expect(screen.getByText('NVDA')).toBeDefined());
    // 1 Universum
    expect(screen.getByText('1')).toBeDefined();
    // 5 Stocks
    expect(screen.getByText('5')).toBeDefined();
    // Top-Pick-Link
    const link = screen.getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toContain('/stock/NVDA');
  });

  it('renders em-dashes when no completed runs', async () => {
    vi.spyOn(runsApi, 'listRuns').mockResolvedValue([
      {
        id: '11111111-1111-1111-1111-111111111111',
        status: 'pending',
        universe_id: 'uni-1',
        created_at: '2026-05-28T10:00:00Z',
      },
    ]);
    vi.spyOn(universesApi, 'listUniverses').mockResolvedValue({
      items: [],
      total: 0,
    });
    vi.spyOn(stocksApi, 'listStocks').mockResolvedValue({ items: [], total: 0 });

    wrap(<DashboardClient />);
    // Top-Pick-Karte zeigt "—" (kein completed run vorhanden)
    await waitFor(() => {
      const dashes = screen.getAllByText('—');
      expect(dashes.length).toBeGreaterThanOrEqual(1);
    });
  });
});
