'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { XCircle, ArrowLeft, Loader2, Download } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { getRun, getRankings, statusLabel, getRankingsCsvUrl } from '@/lib/api/runs';
import { getUniverse } from '@/lib/api/universes';
import { listStocks } from '@/lib/api/stocks';
import { ApiError } from '@/lib/api/client';

import { RankingsTable } from './rankings-table';
import { TopTenLeaderboard } from '@/components/rankings/TopTenLeaderboard';


function TableSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
      ))}
    </div>
  );
}

export default function RankingDetailPage({ params }: { params: { runId: string } }) {
  const runQuery = useQuery({
    queryKey: ['run', params.runId],
    queryFn: () => getRun(params.runId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === 'pending' || status === 'running' ? 5000 : false;
    },
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });

  const isCompleted = runQuery.data?.status === 'completed';

  const rankingsQuery = useQuery({
    queryKey: ['rankings', params.runId],
    queryFn: () => getRankings(params.runId),
    enabled: isCompleted,
  });

  const universeQuery = useQuery({
    queryKey: ['universe', runQuery.data?.universe_id ?? null],
    queryFn: () => getUniverse(runQuery.data!.universe_id),
    enabled: !!runQuery.data?.universe_id,
  });

  const stocksQuery = useQuery({
    queryKey: ['stocks-xswx'],
    queryFn: () => listStocks(200, 0, 'XSWX'),
    staleTime: 5 * 60 * 1000,  // 5 min cache
  });

  const swissTickers = useMemo(
    () => new Set(stocksQuery.data?.items.map((s) => s.ticker) ?? []),
    [stocksQuery.data],
  );

  const is404 = runQuery.error instanceof ApiError && runQuery.error.status === 404;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <Link
            href="/rankings"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Zurück zu Rankings
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">Ranking-Ergebnis</h1>
        </div>
        {isCompleted && rankingsQuery.data && (
          <a
            href={getRankingsCsvUrl(params.runId)}
            download
            data-testid="csv-download-btn"
          >
            <Button variant="outline" size="sm">
              <Download className="mr-1 h-4 w-4" />
              CSV
            </Button>
          </a>
        )}
      </div>

      {is404 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-lg font-medium">Run nicht gefunden</p>
            <p className="text-sm text-muted-foreground mt-1">Run-ID: {params.runId}</p>
          </CardContent>
        </Card>
      )}

      {!is404 && runQuery.data && (
        <Card>
          <CardContent className="py-4 flex items-center gap-4 text-sm">
            <span>
              <span className="text-muted-foreground">Universe:</span>{' '}
              <span className="font-medium">{universeQuery.data?.name ?? runQuery.data.universe_id}</span>
            </span>
            <Badge
              variant={
                runQuery.data.status === 'completed'
                  ? 'default'
                  : runQuery.data.status === 'failed'
                    ? 'destructive'
                    : 'secondary'
              }
            >
              {statusLabel(runQuery.data.status)}
            </Badge>
            <span className="text-muted-foreground">
              {new Date(runQuery.data.created_at).toLocaleString('de-CH')}
            </span>
          </CardContent>
        </Card>
      )}

      {(runQuery.data?.status === 'pending' || runQuery.data?.status === 'running') && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <Loader2 className="h-4 w-4 animate-spin shrink-0" />
          <span>Run läuft noch. Seite aktualisiert sich alle 5s.</span>
        </div>
      )}

      {runQuery.data?.status === 'failed' && (
        <Card>
          <CardContent className="py-8 flex items-center gap-2 text-destructive">
            <XCircle className="h-5 w-5 shrink-0" />
            <span>Run fehlgeschlagen. Prüfe Backend-Logs.</span>
          </CardContent>
        </Card>
      )}

      {!is404 && (runQuery.isLoading || (isCompleted && rankingsQuery.isLoading)) && <TableSkeleton />}

      {isCompleted && rankingsQuery.data && (
        <>
          <TopTenLeaderboard items={rankingsQuery.data} runId={params.runId} />
          <RankingsTable items={rankingsQuery.data} runId={params.runId} swissTickers={swissTickers} />
        </>
      )}

      {isCompleted && rankingsQuery.isError && (
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            Rankings konnten nicht geladen werden:{' '}
            {rankingsQuery.error instanceof Error ? rankingsQuery.error.message : 'Unbekannter Fehler'}
          </span>
        </div>
      )}
    </div>
  );
}
