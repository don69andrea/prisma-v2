import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));
vi.mock('@/hooks/usePrismaMode', () => ({
  usePrismaMode: () => ({ mode: 'simple', isSimple: true, isPro: false, toggle: vi.fn() }),
}));
vi.mock('@/components/GuidedTour', () => ({
  GuidedTourButton: () => null,
}));
vi.mock('@/app/start/start-client', () => ({
  DISCOVER_STORAGE_KEY: 'prisma_discover_cache',
}));

import { DashboardClient } from '../dashboard-client';
import * as decisionsApi from '@/lib/api/decisions';
import * as universesApi from '@/lib/api/universes';

function wrap(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const fakeBuySignal = {
  ticker: 'NVDA',
  snapshot_date: '2026-06-14T00:00:00Z',
  signal: 'BUY' as const,
  confidence: 0.9,
  weighted_score: 88,
  quant_score: 90,
  ml_score: 85,
  macro_score: 80,
  is_3a_eligible: false,
  ml_is_fallback: false,
  signal_reason: 'Starke Fundamentaldaten.',
};

describe('DashboardClient', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders BUY signal card when universe and decisions available', async () => {
    vi.spyOn(universesApi, 'listUniverses').mockResolvedValue({
      items: [{ id: 'uni-1', name: 'SMI', region: 'CH', tickers: ['NESN'] }],
      total: 1,
    });
    vi.spyOn(decisionsApi, 'listDecisions').mockResolvedValue({
      items: [fakeBuySignal],
      total: 1,
    });

    wrap(<DashboardClient />);
    await waitFor(() => expect(screen.getByText('NVDA')).toBeDefined());
    const link = screen.getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toContain('/stocks/NVDA');
  });

  it('zeigt Leer-Zustand wenn kein Universum vorhanden', async () => {
    vi.spyOn(universesApi, 'listUniverses').mockResolvedValue({
      items: [],
      total: 0,
    });

    wrap(<DashboardClient />);
    await waitFor(() => {
      expect(screen.getByText(/Noch keine Signale/)).toBeDefined();
    });
  });
});
