import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { MemoSheet } from '../MemoSheet';
import * as memosApi from '@/lib/api/memos';
import type { Memo } from '@/lib/api/memos';

const STOCK_ID = '11111111-1111-1111-1111-111111111111';
const RUN_ID = '22222222-2222-2222-2222-222222222222';

const fakeMemo: Memo = {
  id: 'memo-1',
  stock_id: STOCK_ID,
  model_run_id: RUN_ID,
  language: 'de',
  one_liner: 'Solider Pick.',
  ranking_interpretation: 'Top-Quintil.',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: ['Strong ROE'],
  key_risks: ['Volatility'],
  confidence: 'medium',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('MemoSheet', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders ticker in header when open', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(
      <MemoSheet
        stockId={STOCK_ID}
        runId={RUN_ID}
        ticker="AAPL"
        open={true}
        onOpenChange={() => {}}
      />,
    );
    await waitFor(() => expect(screen.getByText('AAPL')).toBeDefined());
  });

  it('renders MemoContent when memo loaded', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() => expect(screen.getByText(/Solider Pick/)).toBeDefined());
  });

  it('renders MemoEmpty when memo is null', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Memo generieren/ })).toBeDefined(),
    );
  });

  it('renders MemoErrorCard when memo.is_error', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue({ ...fakeMemo, is_error: true });
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() => expect(screen.getByText(/fehlgeschlagen/i)).toBeDefined());
  });

  it('renders nothing when stockId is null', () => {
    wrap(
      <MemoSheet stockId={null} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    expect(screen.queryByText('AAPL')).toBeNull();
  });

  it('shows factsheet-link in footer', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() => {
      const link = screen.getByRole('link', { name: /Vollständiges Factsheet/ });
      expect(link.getAttribute('href')).toBe(`/rankings/${RUN_ID}/stock/AAPL`);
    });
  });
});
