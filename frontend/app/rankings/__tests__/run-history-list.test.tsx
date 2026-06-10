import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { RunHistoryList } from '../run-history-list';
import type { RunResponse } from '@/lib/api/runs';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockListRuns = vi.fn();
vi.mock('@/lib/api/runs', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/runs')>('@/lib/api/runs');
  return {
    ...actual,
    listRuns: (limit?: number, offset?: number) => mockListRuns(limit, offset),
  };
});

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
  mockPush.mockReset();
});

describe('<RunHistoryList />', () => {
  it('renders empty state when no runs', async () => {
    mockListRuns.mockResolvedValue([]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => {
      expect(screen.getByText(/noch keine Runs/i)).toBeInTheDocument();
    });
  });

  it('renders rows for completed runs', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed', 'Demo-US-5'),
      makeRun('r2', 'completed', 'Tech-Big-12'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => {
      expect(screen.getAllByText('Demo-US-5').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Tech-Big-12').length).toBeGreaterThan(0);
    });
  });

  it('disables checkbox for non-completed runs', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'pending'),
      makeRun('r3', 'failed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes).toHaveLength(3);
      expect(checkboxes[0]).not.toBeDisabled();
      expect(checkboxes[1]).toBeDisabled();
      expect(checkboxes[2]).toBeDisabled();
    });
  });

  it('compare button disabled until 2 selected', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'completed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => screen.getAllByRole('checkbox'));
    const button = screen.getByRole('button', { name: /vergleichen/i });
    expect(button).toBeDisabled();

    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    expect(button).toBeDisabled();

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    expect(button).not.toBeDisabled();
  });

  it('FIFO: third selection removes oldest', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'completed'),
      makeRun('r3', 'completed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => screen.getAllByRole('checkbox'));
    const cbs = screen.getAllByRole('checkbox');

    fireEvent.click(cbs[0]);
    fireEvent.click(cbs[1]);
    fireEvent.click(cbs[2]);

    expect(cbs[0]).not.toBeChecked();
    expect(cbs[1]).toBeChecked();
    expect(cbs[2]).toBeChecked();
  });

  it('navigates to /rankings/compare with selected ids', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'completed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => screen.getAllByRole('checkbox'));
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.click(screen.getAllByRole('checkbox')[1]);

    fireEvent.click(screen.getByRole('button', { name: /vergleichen/i }));

    expect(mockPush).toHaveBeenCalledWith('/rankings/compare?a=r1&b=r2');
  });

  it('zeigt "Datum" als Spaltenheader', async () => {
    mockListRuns.mockResolvedValue([makeRun('r1', 'completed')]);
    renderWithClient(<RunHistoryList />);
    await waitFor(() => expect(screen.getByText('Datum')).toBeInTheDocument());
  });

  it('zeigt deutsche Status-Labels in den Badges', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'pending'),
      makeRun('r3', 'running'),
      makeRun('r4', 'failed'),
    ]);
    renderWithClient(<RunHistoryList />);
    await waitFor(() => {
      expect(screen.getByText('Abgeschlossen')).toBeInTheDocument();
      expect(screen.getByText('Ausstehend')).toBeInTheDocument();
      expect(screen.getByText('Läuft…')).toBeInTheDocument();
      expect(screen.getByText('Fehlgeschlagen')).toBeInTheDocument();
    });
  });
});
