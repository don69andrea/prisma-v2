import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
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

// jsdom does not implement scrollIntoView; the agent-log panel calls it on
// every log update to auto-scroll, which is irrelevant to this test's scope.
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

function renderWithClient() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ResearchClient />
    </QueryClientProvider>,
  );
}

function switchToProMode() {
  const toggle = screen.getByRole('button', { name: /simple mode|pro mode/i });
  if (toggle.textContent?.includes('Simple Mode')) {
    fireEvent.click(toggle);
  }
}

beforeEach(() => {
  localStorage.clear();
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

describe('ResearchClient — Pro Mode Mock-Daten-Kennzeichnung', () => {
  it('zeigt ein Demo-Label bei den Quellen, wenn keine echten Quellen vorliegen', () => {
    renderWithClient();
    switchToProMode();

    // Ohne ausgeführte Suche sind allSources leer -> MOCK_SOURCES + Demo-Badge sichtbar
    expect(screen.getByTestId('research-sources-demo-badge')).toBeInTheDocument();
    expect(screen.getByText('Novartis GB 2025')).toBeInTheDocument();
  });

  it('zeigt ein Demo-Label beim Makro-Kontext-Panel', () => {
    renderWithClient();
    switchToProMode();

    expect(screen.getByTestId('research-macro-demo-badge')).toBeInTheDocument();
  });

  it('blendet das Quellen-Demo-Label aus, sobald echte RAG-Ergebnisse vorliegen', async () => {
    mockRetrieveSwissFilings.mockResolvedValue({
      results: [
        {
          chunk_id: 'c1',
          chunk_idx: 0,
          url: 'https://example.com/report.pdf',
          ticker: 'NOVN',
          source: 'SIX',
          language: 'de',
          filing_date: '2025-03-01',
          doc_type: 'Geschäftsbericht',
          content: 'Inhalt...',
          similarity: 0.91,
        },
      ],
      total: 1,
    });
    mockRetrieveSecFilings.mockResolvedValue({ results: [], total: 0 });

    renderWithClient();
    switchToProMode();

    const input = screen.getByTestId('research-query-input');
    fireEvent.change(input, { target: { value: 'Novartis fundamental?' } });
    fireEvent.click(screen.getByTestId('research-search-btn'));

    expect(await screen.findByText(/NOVN/)).toBeInTheDocument();
    expect(screen.queryByTestId('research-sources-demo-badge')).not.toBeInTheDocument();
  });
});
