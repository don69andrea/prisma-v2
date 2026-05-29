import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { useStockMemo } from '../useStockMemo';
import * as memosApi from '@/lib/api/memos';
import type { Memo } from '@/lib/api/memos';

const STOCK_ID = '11111111-1111-1111-1111-111111111111';
const RUN_ID = '22222222-2222-2222-2222-222222222222';

const fakeMemo: Memo = {
  id: 'memo-1',
  stock_id: STOCK_ID,
  model_run_id: RUN_ID,
  language: 'de',
  one_liner: 'Solide Quality-Geschichte mit Trend-Rückenwind.',
  ranking_interpretation: 'Interpretation.',
  sweet_spot: true,
  sweet_spot_explanation: 'Top-Quintil in allen 5 Modellen.',
  contradictions: [],
  key_strengths: ['Strong ROE', 'Low Debt'],
  key_risks: ['China-Exposure'],
  confidence: 'high',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useStockMemo', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns memo when API returns 200', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    const { result } = renderHook(() => useStockMemo(STOCK_ID, RUN_ID), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.memo).toEqual(fakeMemo);
  });

  it('returns null when API returns 404', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    const { result } = renderHook(() => useStockMemo(STOCK_ID, RUN_ID), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.memo).toBeNull();
  });

  it('does not query when stockId is null', () => {
    const spy = vi.spyOn(memosApi, 'getMemo');
    renderHook(() => useStockMemo(null, RUN_ID), { wrapper });
    expect(spy).not.toHaveBeenCalled();
  });

  it('generate() triggers POST and invalidates query', async () => {
    const getSpy = vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    const genSpy = vi.spyOn(memosApi, 'generateMemo').mockResolvedValue(fakeMemo);

    const { result } = renderHook(() => useStockMemo(STOCK_ID, RUN_ID), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.memo).toBeNull();

    await act(async () => {
      await result.current.generate();
    });

    expect(genSpy).toHaveBeenCalledWith(STOCK_ID, RUN_ID, 'de');
    await waitFor(() => expect(getSpy.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
