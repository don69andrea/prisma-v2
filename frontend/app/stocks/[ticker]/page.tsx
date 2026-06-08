'use client';

import { Suspense, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { SwissBadge } from '@/components/ui/swiss-badge';
import { generateMemo, type Memo } from '@/lib/api/memos';
import { apiFetch } from '@/lib/api/client';
import { getFactsheet } from '@/lib/api/stocks';

function formatMarketCap(value: string): string {
  const n = parseFloat(value);
  if (n >= 1e12) return `CHF ${(n / 1e12).toFixed(1)} Bio.`;
  if (n >= 1e9) return `CHF ${(n / 1e9).toFixed(1)} Mrd.`;
  if (n >= 1e6) return `CHF ${(n / 1e6).toFixed(0)} Mio.`;
  return `CHF ${n.toFixed(0)}`;
}

function FactsheetContent() {
  const { ticker } = useParams<{ ticker: string }>();
  const searchParams = useSearchParams();
  const runId = searchParams.get('run_id') ?? '';
  const symbol = ticker.toUpperCase();

  const [memo, setMemo] = useState<Memo | null>(null);
  const [memoLoading, setMemoLoading] = useState(false);
  const [memoError, setMemoError] = useState<string | null>(null);

  // Optional: load full factsheet for Swiss fields (badge, SIX link, market_cap_chf)
  const { data: factsheet } = useQuery({
    queryKey: ['factsheet', symbol],
    queryFn: () => getFactsheet(symbol),
    retry: false,
  });

  const handleRequestMemo = async () => {
    setMemoLoading(true);
    setMemoError(null);
    try {
      const stockId =
        factsheet?.stock?.id ??
        (await apiFetch<{ id: string }>(`/api/v1/stocks/${symbol}`)).id;
      const result = await generateMemo(stockId, runId);
      setMemo(result);
    } catch (err) {
      setMemoError(err instanceof Error ? err.message : 'Memo-Fehler');
    } finally {
      setMemoLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href={runId ? `/rankings/${runId}` : '/rankings'}
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Zurück
      </Link>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle data-testid="factsheet-ticker">{symbol}</CardTitle>
            {factsheet?.stock && <SwissBadge exchange={factsheet.stock.exchange} />}
          </div>
          <CardDescription>
            {factsheet?.stock?.name ?? 'Factsheet'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl
            className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm"
            data-testid="factsheet-metrics"
          >
            <dt className="text-muted-foreground">Ticker</dt>
            <dd className="font-mono">{symbol}</dd>
            {factsheet?.stock?.sector && (
              <>
                <dt className="text-muted-foreground">Sektor</dt>
                <dd>{factsheet.stock.sector}</dd>
              </>
            )}
            {factsheet?.stock?.market_cap_chf && (
              <>
                <dt className="text-muted-foreground">Marktkapitalisierung</dt>
                <dd className="font-medium">
                  {formatMarketCap(factsheet.stock.market_cap_chf)}
                </dd>
              </>
            )}
            {factsheet?.stock?.exchange === 'XSWX' && (
              <>
                <dt className="text-muted-foreground">Börse</dt>
                <dd>
                  <a
                    href={`https://www.six-group.com/en/products-services/the-swiss-stock-exchange/market-data/shares/share-explorer/share-details.html#id=${symbol}SW`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-600 hover:underline dark:text-sky-400"
                  >
                    SIX Swiss Exchange ↗
                  </a>
                </dd>
              </>
            )}
            {factsheet?.latest_ranking?.total_rank != null && (
              <>
                <dt className="text-muted-foreground">Gesamtrang</dt>
                <dd className="font-semibold">#{factsheet.latest_ranking.total_rank}</dd>
              </>
            )}
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
          {memoError && (
            <p className="text-sm text-destructive">{memoError}</p>
          )}
        </CardContent>
      </Card>

      {memo && (
        <Card data-testid="memo-card">
          <CardHeader>
            <CardTitle>Research-Memo</CardTitle>
          </CardHeader>
          <CardContent>
            <p
              className="whitespace-pre-wrap text-sm"
              data-testid="memo-content"
            >
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
