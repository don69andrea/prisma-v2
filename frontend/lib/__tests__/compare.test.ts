import { describe, it, expect } from 'vitest';

import { buildCompareRows, buildCompareStats, type CompareRow } from '@/lib/compare';
import type { RankingItem } from '@/lib/api/runs';

function item(ticker: string, rank: number, score: number): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: score,
    is_sweet_spot: false,
    per_model_ranks: {},
  };
}

describe('buildCompareRows', () => {
  it('returns only stocks present in both runs', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.9), item('MSFT', 2, 0.8), item('TSLA', 3, 0.7)];
    const b: RankingItem[] = [item('AAPL', 2, 0.85), item('MSFT', 1, 0.92), item('NVDA', 3, 0.7)];

    const rows = buildCompareRows(a, b);

    expect(rows.map((r) => r.ticker)).toEqual(['AAPL', 'MSFT']);
  });

  it('sorts rows by rankA ascending', () => {
    const a: RankingItem[] = [item('MSFT', 2, 0.8), item('AAPL', 1, 0.9)];
    const b: RankingItem[] = [item('MSFT', 1, 0.92), item('AAPL', 2, 0.85)];

    const rows = buildCompareRows(a, b);

    expect(rows[0].ticker).toBe('AAPL');
    expect(rows[1].ticker).toBe('MSFT');
  });

  it('computes deltaRank as rankA - rankB (positive = B better)', () => {
    const a: RankingItem[] = [item('AAPL', 5, 0.5)];
    const b: RankingItem[] = [item('AAPL', 2, 0.7)];

    const [row] = buildCompareRows(a, b);

    expect(row.deltaRank).toBe(3);
  });

  it('computes deltaScore as scoreB - scoreA (positive = B higher)', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.5)];
    const b: RankingItem[] = [item('AAPL', 1, 0.8)];

    const [row] = buildCompareRows(a, b);

    expect(row.deltaScore).toBeCloseTo(0.3, 5);
  });

  it('filters items with null rank or null score', () => {
    const a: RankingItem[] = [
      item('AAPL', 1, 0.9),
      { ticker: 'MSFT', total_rank: null, weighted_avg: 0.8, is_sweet_spot: false, per_model_ranks: {} },
    ];
    const b: RankingItem[] = [
      item('AAPL', 1, 0.9),
      item('MSFT', 2, 0.7),
    ];

    const rows = buildCompareRows(a, b);

    expect(rows.map((r) => r.ticker)).toEqual(['AAPL']);
  });
});

describe('buildCompareStats', () => {
  it('counts common, only-A, only-B', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.9), item('MSFT', 2, 0.8), item('TSLA', 3, 0.7)];
    const b: RankingItem[] = [item('AAPL', 2, 0.85), item('MSFT', 1, 0.92), item('NVDA', 3, 0.7)];

    const stats = buildCompareStats(a, b);

    expect(stats.commonCount).toBe(2);
    expect(stats.onlyACount).toBe(1);
    expect(stats.onlyBCount).toBe(1);
  });

  it('handles empty intersection', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.9)];
    const b: RankingItem[] = [item('MSFT', 1, 0.9)];

    const stats = buildCompareStats(a, b);

    expect(stats.commonCount).toBe(0);
    expect(stats.onlyACount).toBe(1);
    expect(stats.onlyBCount).toBe(1);
  });

  it('ignores items with null rank when counting stats', () => {
    const a: RankingItem[] = [
      item('AAPL', 1, 0.9),
      { ticker: 'PENDING', total_rank: null, weighted_avg: null, is_sweet_spot: false, per_model_ranks: {} },
    ];
    const b: RankingItem[] = [item('AAPL', 1, 0.9)];

    const stats = buildCompareStats(a, b);

    expect(stats.commonCount).toBe(1);
    expect(stats.onlyACount).toBe(0);
    expect(stats.onlyBCount).toBe(0);
  });
});
