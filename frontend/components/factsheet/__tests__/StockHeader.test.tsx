import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StockHeader } from '../StockHeader';
import type { StockRead, LatestRankingSnapshot } from '@/lib/api/stocks';

const stock: StockRead = {
  id: 'abc-123',
  ticker: 'AAPL',
  name: 'Apple Inc.',
  isin: 'US0378331005',
  sector: 'Technology',
  country: 'US',
  currency: 'USD',
  exchange: null,
  market_cap_chf: null,
};

const ranking: LatestRankingSnapshot = {
  total_rank: 1,
  weighted_avg: 0.85,
  is_sweet_spot: true,
  per_model_ranks: {},
};

describe('StockHeader', () => {
  it('renders ticker and name', () => {
    render(<StockHeader stock={stock} ranking={null} />);
    expect(screen.getByText('AAPL')).toBeDefined();
    expect(screen.getByText('Apple Inc.')).toBeDefined();
  });

  it('shows Sweet-Spot badge when is_sweet_spot is true', () => {
    render(<StockHeader stock={stock} ranking={ranking} />);
    expect(screen.getByText('Sweet Spot')).toBeDefined();
  });

  it('does not show Sweet-Spot badge when ranking is null', () => {
    render(<StockHeader stock={stock} ranking={null} />);
    expect(screen.queryByText('Sweet Spot')).toBeNull();
  });

  it('shows total rank when ranking is available', () => {
    render(<StockHeader stock={stock} ranking={ranking} />);
    expect(screen.getByText('#1')).toBeDefined();
  });

  it('shows sector and country', () => {
    render(<StockHeader stock={stock} ranking={null} />);
    expect(screen.getByText('Technology')).toBeDefined();
    expect(screen.getByText('US')).toBeDefined();
  });
});
