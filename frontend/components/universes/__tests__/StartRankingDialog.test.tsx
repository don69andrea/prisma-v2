import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { StartRankingDialog } from '../StartRankingDialog';
import type { RunResponse } from '@/lib/api/runs';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockCreateRun = vi.fn();
vi.mock('@/lib/api/runs', () => ({
  createRun: (id: string) => mockCreateRun(id),
}));

const sampleRun: RunResponse = {
  id: 'run-99',
  status: 'pending',
  universe_id: 'u-1',
  universe_name: 'SMI',
  created_at: '2026-06-01T10:00:00Z',
};

function renderDialog(universe: { id: string; name: string } | null, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <StartRankingDialog universe={universe} onClose={onClose} />
    </QueryClientProvider>
  );
}

describe('StartRankingDialog', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockCreateRun.mockReset();
  });

  it('rendert nichts wenn universe null ist', () => {
    renderDialog(null);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('zeigt Universum-Namen und Ja/Nein-Buttons', () => {
    renderDialog({ id: 'u-1', name: 'SMI' });
    expect(screen.getByText(/SMI/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ja/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Nein/i })).toBeInTheDocument();
  });

  it('Ja-Klick ruft createRun auf und navigiert zu /rankings/<id>', async () => {
    mockCreateRun.mockResolvedValue(sampleRun);
    renderDialog({ id: 'u-1', name: 'SMI' });
    fireEvent.click(screen.getByRole('button', { name: /Ja/i }));
    await waitFor(() => expect(mockCreateRun).toHaveBeenCalledWith('u-1'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/rankings/run-99'));
  });

  it('Nein-Klick ruft onClose auf', () => {
    const onClose = vi.fn();
    renderDialog({ id: 'u-1', name: 'SMI' }, onClose);
    fireEvent.click(screen.getByRole('button', { name: /Nein/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('zeigt Fehlermeldung wenn createRun fehlschlägt', async () => {
    mockCreateRun.mockRejectedValue(new Error('Backend nicht erreichbar'));
    renderDialog({ id: 'u-1', name: 'SMI' });
    fireEvent.click(screen.getByRole('button', { name: /Ja/i }));
    await waitFor(() =>
      expect(screen.getByText(/Backend nicht erreichbar/)).toBeInTheDocument()
    );
  });

  it('Ja-Button ist disabled und zeigt Spinner während Mutation läuft', async () => {
    mockCreateRun.mockImplementation(() => new Promise(() => {})); // never resolves
    renderDialog({ id: 'u-1', name: 'SMI' });
    fireEvent.click(screen.getByRole('button', { name: /Ja/i }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Ja/i })).toBeDisabled();
      expect(screen.getByRole('button', { name: /Nein/i })).toBeDisabled();
    });
  });
});
