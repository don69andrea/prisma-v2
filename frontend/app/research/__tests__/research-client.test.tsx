import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

// Mock streamChat to avoid real network calls
const mockStreamChat = vi.fn();
vi.mock('@/lib/api/chat', () => ({
  streamChat: (...args: unknown[]) => mockStreamChat(...args),
}));

// Mock RAG (used in the collapsible RAG section)
vi.mock('@/lib/api/rag', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/rag')>('@/lib/api/rag');
  return { ...actual, retrieveSwissFilings: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
});

// Mock macro API — no data → shows demo badge
vi.mock('@/lib/api/macro', () => ({
  getMacroContext: vi.fn().mockRejectedValue(new Error('network error')),
}));

// Force Pro Mode so the right panel (MacroPanel, AgentPanel, MetricsPanel) renders
vi.mock('@/hooks/usePrismaMode', () => ({
  usePrismaMode: () => ({ mode: 'pro', toggle: vi.fn() }),
}));

import { ResearchClient } from '../research-client';

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

beforeEach(() => {
  mockStreamChat.mockReset();
  // Default: streamChat returns a no-op abort function
  mockStreamChat.mockReturnValue(() => {});
});

describe('ResearchClient — Chat-Input', () => {
  it('rendert Input und Senden-Button', () => {
    renderWithClient();
    expect(screen.getByTestId('research-query-input')).toBeInTheDocument();
    expect(screen.getByTestId('research-search-btn')).toBeInTheDocument();
  });

  it('sendet keine Anfrage bei leerem Input', () => {
    renderWithClient();
    fireEvent.click(screen.getByTestId('research-search-btn'));
    expect(mockStreamChat).not.toHaveBeenCalled();
  });

  it('ruft streamChat auf wenn eine Frage gesendet wird', async () => {
    renderWithClient();

    fireEvent.change(screen.getByTestId('research-query-input'), {
      target: { value: 'Soll ich Novartis kaufen?' },
    });
    fireEvent.click(screen.getByTestId('research-search-btn'));

    await waitFor(() => {
      expect(mockStreamChat).toHaveBeenCalledOnce();
      expect(mockStreamChat).toHaveBeenCalledWith(
        'Soll ich Novartis kaufen?',
        [],
        expect.any(Function),
        expect.any(Function),
        expect.any(Function),
      );
    });
  });

  it('zeigt die Nutzerfrage in der Konversation an', async () => {
    renderWithClient();

    fireEvent.change(screen.getByTestId('research-query-input'), {
      target: { value: 'Wie ist der SNB-Leitzins?' },
    });
    fireEvent.click(screen.getByTestId('research-search-btn'));

    await waitFor(() => {
      expect(screen.getByText('Wie ist der SNB-Leitzins?')).toBeInTheDocument();
    });
  });
});

describe('ResearchClient — Makro-Kontext Demo-Badge', () => {
  it('zeigt Beispieldaten-Badge wenn Macro-API nicht erreichbar ist', async () => {
    renderWithClient();
    await waitFor(() => {
      expect(screen.getByTestId('research-macro-demo-badge')).toBeInTheDocument();
    });
  });
});

describe('ResearchClient — Beispielqueries', () => {
  it('zeigt Beispielfragen als Schnellstart-Buttons', () => {
    renderWithClient();
    expect(screen.getByText('Soll ich Novartis kaufen?')).toBeInTheDocument();
    expect(screen.getByText('Wie vermeide ich Klumpenrisiko?')).toBeInTheDocument();
  });

  it('sendet Beispielfrage direkt bei Klick', async () => {
    renderWithClient();
    fireEvent.click(screen.getByText('Soll ich Novartis kaufen?'));
    await waitFor(() => {
      expect(mockStreamChat).toHaveBeenCalledWith(
        'Soll ich Novartis kaufen?',
        [],
        expect.any(Function),
        expect.any(Function),
        expect.any(Function),
      );
    });
  });
});
