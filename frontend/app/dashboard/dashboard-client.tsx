'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { TrendingUp, BarChart2, PieChart } from 'lucide-react';

import { listRuns, getRankings, type RankingRunStatus, type RunResponse } from '@/lib/api/runs';
import { listUniverses } from '@/lib/api/universes';
import { listStocks } from '@/lib/api/stocks';
import { listDecisions, type DecisionSignal } from '@/lib/api/decisions';
import { StatsCards, type TopPick } from '@/components/dashboard/StatsCards';
import { MacroWidget } from '@/components/dashboard/MacroWidget';
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

const QUICK_LINKS = [
  { href: '/rankings', title: 'Aktien Ranking', desc: 'Bewerte alle Schweizer Aktien und finde die Besten', icon: TrendingUp },
  { href: '/decision', title: 'Kauf-Signale', desc: 'Aktuelle BUY/HOLD/SELL Empfehlungen', icon: BarChart2 },
  { href: '/portfolio', title: 'Portfolio', desc: 'Analysiere dein bestehendes Portfolio', icon: PieChart },
];

const SIGNAL_COLORS: Record<string, string> = {
  BUY:  'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  HOLD: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  SELL: 'bg-red-500/20 text-red-400 border-red-500/30',
};

function BuySignalsSection({ universeId }: { universeId: string | null }) {
  const [signals, setSignals] = useState<DecisionSignal[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!universeId) {
      setLoaded(true);
      return;
    }
    setLoading(true);
    listDecisions(universeId, 'BUY')
      .then((res) => {
        const sorted = [...res.items].sort((a, b) => b.weighted_score - a.weighted_score);
        setSignals(sorted.slice(0, 3));
      })
      .catch(() => setSignals([]))
      .finally(() => {
        setLoading(false);
        setLoaded(true);
      });
  }, [universeId]);

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <h2 className="text-sm font-semibold text-foreground">Aktuelle Kaufsignale</h2>

      {loading && (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      )}

      {loaded && !loading && signals.length === 0 && (
        <div className="py-4 text-center">
          <Link href="/rankings" className="text-sm text-blue-400 hover:text-blue-300 transition-colors">
            Ersten Ranking-Run starten →
          </Link>
        </div>
      )}

      {loaded && !loading && signals.length > 0 && (
        <div className="space-y-2">
          {signals.map((sig) => (
            <div key={sig.ticker} className="flex items-center gap-3 rounded-md px-3 py-2 hover:bg-muted/50 transition-colors">
              <span className="font-mono text-xs font-bold w-12 shrink-0 text-foreground">
                {sig.ticker}
              </span>
              <div className="flex-1 min-w-0">
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    style={{ width: `${Math.round(sig.weighted_score * 100)}%` }}
                    className="h-full bg-emerald-500 rounded-full transition-all"
                  />
                </div>
              </div>
              <span className="text-xs tabular-nums text-muted-foreground w-8 text-right shrink-0">
                {Math.round(sig.weighted_score * 100)}
              </span>
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded border shrink-0 ${SIGNAL_COLORS[sig.signal] ?? ''}`}>
                {sig.signal}
              </span>
              <Link
                href={`/decision?tickers=${sig.ticker}`}
                className="text-xs text-blue-400 hover:text-blue-300 shrink-0 transition-colors"
              >
                →
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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
    refetchInterval: (q) => {
      const data = q.state.data as RunResponse[] | undefined;
      const hasActive = data?.some(
        (r: RunResponse) => r.status === 'pending' || r.status === 'running',
      );
      return hasActive ? 5_000 : false;
    },
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

  // First universe ID for BUY signals fetch
  const firstUniverseId = universesData?.items[0]?.id ?? null;

  const quickLinks = (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {QUICK_LINKS.map(({ href, title, desc, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          className="bg-card border border-border rounded-lg p-4 hover:border-blue-500/50 transition-all cursor-pointer flex flex-col gap-2"
        >
          <Icon className="h-5 w-5 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">{title}</span>
          <span className="text-xs text-muted-foreground leading-relaxed">{desc}</span>
        </Link>
      ))}
    </div>
  );

  const statsCards = (
    <>
      <StatsCards
        latestRun={latestRun}
        universeCount={universeCount}
        stockCount={stockCount}
        topPick={topPick}
      />
      <MacroWidget />
    </>
  );

  if (runsLoading) {
    return (
      <div className="space-y-6">
        {quickLinks}
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
        {quickLinks}
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
        {quickLinks}
        {statsCards}
        <BuySignalsSection universeId={firstUniverseId} />
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
      {quickLinks}
      {statsCards}
      <BuySignalsSection universeId={firstUniverseId} />
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
                className={`cursor-pointer ${run.status === 'pending' || run.status === 'running' ? 'animate-pulse' : ''}`}
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
