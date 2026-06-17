import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CryptoChartSheet } from '../CryptoChartSheet';
import type { CryptoSignal } from '@/lib/api/crypto';

vi.mock('../CryptoHistoryChart', () => ({
  CryptoHistoryChart: ({ ticker }: { ticker: string }) => (
    <div data-testid="mock-history-chart">{ticker}</div>
  ),
}));

vi.mock('../CryptoAgentPanel', () => ({
  CryptoAgentPanel: () => <div data-testid="mock-agent-panel" />,
}));

function makeSignal(overrides: Partial<CryptoSignal> = {}): CryptoSignal {
  return {
    ticker: 'BTC',
    name: 'Bitcoin',
    signal: 'STRONG_BUY',
    score: 84,
    score_components: { momentum: 25, trend: 20, sentiment: 15, markt: 12, risiko: 8 },
    signal_reason_de: 'Starke Aufwärtsdynamik',
    price_chf: 82400,
    market_cap_chf: null,
    price_change_24h_pct: 3.2,
    price_change_7d_pct: 8.1,
    ath_change_pct: -20,
    market_cap_rank: 1,
    rsi_14: 58.3,
    macd_signal: 'bullish',
    volatility_30d_pct: 42,
    correlation_smi_1y: 0.12,
    fear_greed_value: 65,
    fear_greed_label: 'Gier',
    has_six_etp: true,
    timestamp: '2026-06-17T10:00:00Z',
    ...overrides,
  };
}

function renderSheet(signal = makeSignal()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CryptoChartSheet ticker={signal.ticker} signal={signal} />
    </QueryClientProvider>
  );
}

describe('CryptoChartSheet', () => {
  it('rendert Chart-Button mit korrektem data-testid', () => {
    renderSheet();
    expect(screen.getByTestId('chart-sheet-trigger-BTC')).toBeInTheDocument();
  });

  it('Sheet ist initial geschlossen — kein Chart-Inhalt sichtbar', () => {
    renderSheet();
    expect(screen.queryByTestId('mock-history-chart')).not.toBeInTheDocument();
  });

  it('Sheet öffnet sich beim Klick auf den Button', async () => {
    renderSheet();
    fireEvent.click(screen.getByTestId('chart-sheet-trigger-BTC'));
    expect(await screen.findByTestId('mock-history-chart')).toBeInTheDocument();
  });

  it('Chart-Tab zeigt CryptoHistoryChart mit korrektem Ticker', async () => {
    renderSheet();
    fireEvent.click(screen.getByTestId('chart-sheet-trigger-BTC'));
    const chart = await screen.findByTestId('mock-history-chart');
    expect(chart).toHaveTextContent('BTC');
  });

  it('KI-Analyse-Tab zeigt CryptoAgentPanel nach Tab-Wechsel', async () => {
    renderSheet();
    fireEvent.click(screen.getByTestId('chart-sheet-trigger-BTC'));
    await screen.findByTestId('mock-history-chart');
    fireEvent.click(screen.getByRole('tab', { name: /KI-Analyse/i }));
    expect(await screen.findByTestId('mock-agent-panel')).toBeInTheDocument();
  });
});
