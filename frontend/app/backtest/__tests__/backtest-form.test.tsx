import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import BacktestPage from '../page';
import type { RunResponse } from '@/lib/api/runs';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

const mockListRuns = vi.fn();
vi.mock('@/lib/api/runs', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/runs')>('@/lib/api/runs');
  return {
    ...actual,
    listRuns: (limit?: number, offset?: number) => mockListRuns(limit, offset),
  };
});

vi.mock('@/lib/api/backtest', () => ({
  runBacktest: vi.fn(),
}));

function makeRun(id: string, status: RunResponse['status'], name = 'Demo-US-5'): RunResponse {
  return {
    id,
    status,
    universe_id: `u-${id}`,
    universe_name: name,
    created_at: '2026-05-29T12:00:00Z',
  };
}

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  mockListRuns.mockReset();
});

describe('Backtest — Run-Dropdown', () => {
  it('bietet nur completed Runs als Optionen an', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed', 'Demo-US-5'),
      makeRun('r2', 'pending', 'Tech-Big-12'),
    ]);

    renderWithClient(<BacktestPage />);

    const select = (await screen.findByTestId('backtest-run-id')) as HTMLSelectElement;
    await waitFor(() => {
      const values = Array.from(select.querySelectorAll('option')).map((o) => o.value);
      expect(values).toContain('r1');
      expect(values).not.toContain('r2');
    });
  });

  it('aktiviert den Start-Button erst nach Run-Auswahl', async () => {
    mockListRuns.mockResolvedValue([makeRun('r1', 'completed')]);

    renderWithClient(<BacktestPage />);

    const btn = await screen.findByTestId('start-backtest-btn');
    expect(btn).toBeDisabled();

    const select = (await screen.findByTestId('backtest-run-id')) as HTMLSelectElement;
    await waitFor(() =>
      expect(Array.from(select.querySelectorAll('option')).map((o) => o.value)).toContain('r1'),
    );
    fireEvent.change(select, { target: { value: 'r1' } });

    await waitFor(() => expect(btn).not.toBeDisabled());
  });

  it('zeigt Empty-State wenn keine completed Runs existieren', async () => {
    mockListRuns.mockResolvedValue([makeRun('r1', 'pending')]);

    renderWithClient(<BacktestPage />);

    await waitFor(() => {
      expect(screen.getByText(/keine abgeschlossenen runs/i)).toBeInTheDocument();
    });
  });
});
