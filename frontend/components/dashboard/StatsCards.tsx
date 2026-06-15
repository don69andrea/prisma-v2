import Link from 'next/link';
import { Clock, Layers, TrendingUp, Star, Sparkles } from 'lucide-react';

import type { RunResponse, RankingRunStatus } from '@/lib/api/runs';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { InfoPopover } from '@/components/InfoPopover';

const STATUS_LABEL: Record<RankingRunStatus, string> = {
  pending: 'Ausstehend',
  running: 'Läuft',
  completed: 'Abgeschlossen',
  failed: 'Fehler',
};

const STATUS_VARIANT: Record<
  RankingRunStatus,
  'warning' | 'default' | 'success' | 'destructive'
> = {
  pending: 'warning',
  running: 'default',
  completed: 'success',
  failed: 'destructive',
};

export interface TopPick {
  ticker: string;
  isSweetSpot: boolean;
  runId: string;
}

interface Props {
  latestRun: RunResponse | null;
  universeCount: number;
  stockCount: number;
  topPick: TopPick | null;
}

export function StatsCards({ latestRun, universeCount, stockCount, topPick }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Letzter Run */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Clock className="h-4 w-4" />
            <div className="flex items-center gap-1">
              <span>Letzter Run</span>
              <InfoPopover ariaLabel="Info: Letzter Run">
                Wie oft wurde eine Analyse durchgeführt
              </InfoPopover>
            </div>
          </div>
          {latestRun ? (
            <>
              <Link
                href={`/rankings/${latestRun.id}`}
                className="block text-base font-bold hover:underline"
              >
                {new Date(latestRun.created_at).toLocaleDateString('de-CH', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                })}
              </Link>
              <Badge variant={STATUS_VARIANT[latestRun.status]}>
                {STATUS_LABEL[latestRun.status]}
              </Badge>
            </>
          ) : (
            <p className="text-base font-bold">—</p>
          )}
        </CardContent>
      </Card>

      {/* # Universen */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Layers className="h-4 w-4" />
            <span>Universen</span>
          </div>
          <Link href="/universes" className="block text-2xl font-bold hover:underline">
            {universeCount}
          </Link>
        </CardContent>
      </Card>

      {/* # Stocks */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <TrendingUp className="h-4 w-4" />
            <div className="flex items-center gap-1">
              <span>Stocks</span>
              <InfoPopover ariaLabel="Info: Stocks">
                Anzahl der Schweizer Aktien die PRISMA kennt und analysieren kann
              </InfoPopover>
            </div>
          </div>
          <p className="text-2xl font-bold">{stockCount}</p>
        </CardContent>
      </Card>

      {/* Top-Pick */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Star className="h-4 w-4" />
            <div className="flex items-center gap-1">
              <span>Top-Pick</span>
              <InfoPopover ariaLabel="Info: Top-Pick">
                Aktien mit einem PRISMA-Score von mindestens 70 von 100
              </InfoPopover>
            </div>
          </div>
          {topPick ? (
            <Link
              href={`/rankings/${topPick.runId}/stock/${topPick.ticker}`}
              className="inline-flex items-center gap-2 text-xl font-bold hover:underline"
            >
              {topPick.ticker}
              {topPick.isSweetSpot && (
                <Sparkles
                  className="h-4 w-4 text-pink-600 dark:text-pink-400"
                  aria-label="Sweet-Spot"
                />
              )}
            </Link>
          ) : (
            <p className="text-xl font-bold">—</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
