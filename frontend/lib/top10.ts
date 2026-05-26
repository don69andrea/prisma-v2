import type { RankingItem } from '@/lib/api/runs';

/**
 * Sortiert items nach total_rank aufsteigend (nulls zuletzt) und gibt die ersten n zurück.
 * Non-mutating — gibt eine neue Liste zurück.
 */
export function selectTopN(items: RankingItem[], n = 10): RankingItem[] {
  return [...items]
    .sort((a, b) => {
      const ar = a.total_rank ?? Infinity;
      const br = b.total_rank ?? Infinity;
      if (ar === Infinity && br === Infinity) return 0;
      if (ar === Infinity) return 1;
      if (br === Infinity) return -1;
      return ar - br;
    })
    .slice(0, n);
}
