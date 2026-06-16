import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/hooks/usePrismaMode', () => ({
  usePrismaMode: () => ({ mode: 'simple', isSimple: true, isPro: false, toggle: vi.fn() }),
}));

const mockRetrieveSwissFilings = vi.fn();
const mockRetrieveSecFilings = vi.fn();
vi.mock('@/lib/api/rag', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/rag')>('@/lib/api/rag');
  return {
    ...actual,
    retrieveSwissFilings: (...args: unknown[]) => mockRetrieveSwissFilings(...args),
    retrieveSecFilings: (...args: unknown[]) => mockRetrieveSecFilings(...args),
  };
});

import { ResearchClient } from '../research-client';

function renderWithClient() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ResearchClient />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  mockRetrieveSwissFilings.mockReset();
  mockRetrieveSecFilings.mockReset();
  mockRetrieveSwissFilings.mockResolvedValue({ results: [], total: 0 });
  mockRetrieveSecFilings.mockResolvedValue({ results: [], total: 0 });
});

describe('ResearchClient — Query-Validierung', () => {
  it('zeigt Fehlermeldung und löst keine Mutation aus, wenn die Suchanfrage zu kurz ist', async () => {
    renderWithClient();

    const input = screen.getByTestId('research-query-input');
    const btn = screen.getByTestId('research-search-btn');

    fireEvent.change(input, { target: { value: 'ab' } });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByTestId('research-validation-error')).toHaveTextContent(
        /mindestens 3 zeichen/i,
      );
    });
    expect(mockRetrieveSwissFilings).not.toHaveBeenCalled();
    expect(mockRetrieveSecFilings).not.toHaveBeenCalled();
  });

  it('löst die Mutation aus, wenn die Suchanfrage mindestens 3 Zeichen hat', async () => {
    renderWithClient();

    const input = screen.getByTestId('research-query-input');
    const btn = screen.getByTestId('research-search-btn');

    fireEvent.change(input, { target: { value: 'Novartis Dividende' } });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockRetrieveSwissFilings).toHaveBeenCalled();
      expect(mockRetrieveSecFilings).toHaveBeenCalled();
    });
    expect(screen.queryByTestId('research-validation-error')).not.toBeInTheDocument();
  });

  it('zeigt keine Fehlermeldung initial an', () => {
    renderWithClient();
    expect(screen.queryByTestId('research-validation-error')).not.toBeInTheDocument();
  });
});
