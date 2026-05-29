'use client';

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

import { listRuns, getRankings, type RankingRunStatus } from '@/lib/api/runs';
import { listUniverses } from '@/lib/api/universes';
import { listStocks } from '@/lib/api/stocks';
import { StatsCards, type TopPick } from '@/components/dashboard/StatsCards';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const STATUS_VARIANT: Record<RankingRunStatus, 'warning' | 'default' | 'success' | 'destructive'> =
  {
    pending: 'warning',
    running: 'default',
    completed: 'success',
    failed: 'destructive',
  };

const STATUS_LABEL: Record<RankingRunStatus, string> = {
  pending: 'Ausstehend',
  running: 'Läuft',
  completed: 'Abgeschlossen',
  failed: 'Fehler',
};

export function DashboardClient() {
  const router = useRouter();

  const {
    data: runs,
    isLoading: runsLoading,
    isError: runsError,
    refetch,
  } = useQuery({
    queryKey: ['runs'],
    queryFn: () => listRuns(),
  });

  const { data: universesData } = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
  });

  const stocksTotalQuery = useQuery({
    queryKey: ['stocks-total'],
    queryFn: () => listStocks(200, 0),
  });

  const latestCompletedRun = runs?.find((r) => r.status === 'completed') ?? null;

  const rankingsQuery = useQuery({
    queryKey: ['rankings', latestCompletedRun?.id],
    queryFn: () => getRankings(latestCompletedRun!.id),
    enabled: latestCompletedRun !== null,
  });

  const universeMap = new Map(universesData?.items.map((u) => [u.id, u.name]) ?? []);

  const latestRun = runs?.[0] ?? null;
  const universeCount = universesData?.items.length ?? 0;
  // Backend's `total`-Field ist buggy (siehe lib/api/stocks.ts) → items.length nutzen.
  const stockCount = stocksTotalQuery.data?.items.length ?? 0;
  const topPickItem = rankingsQuery.data?.find((r) => r.total_rank === 1);
  const topPick: TopPick | null =
    topPickItem && latestCompletedRun
      ? {
          ticker: topPickItem.ticker,
          isSweetSpot: topPickItem.is_sweet_spot,
          runId: latestCompletedRun.id,
        }
      : null;

  const statsCards = (
    <StatsCards
      latestRun={latestRun}
      universeCount={universeCount}
      stockCount={stockCount}
      topPick={topPick}
    />
  );

  if (runsLoading) {
    return (
      <div className="space-y-6">
        {statsCards}
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (runsError) {
    return (
      <div className="space-y-6">
        {statsCards}
        <div className="space-y-4">
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            Runs konnten nicht geladen werden.
          </div>
          <Button variant="outline" onClick={() => refetch()}>
            Erneut versuchen
          </Button>
        </div>
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="space-y-6">
        {statsCards}
        <div className="space-y-4">
          <p className="text-muted-foreground">Noch keine Runs vorhanden.</p>
          <Button asChild>
            <Link href="/rankings">Neuen Run erstellen</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {statsCards}
      <div className="space-y-4">
        <div className="flex justify-end">
          <Button asChild size="sm">
            <Link href="/rankings">Neuen Run erstellen</Link>
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Run-ID</TableHead>
              <TableHead>Erstellt am</TableHead>
              <TableHead>Universum</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow
                key={run.id}
                className="cursor-pointer"
                onClick={() => router.push(`/rankings/${run.id}`)}
              >
                <TableCell className="font-mono text-xs">{run.id.slice(0, 8)}</TableCell>
                <TableCell>
                  {new Date(run.created_at).toLocaleString('de-CH', {
                    dateStyle: 'short',
                    timeStyle: 'short',
                  })}
                </TableCell>
                <TableCell>
                  {universeMap.get(run.universe_id) ?? run.universe_id.slice(0, 8)}
                </TableCell>
                <TableCell>
                  <Badge variant={STATUS_VARIANT[run.status]}>{STATUS_LABEL[run.status]}</Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
