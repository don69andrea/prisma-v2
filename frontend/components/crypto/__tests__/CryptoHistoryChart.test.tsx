import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CryptoHistoryChart } from '../CryptoHistoryChart';
import type { CryptoHistoryPoint } from '@/lib/api/crypto';
import { useCryptoHistory } from '@/hooks/useCryptoHistory';

vi.mock('@/hooks/useCryptoHistory');

global.ResizeObserver = vi.fn().mockImplementation(() => ({ observe: vi.fn(), unobserve: vi.fn(), disconnect: vi.fn() }));

function point(overrides: Partial<CryptoHistoryPoint> = {}): CryptoHistoryPoint {
  return {
    date: '2026-06-15',
    signal: 'BUY',
    score: 70,
    price_chf: 82000,
    fear_greed_value: 50,
    rsi_14: 55,
    detected_patterns: [],
    pattern_score: 0,
    ...overrides,
  };
}

function renderChart(ticker = 'BTC') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CryptoHistoryChart ticker={ticker} />
    </QueryClientProvider>
  );
}

describe('CryptoHistoryChart', () => {
  beforeEach(() => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [], loading: false });
  });

  it('zeigt kein chart-testid während Ladezustand', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [], loading: true });
    renderChart();
    expect(screen.queryByTestId('crypto-history-chart')).not.toBeInTheDocument();
  });

  it('zeigt Platzhalter wenn weniger als 2 Datenpunkte vorhanden', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [point()], loading: false });
    renderChart();
    expect(screen.getByTestId('crypto-history-chart')).toBeInTheDocument();
    expect(screen.getByTestId('no-data-placeholder')).toBeInTheDocument();
  });

  it('zeigt Chart-Container wenn 2+ Datenpunkte vorhanden', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({
      data: [point(), point({ date: '2026-06-16', score: 84, price_chf: 85000 })],
      loading: false,
    });
    renderChart();
    expect(screen.getByTestId('crypto-history-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('no-data-placeholder')).not.toBeInTheDocument();
  });

  it('übergibt neuen days-Wert an useCryptoHistory nach Klick auf Zeitraum-Button', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [], loading: false });
    renderChart();
    fireEvent.click(screen.getByTestId('days-btn-90'));
    expect(vi.mocked(useCryptoHistory)).toHaveBeenCalledWith('BTC', 90);
  });

  it('default Zeitraum ist 30 Tage', () => {
    renderChart();
    expect(vi.mocked(useCryptoHistory)).toHaveBeenCalledWith('BTC', 30);
  });
});
