import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { RankingsTable } from '../[runId]/rankings-table';
import type { RankingItem } from '@/lib/api/runs';

const sampleItems: RankingItem[] = [
  {
    ticker: 'AAPL',
    total_rank: 1,
    weighted_avg: 2.1,
    is_sweet_spot: true,
    per_model_ranks: {
      quality_classic: 1,
      diversification: 3,
      trend_momentum: 2,
      value_alpha_potential: 2,
      alpha: 1,
    },
  },
  {
    ticker: 'MSFT',
    total_rank: 2,
    weighted_avg: 2.4,
    is_sweet_spot: false,
    per_model_ranks: {
      quality_classic: 2,
      diversification: null,
      trend_momentum: 4,
      value_alpha_potential: 1,
      alpha: 3,
    },
  },
];

describe('RankingsTable', () => {
  it('rendert eine Zeile pro Item', () => {
    render(<RankingsTable items={sampleItems} />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('zeigt Sweet-Spot-Badge nur wenn is_sweet_spot=true', () => {
    render(<RankingsTable items={sampleItems} />);
    const badges = screen.queryAllByText('★');
    expect(badges).toHaveLength(1);
  });

  it('zeigt em-dash für null-Werte', () => {
    render(<RankingsTable items={sampleItems} />);
    const dashes = screen.queryAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('rendert Modell-Spalten in fixer Reihenfolge', () => {
    render(<RankingsTable items={sampleItems} />);
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent);
    expect(headers).toEqual([
      '#',
      'Ticker',
      'Avg',
      'Sweet-Spot',
      'Quality',
      'Diversification',
      'Trend',
      'Value',
      'Alpha',
    ]);
  });

  it('zeigt Empty-State wenn items leer', () => {
    render(<RankingsTable items={[]} />);
    expect(screen.getByText(/Keine Ergebnisse/)).toBeInTheDocument();
  });
});
