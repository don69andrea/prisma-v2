'use client';

import { Suspense, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { generateMemo, type Memo } from '@/lib/api/memos';
import { apiFetch } from '@/lib/api/client';
import { getFundamentals } from '@/lib/api/fundamentals';
import { FundamentalsCard } from '@/components/FundamentalsCard';
import { getEligibility } from '@/lib/api/eligibility';
import { EligibilityPanel } from '@/components/EligibilityPanel';

interface StockDetail {
  id: string;
  ticker: string;
  name: string;
  isin?: string;
  sector?: string;
  country?: string;
  currency: string;
}

function FactsheetContent() {
  const { ticker } = useParams<{ ticker: string }>();
  const searchParams = useSearchParams();
  const runId = searchParams.get('run_id') ?? '';
  const symbol = ticker.toUpperCase();

  const [memo, setMemo] = useState<Memo | null>(null);
  const [memoLoading, setMemoLoading] = useState(false);
  const [memoError, setMemoError] = useState<string | null>(null);

  const { data: fundamentals, isLoading: fundsLoading } = useQuery({
    queryKey: ['fundamentals', symbol],
    queryFn: () => getFundamentals(symbol),
    staleTime: 10 * 60 * 1000,
  });

  const { data: eligibility, isLoading: eligibilityLoading } = useQuery({
    queryKey: ['3a-eligibility', symbol],
    queryFn: () => getEligibility(symbol),
    staleTime: 30 * 60 * 1000,
  });

  const handleRequestMemo = async () => {
    setMemoLoading(true);
    setMemoError(null);
    try {
      const stock = await apiFetch<StockDetail>(`/api/v1/stocks/${symbol}`);
      const result = await generateMemo(stock.id, runId);
      setMemo(result);
    } catch (err) {
      setMemoError(err instanceof Error ? err.message : 'Memo-Fehler');
    } finally {
      setMemoLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Card>
        <CardHeader>
          <CardTitle data-testid="factsheet-ticker">{symbol}</CardTitle>
          <CardDescription>Factsheet</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl
            className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm"
            data-testid="factsheet-metrics"
          >
            <dt className="text-muted-foreground">Ticker</dt>
            <dd className="font-mono">{symbol}</dd>
            <dt className="text-muted-foreground">Run ID</dt>
            <dd className="truncate font-mono text-xs">{runId || '—'}</dd>
          </dl>
          <Button
            onClick={handleRequestMemo}
            disabled={memoLoading || !runId}
            data-testid="request-memo-btn"
          >
            {memoLoading ? 'Memo wird erstellt…' : 'Memo anfordern'}
          </Button>
          {memoError && <p className="text-sm text-destructive">{memoError}</p>}
        </CardContent>
      </Card>

      {fundsLoading ? (
        <Skeleton className="h-48 w-full rounded-xl" />
      ) : fundamentals ? (
        <FundamentalsCard data={fundamentals} />
      ) : null}

      {eligibilityLoading ? (
        <Skeleton className="h-24 w-full rounded-xl" />
      ) : eligibility ? (
        <EligibilityPanel data={eligibility} />
      ) : null}

      {memo && (
        <Card data-testid="memo-card">
          <CardHeader>
            <CardTitle>Research-Memo</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm" data-testid="memo-content">
              {memo.one_liner}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function StockFactsheetPage() {
  return (
    <Suspense>
      <FactsheetContent />
    </Suspense>
  );
}
