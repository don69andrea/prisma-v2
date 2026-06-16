import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { MemoPanel } from '../MemoPanel';
import * as memosApi from '@/lib/api/memos';
import type { Memo } from '@/lib/api/memos';

const STOCK_ID = 'aaaa1111-bbbb-cccc-dddd-eeeeeeeeeeee';
const RUN_ID = 'rrrr1111-rrrr-rrrr-rrrr-rrrrrrrrrrrr';

const fakeMemo: Memo = {
  id: 'memo-1',
  stock_id: STOCK_ID,
  model_run_id: RUN_ID,
  language: 'de',
  one_liner: 'Hero one-liner.',
  ranking_interpretation: 'Interpretation.',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: ['S1'],
  key_risks: ['R1'],
  confidence: 'high',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('MemoPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders MemoContent when memo present', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(<MemoPanel stockId={STOCK_ID} runId={RUN_ID} />);
    await waitFor(() => expect(screen.getByText(/Hero one-liner/)).toBeDefined());
  });

  it('renders MemoEmpty when no memo', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    wrap(<MemoPanel stockId={STOCK_ID} runId={RUN_ID} />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /KI-Analyse generieren/ })).toBeDefined(),
    );
  });

  it('renders MemoErrorCard when memo.is_error', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue({ ...fakeMemo, is_error: true });
    wrap(<MemoPanel stockId={STOCK_ID} runId={RUN_ID} />);
    await waitFor(() => expect(screen.getByText(/fehlgeschlagen/i)).toBeDefined());
  });
});
