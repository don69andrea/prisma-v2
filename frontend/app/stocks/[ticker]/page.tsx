'use client';

import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import { getFactsheet } from '@/lib/api/stocks';
import { StockHeader } from '@/components/factsheet/StockHeader';
import { MemoPanel } from '@/components/factsheet/MemoPanel';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

function FactsheetContent() {
  const { ticker } = useParams<{ ticker: string }>();
  const searchParams = useSearchParams();
  const runId = searchParams.get('run_id') ?? '';
  const symbol = ticker.toUpperCase();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['factsheet', symbol],
    queryFn: () => getFactsheet(symbol),
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-20 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card>
          <CardContent className="py-8 text-center text-sm text-destructive">
            Stock &apos;{symbol}&apos; nicht gefunden.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href={runId ? `/rankings/${runId}` : '/rankings'}
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Zurück
      </Link>

      <StockHeader stock={data.stock} ranking={data.latest_ranking} />

      {runId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Research-Memo</CardTitle>
          </CardHeader>
          <CardContent>
            <MemoPanel stockId={data.stock.id} runId={runId} />
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
