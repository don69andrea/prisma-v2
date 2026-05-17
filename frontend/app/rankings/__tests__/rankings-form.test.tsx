import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { RankingsForm } from '../rankings-form';
import type { UniverseListResponse } from '@/lib/api/universes';
import type { RunResponse } from '@/lib/api/runs';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockListUniverses = vi.fn();
const mockCreateRun = vi.fn();
vi.mock('@/lib/api/universes', () => ({
  listUniverses: () => mockListUniverses(),
}));
vi.mock('@/lib/api/runs', () => ({
  createRun: (universeId: string) => mockCreateRun(universeId),
}));

const sampleUniverses: UniverseListResponse = {
  total: 2,
  items: [
    { id: 'u-1', name: 'SMI', region: 'CH', tickers: ['NESN', 'NOVN'] },
    { id: 'u-2', name: 'Tech-5', region: 'US', tickers: ['AAPL', 'MSFT'] },
  ],
};

const sampleRun: RunResponse = {
  id: 'run-42',
  status: 'completed',
  universe_id: 'u-1',
  created_at: '2026-05-17T12:00:00Z',
};

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RankingsForm />
    </QueryClientProvider>
  );
}

describe('RankingsForm', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockListUniverses.mockReset();
    mockCreateRun.mockReset();
  });

  it('rendert Universe-Optionen aus listUniverses', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    renderForm();
    await waitFor(() => expect(screen.getByText('SMI')).toBeInTheDocument());
    expect(screen.getByText('Tech-5')).toBeInTheDocument();
  });

  it('disabled Run-Button solange kein Universe gewählt', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    renderForm();
    const button = await screen.findByRole('button', { name: /Run starten/i });
    expect(button).toBeDisabled();
  });

  it('submit ruft createRun und navigiert zur Detail-URL', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    mockCreateRun.mockResolvedValue(sampleRun);
    renderForm();
    await screen.findByText('SMI');
    fireEvent.change(screen.getByLabelText(/Universe/i), { target: { value: 'u-1' } });
    fireEvent.click(screen.getByRole('button', { name: /Run starten/i }));
    await waitFor(() => expect(mockCreateRun).toHaveBeenCalledWith('u-1'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/rankings/run-42'));
  });

  it('zeigt Error-Banner wenn createRun fehlschlägt', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    mockCreateRun.mockRejectedValue(new Error('Backend down'));
    renderForm();
    await screen.findByText('SMI');
    fireEvent.change(screen.getByLabelText(/Universe/i), { target: { value: 'u-1' } });
    fireEvent.click(screen.getByRole('button', { name: /Run starten/i }));
    await waitFor(() => expect(screen.getByText(/Backend down/)).toBeInTheDocument());
  });
});
