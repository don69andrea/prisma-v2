import { describe, it, expect } from 'vitest';

import { selectTopN } from '../top10';
import type { RankingItem } from '@/lib/api/runs';

function makeItem(ticker: string, rank: number | null, avg: number | null = 0): RankingItem {
  return {
    stock_id: null,
    ticker,
    total_rank: rank,
    weighted_avg: avg,
    is_sweet_spot: false,
    per_model_ranks: {},
  };
}

describe('selectTopN', () => {
  it('leeres Array bleibt leer', () => {
    expect(selectTopN([], 10)).toEqual([]);
  });

  it('sortiert nach total_rank aufsteigend', () => {
    const items = [makeItem('C', 3), makeItem('A', 1), makeItem('B', 2)];
    expect(selectTopN(items, 10).map((i) => i.ticker)).toEqual(['A', 'B', 'C']);
  });

  it('limitiert auf n Items', () => {
    const items = [
      makeItem('A', 1),
      makeItem('B', 2),
      makeItem('C', 3),
      makeItem('D', 4),
      makeItem('E', 5),
    ];
    expect(selectTopN(items, 3).map((i) => i.ticker)).toEqual(['A', 'B', 'C']);
  });

  it('n größer als items.length → gibt alle items zurück', () => {
    const items = [makeItem('A', 1), makeItem('B', 2)];
    expect(selectTopN(items, 10)).toHaveLength(2);
  });

  it('Items mit total_rank=null landen am Ende', () => {
    const items = [
      makeItem('NULL1', null),
      makeItem('A', 1),
      makeItem('NULL2', null),
      makeItem('B', 2),
    ];
    expect(selectTopN(items, 10).map((i) => i.ticker)).toEqual(['A', 'B', 'NULL1', 'NULL2']);
  });

  it('ist non-mutating (Original-Array unverändert)', () => {
    const items = [makeItem('C', 3), makeItem('A', 1), makeItem('B', 2)];
    const originalOrder = items.map((i) => i.ticker);
    selectTopN(items, 10);
    expect(items.map((i) => i.ticker)).toEqual(originalOrder);
  });

  it('Default n=10', () => {
    const items = Array.from({ length: 15 }, (_, i) => makeItem(`T${i}`, i + 1));
    expect(selectTopN(items)).toHaveLength(10);
  });
});
