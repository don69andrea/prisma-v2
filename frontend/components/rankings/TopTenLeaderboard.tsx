import { selectTopN } from '@/lib/top10';
import type { RankingItem } from '@/lib/api/runs';

import { TopTenCards } from './TopTenCards';
import { TopTenBars } from './TopTenBars';

interface Props {
  items: RankingItem[];
  runId: string;
}

export function TopTenLeaderboard({ items, runId }: Props) {
  if (items.length === 0) return null;
  const topN = selectTopN(items, 10);
  const n = topN.length;

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight">Top {n}</h2>
      <TopTenCards items={topN} runId={runId} />
      <TopTenBars items={topN} runId={runId} />
    </section>
  );
}
