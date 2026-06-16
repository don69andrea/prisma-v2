import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CryptoProRow } from '../CryptoProRow';
import type { CryptoSignal } from '@/lib/api/crypto';

function makeSignal(overrides: Partial<CryptoSignal> = {}): CryptoSignal {
  return {
    ticker: 'ADA',
    name: 'Cardano',
    signal: 'HOLD',
    score: 50,
    score_components: {
      momentum: 0,
      trend: 0,
      sentiment: 0,
      markt: 0,
      risiko: 0,
    },
    signal_reason_de: '',
    price_chf: 0.35,
    market_cap_chf: null,
    price_change_24h_pct: 1.2,
    price_change_7d_pct: -2.3,
    ath_change_pct: null,
    market_cap_rank: null,
    rsi_14: 55.5,
    macd_signal: 'bullish',
    volatility_30d_pct: 12.3,
    correlation_smi_1y: 0.45,
    fear_greed_value: 50,
    fear_greed_label: 'Neutral',
    has_six_etp: false,
    timestamp: '2026-06-16T00:00:00Z',
    ...overrides,
  };
}

function renderRow(signal: CryptoSignal) {
  return render(
    <table>
      <tbody>
        <CryptoProRow signal={signal} />
      </tbody>
    </table>
  );
}

describe('CryptoProRow', () => {
  it('zeigt Nachkommastellen für Niedrigpreis-Coins (ADA < CHF 1) statt CHF 0', () => {
    renderRow(makeSignal({ ticker: 'ADA', price_chf: 0.35 }));
    expect(screen.queryByText('CHF 0')).not.toBeInTheDocument();
    expect(screen.getByText('CHF 0.35')).toBeInTheDocument();
  });

  it('zeigt 2 Dezimalstellen für XRP-ähnliche Preise (~CHF 1.x)', () => {
    renderRow(makeSignal({ ticker: 'XRP', price_chf: 1.23 }));
    expect(screen.getByText('CHF 1.23')).toBeInTheDocument();
  });

  it('zeigt ganze Zahlen ohne Dezimalstellen für hochpreisige Coins (z.B. BTC)', () => {
    renderRow(makeSignal({ ticker: 'BTC', price_chf: 54321 }));
    expect(screen.getByText("CHF 54'321")).toBeInTheDocument();
  });

  it('zeigt "—" wenn price_chf null ist', () => {
    renderRow(makeSignal({ price_chf: null }));
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
