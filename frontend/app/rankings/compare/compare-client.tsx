'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useQueries } from '@tanstack/react-query';
import { ArrowLeft, XCircle } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { getRankings, getRun, type RankingItem, type RunResponse } from '@/lib/api/runs';
import { buildCompareRows, buildCompareStats } from '@/lib/compare';
import { ApiError } from '@/lib/api/client';

import { CompareBanner } from './compare-banner';
import { CompareTable } from './compare-table';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function ErrorBox({ title, detail }: { title: string; detail?: string }) {
  return (
    <Card>
      <CardContent className="py-12 text-center space-y-2">
        <XCircle className="mx-auto h-8 w-8 text-destructive" />
        <p className="text-lg font-medium">{title}</p>
        {detail && <p className="text-sm text-muted-foreground">{detail}</p>}
        <Link
          href="/rankings"
          className="inline-flex items-center text-sm text-primary hover:underline mt-2"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Zurück zur Übersicht
        </Link>
      </CardContent>
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-24 rounded-md bg-muted animate-pulse" />
      <div className="h-64 rounded-md bg-muted animate-pulse" />
    </div>
  );
}

function retryNon404(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status === 404) return false;
  return failureCount < 2;
}

export function CompareClient() {
  const params = useSearchParams();
  const a = params.get('a');
  const b = params.get('b');

  const validA = a !== null && UUID_RE.test(a);
  const validB = b !== null && UUID_RE.test(b);
  const enabled = validA && validB;

  const queries = useQueries({
    queries: [
      {
        queryKey: ['run', a ?? 'invalid'],
        queryFn: () => getRun(a as string),
        enabled,
        retry: retryNon404,
      },
      {
        queryKey: ['run', b ?? 'invalid'],
        queryFn: () => getRun(b as string),
        enabled,
        retry: retryNon404,
      },
      {
        queryKey: ['rankings', a ?? 'invalid'],
        queryFn: () => getRankings(a as string),
        enabled,
      },
      {
        queryKey: ['rankings', b ?? 'invalid'],
        queryFn: () => getRankings(b as string),
        enabled,
      },
    ],
  });

  if (!a || !b) {
    return <ErrorBox title="Fehlende Run-IDs" detail="URL benötigt ?a=<runId>&b=<runId>" />;
  }
  if (!validA || !validB) {
    return <ErrorBox title="Ungültige Run-ID" />;
  }

  const [runAQ, runBQ, rankAQ, rankBQ] = queries;

  if (queries.some((q) => q.isLoading)) {
    return <LoadingSkeleton />;
  }

  const notFound = [runAQ.error, runBQ.error].find(
    (e) => e instanceof ApiError && e.status === 404,
  );
  if (notFound) {
    return <ErrorBox title="Run nicht gefunden" />;
  }

  const runA = runAQ.data as RunResponse | undefined;
  const runB = runBQ.data as RunResponse | undefined;
  if (!runA || !runB) {
    return <ErrorBox title="Run konnte nicht geladen werden" />;
  }

  if (runA.status !== 'completed' || runB.status !== 'completed') {
    return (
      <ErrorBox
        title="Run noch nicht fertig"
        detail="Bitte warte bis beide Runs den Status 'completed' haben."
      />
    );
  }

  const rankingsA = (rankAQ.data ?? []) as RankingItem[];
  const rankingsB = (rankBQ.data ?? []) as RankingItem[];

  const stats = buildCompareStats(rankingsA, rankingsB);
  const rows = buildCompareRows(rankingsA, rankingsB);

  return (
    <div className="space-y-4">
      <CompareBanner runA={runA} runB={runB} stats={stats} />
      {stats.commonCount > 0 && <CompareTable rows={rows} />}
    </div>
  );
}
