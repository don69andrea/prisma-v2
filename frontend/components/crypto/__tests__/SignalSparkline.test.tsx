import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { SignalSparkline } from '../SignalSparkline';
import type { CryptoHistoryPoint } from '@/lib/api/crypto';

function point(overrides: Partial<CryptoHistoryPoint> = {}): CryptoHistoryPoint {
  return {
    date: '2026-06-15',
    signal: 'BUY',
    score: 60,
    price_chf: 90000,
    fear_greed_value: 30,
    rsi_14: 45,
    detected_patterns: [],
    pattern_score: 0,
    ...overrides,
  };
}

describe('SignalSparkline', () => {
  it('zeigt Platzhalter bei weniger als 2 Datenpunkten', () => {
    render(<SignalSparkline data={[point()]} />);
    expect(screen.getByText('Noch keine Historie')).toBeInTheDocument();
  });

  it('zeigt Aufwärtspfeil wenn letzter Score >= erster Score', () => {
    render(<SignalSparkline data={[point({ score: 50 }), point({ score: 70 })]} />);
    expect(screen.getByText('↑ 70')).toBeInTheDocument();
  });

  it('zeigt Abwärtspfeil wenn letzter Score < erster Score', () => {
    render(<SignalSparkline data={[point({ score: 80 }), point({ score: 40 })]} />);
    expect(screen.getByText('↓ 40')).toBeInTheDocument();
  });
});
