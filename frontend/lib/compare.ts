import type { RankingItem } from '@/lib/api/runs';

export interface CompareRow {
  ticker: string;
  rankA: number;
  rankB: number;
  scoreA: number;
  scoreB: number;
  deltaRank: number;
  deltaScore: number;
}

export interface CompareStats {
  commonCount: number;
  onlyACount: number;
  onlyBCount: number;
}

function validItems(items: RankingItem[]): Map<string, { rank: number; score: number }> {
  const result = new Map<string, { rank: number; score: number }>();
  for (const item of items) {
    if (item.total_rank !== null && item.weighted_avg !== null) {
      result.set(item.ticker, { rank: item.total_rank, score: item.weighted_avg });
    }
  }
  return result;
}

export function buildCompareRows(
  rankingsA: RankingItem[],
  rankingsB: RankingItem[],
): CompareRow[] {
  const mapA = validItems(rankingsA);
  const mapB = validItems(rankingsB);
  const rows: CompareRow[] = [];

  for (const [ticker, a] of mapA) {
    const b = mapB.get(ticker);
    if (b === undefined) continue;
    rows.push({
      ticker,
      rankA: a.rank,
      rankB: b.rank,
      scoreA: a.score,
      scoreB: b.score,
      deltaRank: a.rank - b.rank,
      deltaScore: b.score - a.score,
    });
  }

  rows.sort((x, y) => x.rankA - y.rankA);
  return rows;
}

export function buildCompareStats(
  rankingsA: RankingItem[],
  rankingsB: RankingItem[],
): CompareStats {
  const mapA = validItems(rankingsA);
  const mapB = validItems(rankingsB);

  let common = 0;
  for (const ticker of mapA.keys()) {
    if (mapB.has(ticker)) common += 1;
  }

  return {
    commonCount: common,
    onlyACount: mapA.size - common,
    onlyBCount: mapB.size - common,
  };
}
