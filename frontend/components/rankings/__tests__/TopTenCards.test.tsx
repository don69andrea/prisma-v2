import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { TopTenCards } from '../TopTenCards';
import type { RankingItem } from '@/lib/api/runs';

function makeItem(ticker: string, rank: number, sweetSpot = false): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: rank,
    is_sweet_spot: sweetSpot,
    per_model_ranks: {},
  };
}

const items: RankingItem[] = [
  makeItem('AAPL', 1, true),
  makeItem('MSFT', 2, true),
  makeItem('NVDA', 3, false),
];

describe('TopTenCards', () => {
  it('rendert eine Karte pro Item', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
  });

  it('zeigt Rank-Badge mit Hash-Prefix', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
  });

  it('zeigt Sweet-Spot-Stern nur bei is_sweet_spot=true', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    const stars = screen.getAllByLabelText('Sweet-Spot');
    expect(stars).toHaveLength(2); // AAPL + MSFT
  });

  it('Sweet-Spot-Karten haben Amber-Border-Klasse', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    const aaplLink = screen.getByText('AAPL').closest('a');
    expect(aaplLink?.className).toMatch(/border-amber-400/);
    const nvdaLink = screen.getByText('NVDA').closest('a');
    expect(nvdaLink?.className).not.toMatch(/border-amber-400/);
  });

  it('jede Karte ist ein Link zur Factsheet-Route', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    const aaplLink = screen.getByText('AAPL').closest('a');
    expect(aaplLink).toHaveAttribute('href', '/rankings/run-1/stock/AAPL');
  });
});
