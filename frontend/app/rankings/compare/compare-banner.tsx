import { AlertTriangle } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import type { CompareStats } from '@/lib/compare';
import type { RunResponse } from '@/lib/api/runs';

const DATE_FMT = new Intl.DateTimeFormat('de-CH', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

interface Props {
  runA: RunResponse;
  runB: RunResponse;
  stats: CompareStats;
}

export function CompareBanner({ runA, runB, stats }: Props) {
  const sameUniverse = runA.universe_id === runB.universe_id;

  return (
    <Card>
      <CardContent className="py-4 space-y-3">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground text-xs">Run A</div>
            <div className="font-medium">{runA.universe_name}</div>
            <div className="text-muted-foreground text-xs">
              {DATE_FMT.format(new Date(runA.created_at))}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Run B</div>
            <div className="font-medium">{runB.universe_name}</div>
            <div className="text-muted-foreground text-xs">
              {DATE_FMT.format(new Date(runB.created_at))}
            </div>
          </div>
        </div>

        {stats.commonCount === 0 ? (
          <div className="flex items-center gap-2 rounded-md bg-amber-50 dark:bg-amber-950 px-3 py-2 text-sm text-amber-900 dark:text-amber-200">
            <AlertTriangle className="h-4 w-4" />
            <span>Keine gemeinsamen Stocks — Vergleich nicht möglich.</span>
          </div>
        ) : sameUniverse ? (
          <div className="text-sm text-muted-foreground">
            {`${stats.commonCount} gemeinsame Stocks verglichen`}
          </div>
        ) : (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="text-foreground">{`${stats.commonCount} gemeinsam`}</span>
            <span>{`${stats.onlyACount} nur in Run A`}</span>
            <span>{`${stats.onlyBCount} nur in Run B`}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
