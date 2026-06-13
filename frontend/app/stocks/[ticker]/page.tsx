'use client';

import { Fragment, Suspense, useState } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { ArrowLeft, Bell, FileSearch } from 'lucide-react';
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
import { getFactsheet, getLangfristScore, getPrices, type LangfristScore } from '@/lib/api/stocks';
import { getDividends } from '@/lib/api/dividends';
import { getFundamentals } from '@/lib/api/fundamentals';
import { DividendCard } from '@/components/factsheet/DividendCard';
import { FundamentalsCard } from '@/components/factsheet/FundamentalsCard';
import { MacroWidget } from '@/components/dashboard/MacroWidget';
import { NewsPanel } from '@/components/factsheet/NewsPanel';
import { SteuerPanel } from '@/components/factsheet/SteuerPanel';
import { PriceChart } from '@/components/factsheet/PriceChart';
import { AuditPanel } from '@/components/factsheet/AuditPanel';
import { MLPanel } from '@/components/factsheet/MLPanel';
import { EligibilityPanel } from '@/components/factsheet/EligibilityPanel';

function scoreColor(value: number): string {
  if (value >= 7.5) return 'text-emerald-600 dark:text-emerald-400';
  if (value >= 5.0) return 'text-amber-600 dark:text-amber-400';
  return 'text-red-600 dark:text-red-400';
}

function LangfristCard({ score }: { score: LangfristScore }) {
  const componentLabels: Record<string, string> = {
    dividende: 'Dividende',
    bilanz: 'Bilanz',
    stabilitaet: 'Stabilität',
    marktkapita: 'Marktgrösse',
  };
  return (
    <Card data-testid="langfrist-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">VIAC Langfrist-Score</CardTitle>
          <span className={`text-2xl font-bold tabular-nums ${scoreColor(score.value)}`}>
            {score.value.toFixed(1)}<span className="text-sm font-normal text-muted-foreground">/10</span>
          </span>
        </div>
        <CardDescription className="text-xs">{score.explanation}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {Object.entries(score.components).map(([key, val]) => (
            <Fragment key={key}>
              <dt className="text-muted-foreground">{componentLabels[key] ?? key}</dt>
              <dd className={`font-medium ${scoreColor(val)}`}>{val.toFixed(1)}</dd>
            </Fragment>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">{score.disclaimer}</p>
      </CardContent>
    </Card>
  );
}

function formatMarketCap(value: number): string {
  if (value >= 1e12) return `CHF ${(value / 1e12).toFixed(1)} Bio.`;
  if (value >= 1e9) return `CHF ${(value / 1e9).toFixed(1)} Mrd.`;
  if (value >= 1e6) return `CHF ${(value / 1e6).toFixed(0)} Mio.`;
  return `CHF ${value.toFixed(0)}`;
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
  const { data: factsheet, error: factsheetError } = useQuery({
    queryKey: ['factsheet', symbol],
    queryFn: () => getFactsheet(symbol),
    retry: 1,
  });

  // Optional: load Langfrist-Score for Swiss stocks
  const { data: langfrist } = useQuery({
    queryKey: ['langfrist-score', symbol],
    queryFn: () => getLangfristScore(symbol),
    retry: 1,
  });

  const { data: dividendData } = useQuery({
    queryKey: ['dividends', symbol],
    queryFn: () => getDividends(symbol),
    retry: 1,
    staleTime: 5 * 60 * 1_000,
  });

  const { data: fundamentalsData, error: fundamentalsError } = useQuery({
    queryKey: ['fundamentals', symbol],
    queryFn: () => getFundamentals(symbol),
    retry: 1,
    staleTime: 5 * 60 * 1_000,
  });

  const { data: prices, error: pricesError } = useQuery({
    queryKey: ['prices', symbol],
    queryFn: () => getPrices(symbol),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const handleRequestMemo = async () => {
    setMemoLoading(true);
    setMemoError(null);
    try {
      const stockId =
        factsheet?.stock?.id ??
        (await apiFetch<{ id: string }>(`/api/v1/stocks/${symbol}`)).id;
      const result = await generateMemo(stockId, runId || null);
      setMemo(result);
    } catch (err) {
      setMemoError(err instanceof Error ? err.message : 'Memo-Fehler');
    } finally {
      setMemoLoading(false);
    }
  };

  const hasError = factsheetError || fundamentalsError || pricesError;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      {hasError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Einige Daten konnten nicht geladen werden. Bitte Seite neu laden.
        </div>
      )}
      <div className="flex items-center justify-between">
        <Link
          href={runId ? `/rankings/${runId}` : '/discover'}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          {runId ? 'Zurück' : 'Mein Universe'}
        </Link>
        <div className="flex items-center gap-3">
          <Link
            href={`/research?ticker=${symbol}`}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            data-testid="research-link"
          >
            <FileSearch className="h-3.5 w-3.5" />
            CH-Filings
          </Link>
          <Link
            href={`/alerts?ticker=${symbol}`}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            data-testid="create-alert-link"
          >
            <Bell className="h-3.5 w-3.5" />
            Alert
          </Link>
        </div>
      </div>

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
                <dd>
                  <Link
                    href={`/stocks?sector=${encodeURIComponent(factsheet.stock.sector)}`}
                    className="hover:underline"
                    data-testid="factsheet-sector-link"
                  >
                    {factsheet.stock.sector}
                  </Link>
                </dd>
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
            disabled={memoLoading}
            data-testid="request-memo-btn"
          >
            {memoLoading ? 'Memo wird erstellt…' : 'Memo anfordern'}
          </Button>
          {memoError && (
            <p className="text-sm text-destructive">{memoError}</p>
          )}
        </CardContent>
      </Card>

      {langfrist && <LangfristCard score={langfrist} />}

      {fundamentalsData && <FundamentalsCard data={fundamentalsData} />}

      {dividendData && <DividendCard data={dividendData} />}

      {prices && <PriceChart ticker={symbol} prices={prices.prices} />}

      <MacroWidget />

      <NewsPanel ticker={symbol} />

      <MLPanel ticker={symbol} />

      <SteuerPanel ticker={symbol} />

      <AuditPanel ticker={symbol} />

      <EligibilityPanel ticker={symbol} />


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


function FactsheetSkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="h-5 w-32 rounded bg-muted animate-pulse" />
      <div className="h-36 rounded-xl bg-muted animate-pulse" />
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
        ))}
      </div>
      <div className="h-64 rounded-xl bg-muted animate-pulse" />
    </div>
  );
}

export default function StockFactsheetPage() {
  return (
    <Suspense fallback={<FactsheetSkeleton />}>
      <FactsheetContent />
    </Suspense>
  );
}
