'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Search, ExternalLink } from 'lucide-react';

import {
  retrieveSecFilings,
  retrieveSwissFilings,
  type SecChunkResult,
  type SwissChunkResult,
} from '@/lib/api/rag';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

type TabType = 'swiss' | 'sec';

function SimilarityBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 80 ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
    : pct >= 60 ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
    : 'bg-muted text-muted-foreground';
  return (
    <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded', color)}>
      {pct}%
    </span>
  );
}

function SwissResultCard({ item }: { item: SwissChunkResult }) {
  return (
    <div className="rounded-lg border bg-card p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href={`/stocks/${item.ticker}`}
            className="font-mono font-semibold text-sm hover:underline"
            data-testid={`research-result-ticker-${item.ticker}`}
          >
            {item.ticker}
          </Link>
          <Badge variant="outline" className="text-[10px]">{item.doc_type}</Badge>
          <Badge variant="outline" className="text-[10px]">{item.language.toUpperCase()}</Badge>
        </div>
        <SimilarityBadge value={item.similarity} />
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>{item.source}</span>
        <span>·</span>
        <span>{new Date(item.filing_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}</span>
        {item.url && (
          <>
            <span>·</span>
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 text-sky-600 hover:underline dark:text-sky-400"
            >
              Quelle <ExternalLink className="h-3 w-3" />
            </a>
          </>
        )}
      </div>
      <p className="text-xs text-muted-foreground line-clamp-4 leading-relaxed">{item.content}</p>
    </div>
  );
}

function SecResultCard({ item }: { item: SecChunkResult }) {
  return (
    <div className="rounded-lg border bg-card p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Link
            href={`/stocks/${item.ticker}`}
            className="font-mono font-semibold text-sm hover:underline"
            data-testid={`research-result-ticker-${item.ticker}`}
          >
            {item.ticker}
          </Link>
          <Badge variant="outline" className="text-[10px]">{item.doc_type}</Badge>
        </div>
        <SimilarityBadge value={item.similarity} />
      </div>
      <p className="text-xs text-muted-foreground line-clamp-4 leading-relaxed">{item.content}</p>
    </div>
  );
}

export function ResearchClient() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<TabType>('swiss');
  const [query, setQuery] = useState('');
  const [ticker, setTicker] = useState(
    () => searchParams.get('ticker')?.toUpperCase() ?? '',
  );
  const [swissLang, setSwissLang] = useState<'' | 'de' | 'en' | 'fr'>(() => {
    const lang = searchParams.get('lang');
    return (lang === 'de' || lang === 'en' || lang === 'fr') ? lang : '';
  });
  const [swissResults, setSwissResults] = useState<SwissChunkResult[] | null>(null);
  const [secResults, setSecResults] = useState<SecChunkResult[] | null>(null);

  const swissMutation = useMutation({
    mutationFn: () =>
      retrieveSwissFilings({
        query,
        k: 10,
        ticker: ticker.trim() || undefined,
        language: swissLang || undefined,
      }),
    onSuccess: (data) => setSwissResults(data.results),
  });

  const secMutation = useMutation({
    mutationFn: () =>
      retrieveSecFilings({ query, k: 10, ticker: ticker.trim() || undefined }),
    onSuccess: (data) => setSecResults(data.results),
  });

  const isPending = tab === 'swiss' ? swissMutation.isPending : secMutation.isPending;
  const isError   = tab === 'swiss' ? swissMutation.isError   : secMutation.isError;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    if (tab === 'swiss') swissMutation.mutate();
    else secMutation.mutate();
  };

  const results = tab === 'swiss' ? swissResults : secResults;

  return (
    <div className="space-y-6">
      <div className="flex gap-1 border-b">
        {(['swiss', 'sec'] as TabType[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors',
              tab === t
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}
          >
            {t === 'swiss' ? 'Swiss Jahresberichte' : 'SEC Filings'}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {tab === 'swiss' ? 'SIX Jahresbericht-Suche' : 'SEC Filing-Suche'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={
                  tab === 'swiss'
                    ? 'z.B. Dividendenpolitik, Nachhaltigkeit, Umsatzwachstum …'
                    : 'z.B. revenue growth, risk factors, acquisitions …'
                }
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="pl-9"
                data-testid="research-query-input"
              />
            </div>
            <Input
              placeholder="Ticker (opt.)"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              className="w-full sm:w-28"
              data-testid="research-ticker-input"
            />
            {tab === 'swiss' && (
              <select
                value={swissLang}
                onChange={(e) => setSwissLang(e.target.value as '' | 'de' | 'en' | 'fr')}
                className="rounded-md border border-input bg-background px-3 py-2 text-sm w-full sm:w-24"
                data-testid="research-lang-select"
              >
                <option value="">Alle</option>
                <option value="de">DE</option>
                <option value="en">EN</option>
                <option value="fr">FR</option>
              </select>
            )}
            <Button
              type="submit"
              disabled={isPending || !query.trim()}
              data-testid="research-search-btn"
            >
              {isPending ? 'Suche…' : 'Suchen'}
            </Button>
          </form>
          {isError && (
            <p className="mt-3 text-sm text-destructive">Suche fehlgeschlagen.</p>
          )}
        </CardContent>
      </Card>

      {results !== null && (
        <div className="space-y-3">
          {results.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">
              Keine Ergebnisse für «{query}».
            </p>
          ) : (
            <>
              <p className="text-xs text-muted-foreground">
                {results.length} Treffer
              </p>
              {tab === 'swiss'
                ? (swissResults ?? []).map((r) => (
                    <SwissResultCard key={r.chunk_id} item={r} />
                  ))
                : (secResults ?? []).map((r) => (
                    <SecResultCard key={r.chunk_id} item={r} />
                  ))
              }
            </>
          )}
        </div>
      )}
    </div>
  );
}
