'use client';

import { useQuery } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { getFactsheet, getPrices } from '@/lib/api/stocks';
import { ApiError } from '@/lib/api/client';
import { Card, CardContent } from '@/components/ui/card';
import { StockHeader } from '@/components/factsheet/StockHeader';
import { ModelRankCards } from '@/components/factsheet/ModelRankCards';
import { PriceChart } from '@/components/factsheet/PriceChart';
import { MemoPanel } from '@/components/factsheet/MemoPanel';
import { AuditPanel } from '@/components/factsheet/AuditPanel';

function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`h-32 rounded-lg bg-muted animate-pulse ${className}`} />
  );
}

interface Props {
  runId: string;
  ticker: string;
}

export function FactsheetView({ ticker, runId }: Props) {
  const factsheetQuery = useQuery({
    queryKey: ['factsheet', ticker],
    queryFn: () => getFactsheet(ticker),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });

  const pricesQuery = useQuery({
    queryKey: ['prices', ticker],
    queryFn: () => getPrices(ticker),
    staleTime: 5 * 60 * 1000,
  });

  const is404 =
    factsheetQuery.error instanceof ApiError && factsheetQuery.error.status === 404;

  if (is404) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-lg font-medium">Stock nicht gefunden</p>
          <p className="text-sm text-muted-foreground mt-1">Ticker: {ticker}</p>
        </CardContent>
      </Card>
    );
  }

  if (factsheetQuery.isError) {
    return (
      <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
        <XCircle className="h-4 w-4 shrink-0" />
        <span>
          Factsheet konnte nicht geladen werden:{' '}
          {factsheetQuery.error instanceof Error
            ? factsheetQuery.error.message
            : 'Unbekannter Fehler'}
        </span>
      </div>
    );
  }

  if (factsheetQuery.isLoading) {
    return (
      <div className="space-y-4">
        <SkeletonCard className="h-24" />
        <div className="grid grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <SkeletonCard key={i} className="h-28" />
          ))}
        </div>
        <SkeletonCard className="h-72" />
        <SkeletonCard className="h-32" />
      </div>
    );
  }

  const { stock, latest_ranking } = factsheetQuery.data!;

  return (
    <div className="space-y-4">
      <StockHeader stock={stock} ranking={latest_ranking} />

      {latest_ranking && (
        <ModelRankCards perModelRanks={latest_ranking.per_model_ranks} />
      )}

      {pricesQuery.data && (
        <PriceChart ticker={ticker} prices={pricesQuery.data.prices} />
      )}
      {pricesQuery.isLoading && <SkeletonCard className="h-72" />}

      <AuditPanel ticker={ticker} />

      <MemoPanel stockId={stock.id} runId={runId} />
    </div>
  );
}
