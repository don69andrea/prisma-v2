'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Download, ExternalLink, Newspaper, Search } from 'lucide-react';
import Link from 'next/link';

import { retrieveNews, type NewsChunkResult } from '@/lib/api/news';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { PrismaBar } from '@/components/ui/PrismaBar';
import { Skeleton } from '@/components/ui/skeleton';

// ---------------------------------------------------------------------------
// Constants & helpers
// ---------------------------------------------------------------------------

const SOURCE_LABEL: Record<string, string> = {
  nzz: 'NZZ',
  srf: 'SRF',
};

const DAILY_QUERY = 'SMI Schweizer Aktien heute';

const LS_KEY = 'prisma_news_last_search';

function loadStoredSearch() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw) as { query: string; ticker: string };
  } catch {}
  return null;
}

/** Return the first 1-2 sentences of a string (used as AI interpretation). */
function firstTwoSentences(text: string): string {
  const matches = text.match(/[^.!?]+[.!?]+/g);
  if (!matches) return text.slice(0, 180).trim();
  return matches.slice(0, 2).join(' ').trim();
}

/** Format relative time label (e.g. "vor 2h"). Falls back to short date. */
function relativeTime(iso: string | null): string {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60_000);
  if (mins < 60) return `vor ${mins}m`;
  const hrs = Math.round(diff / 3_600_000);
  if (hrs < 24) return `vor ${hrs}h`;
  return new Date(iso).toLocaleDateString('de-CH', { dateStyle: 'short' });
}

/** Article URL — no url field on NewsChunkResult, so link to /research pre-filled. */
function articleHref(item: NewsChunkResult): string {
  return `/research?q=${encodeURIComponent(item.title)}`;
}

function exportNewsCsv(items: NewsChunkResult[], queryText: string) {
  const rows = [
    ['Titel', 'Quelle', 'Datum', 'Ähnlichkeit%', 'Tickers', 'Inhalt'],
    ...items.map((r) => [
      r.title,
      SOURCE_LABEL[r.source] ?? r.source,
      r.published_at
        ? new Date(r.published_at).toLocaleDateString('de-CH', { dateStyle: 'short' })
        : '',
      Math.round(r.similarity * 100).toString(),
      r.tickers.join(' '),
      r.content.slice(0, 200),
    ]),
  ];
  const csv = rows
    .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `news-${queryText.replace(/\s+/g, '-').slice(0, 30)}-${new Date()
    .toISOString()
    .slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Article card — Simple Mode
// ---------------------------------------------------------------------------

function SimpleNewsCard({ item }: { item: NewsChunkResult }) {
  const interpretation = firstTwoSentences(item.content);

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-sm leading-snug">{item.title}</p>
        <span className="shrink-0 text-xs text-muted-foreground whitespace-nowrap">
          {relativeTime(item.published_at)}
        </span>
      </div>

      {/* KI-Interpretation */}
      <div className="space-y-1">
        <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
          Was das für dich bedeutet:
        </p>
        <p className="text-sm text-foreground leading-relaxed">
          &ldquo;{interpretation}&rdquo;
        </p>
      </div>

      {/* Affected tickers */}
      {item.tickers.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <span className="text-muted-foreground">Betrifft:</span>
          {item.tickers.slice(0, 4).map((t) => (
            <Link
              key={t}
              href={`/stocks/${t}`}
              className="font-mono font-bold text-blue-400 hover:underline"
              data-testid={`news-ticker-link-${t}`}
            >
              {t}
            </Link>
          ))}
        </div>
      )}

      {/* Footer: source + read link */}
      <div className="flex items-center justify-between pt-1">
        <span className="text-xs text-muted-foreground">
          {SOURCE_LABEL[item.source] ?? item.source}
        </span>
        <Link
          href={articleHref(item)}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          data-testid={`news-article-link-${item.chunk_id}`}
        >
          Artikel lesen
          <ExternalLink className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Article card — Pro Mode (compact, with Vollständige Analyse link)
// ---------------------------------------------------------------------------

function ProNewsCard({ item }: { item: NewsChunkResult }) {
  const similarityPct = Math.round(item.similarity * 100);

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-sm leading-snug">{item.title}</p>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {similarityPct}%
        </Badge>
      </div>

      <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
        <span className="font-medium">{SOURCE_LABEL[item.source] ?? item.source}</span>
        {item.published_at && (
          <>
            <span>·</span>
            <span>{relativeTime(item.published_at)}</span>
          </>
        )}
        {item.tickers.length > 0 && (
          <>
            <span>·</span>
            <span className="flex items-center gap-1 flex-wrap">
              {item.tickers.slice(0, 4).map((t) => (
                <Link
                  key={t}
                  href={`/stocks/${t}`}
                  className="font-mono hover:underline text-foreground"
                  data-testid={`news-ticker-link-${t}`}
                >
                  {t}
                </Link>
              ))}
            </span>
          </>
        )}
      </div>

      <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
        {item.content}
      </p>

      <div className="flex items-center justify-between pt-1">
        <Link
          href={`/research?q=${encodeURIComponent(item.title)}`}
          className="text-xs text-blue-400 hover:underline"
        >
          Vollständige Analyse in Research →
        </Link>
        <Link
          href={articleHref(item)}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
          data-testid={`news-article-link-${item.chunk_id}`}
        >
          Artikel lesen
          <ExternalLink className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Markt-Sentiment panel (Pro Mode sidebar)
// ---------------------------------------------------------------------------

function MarktSentimentPanel() {
  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      <h3 className="text-sm font-semibold tracking-wide uppercase">
        Markt-Stimmung
      </h3>
      <p className="text-xs text-muted-foreground leading-relaxed">
        Live-Sentiment ist in dieser Version nicht verfügbar. News-basierte Analyse via Suche.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Simple Mode view
// ---------------------------------------------------------------------------

function SimpleNewsView({ dailyNews }: { dailyNews: NewsChunkResult[] | null }) {
  return (
    <div className="space-y-4">
      {dailyNews === null ? (
        <div className="space-y-3">
          <PrismaBar />
          {[1, 2, 3].map((i) => (
            <div key={i} className="rounded-lg border border-border p-4 space-y-2 animate-pulse">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : dailyNews.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
          <Newspaper className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium">Keine News verfügbar</p>
          <p className="text-xs text-muted-foreground">Bitte später erneut versuchen.</p>
        </div>
      ) : (
        dailyNews.map((item) => <SimpleNewsCard key={item.chunk_id} item={item} />)
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode view
// ---------------------------------------------------------------------------

interface ProNewsViewProps {
  dailyNews: NewsChunkResult[] | null;
  searchResults: NewsChunkResult[] | null;
  isSearchPending: boolean;
  isSearchError: boolean;
  query: string;
  setQuery: (v: string) => void;
  ticker: string;
  setTicker: (v: string) => void;
  onSearch: (e: React.FormEvent) => void;
  sourceFilter: 'all' | 'nzz' | 'srf';
  setSourceFilter: (v: 'all' | 'nzz' | 'srf') => void;
  sortMode: 'relevance' | 'date';
  setSortMode: (v: 'relevance' | 'date') => void;
  displayResults: NewsChunkResult[] | null;
}

function ProNewsView({
  dailyNews,
  searchResults,
  isSearchPending,
  isSearchError,
  query,
  setQuery,
  ticker,
  setTicker,
  onSearch,
  sourceFilter,
  setSourceFilter,
  sortMode,
  setSortMode,
  displayResults,
}: ProNewsViewProps) {
  // Items shown in the left feed: manual search results take precedence over daily news
  const feedItems = displayResults ?? dailyNews ?? [];
  const feedLabel = displayResults !== null ? 'Suchergebnisse' : 'Heutige News';

  const sourceCounts = useMemo(() => {
    const base = searchResults ?? dailyNews ?? [];
    return {
      nzz: base.filter((r) => r.source === 'nzz').length,
      srf: base.filter((r) => r.source === 'srf').length,
    };
  }, [searchResults, dailyNews]);

  const totalCount = searchResults?.length ?? dailyNews?.length ?? 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
      {/* LEFT: article list */}
      <div className="space-y-4">
        {/* Search bar */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">News-Suche</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSearch} className="flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="z.B. SNB Leitzins, Nestlé Dividende, SMI …"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-9"
                  data-testid="news-query-input"
                />
              </div>
              <div className="relative w-full sm:w-28">
                <Input
                  placeholder="Ticker (opt.)"
                  value={ticker}
                  onChange={(e) => setTicker(e.target.value)}
                  className="w-full"
                  data-testid="news-ticker-input"
                />
              </div>
              <Button
                type="submit"
                disabled={isSearchPending || !query.trim()}
                data-testid="news-search-btn"
              >
                {isSearchPending ? 'Suche…' : 'Suchen'}
              </Button>
            </form>
            {isSearchError && (
              <p className="mt-3 text-sm text-destructive">
                Suche fehlgeschlagen. Bitte erneut versuchen.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Filters row */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Source filter pills */}
          {(['all', 'nzz', 'srf'] as const).map((src) => {
            const label = src === 'all' ? 'Alle Quellen' : SOURCE_LABEL[src];
            const count = src === 'all' ? totalCount : sourceCounts[src];
            const active = sourceFilter === src;
            return (
              <button
                key={src}
                onClick={() => setSourceFilter(src)}
                className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  active
                    ? 'border-transparent bg-foreground text-background'
                    : 'bg-background hover:bg-muted'
                }`}
                data-testid={`news-source-filter-${src}`}
              >
                {label}
                <span className="tabular-nums">{count}</span>
              </button>
            );
          })}

          {/* Sort controls */}
          <div className="ml-auto flex items-center gap-1">
            {(['relevance', 'date'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setSortMode(mode)}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  sortMode === mode
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid={`news-sort-${mode}`}
              >
                {mode === 'relevance' ? 'Relevanz' : 'Datum ↓'}
              </button>
            ))}
            {displayResults && displayResults.length > 0 && (
              <button
                onClick={() => exportNewsCsv(displayResults, query)}
                className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-medium hover:bg-muted transition-colors ml-1"
                data-testid="news-csv-export-btn"
              >
                <Download className="h-3 w-3" />
                CSV
              </button>
            )}
          </div>
        </div>

        {/* Article list */}
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground" data-testid="news-results-count">
            {feedLabel} · {feedItems.length} Artikel
          </p>
          {dailyNews === null && !displayResults && (
            <div className="space-y-3">
              <PrismaBar />
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="rounded-lg border border-border p-4 space-y-2 animate-pulse">
                  <Skeleton className="h-4 w-4/5" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
              ))}
            </div>
          )}
          {dailyNews !== null && feedItems.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
              <Newspaper className="h-10 w-10 text-muted-foreground/40" />
              <p className="text-sm font-medium">Keine News gefunden</p>
              <p className="text-xs text-muted-foreground">
                Versuche einen anderen Suchbegriff oder Ticker
              </p>
            </div>
          ) : (
            feedItems.map((item) => <ProNewsCard key={item.chunk_id} item={item} />)
          )}
        </div>
      </div>

      {/* RIGHT: Sentiment panel (sticky) */}
      <div className="space-y-4 lg:sticky lg:top-6 self-start">
        <MarktSentimentPanel />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export: NewsClient
// ---------------------------------------------------------------------------

export function NewsClient() {
  const { isSimple } = usePrismaMode();

  // Manual search state
  const [query, setQuery] = useState('');
  const [ticker, setTicker] = useState('');

  useEffect(() => {
    const s = loadStoredSearch();
    if (!s) return;
    if (s.query) setQuery(s.query);
    if (s.ticker) setTicker(s.ticker);
  }, []);
  const [searchResults, setSearchResults] = useState<NewsChunkResult[] | null>(null);
  const [sourceFilter, setSourceFilter] = useState<'all' | 'nzz' | 'srf'>('all');
  const [sortMode, setSortMode] = useState<'relevance' | 'date'>('relevance');

  // Daily curated news (auto-loaded)
  const { data: dailyData } = useQuery({
    queryKey: ['daily-news'],
    queryFn: () => retrieveNews({ query: DAILY_QUERY, k: 10 }),
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });
  const dailyNews = dailyData?.results ?? null;

  // Manual search mutation
  const searchMutation = useMutation({
    mutationFn: () =>
      retrieveNews({ query, k: 10, ticker: ticker.trim() || undefined }),
    onSuccess: (data) => {
      setSearchResults(data.results);
      try {
        localStorage.setItem(LS_KEY, JSON.stringify({ query, ticker }));
      } catch {}
      setSourceFilter('all');
      setSortMode('relevance');
    },
  });

  // Filtered + sorted manual results
  const filteredResults = useMemo(() => {
    if (!searchResults) return null;
    if (sourceFilter === 'all') return searchResults;
    return searchResults.filter((r) => r.source === sourceFilter);
  }, [searchResults, sourceFilter]);

  const displayResults = useMemo(() => {
    if (!filteredResults) return null;
    if (sortMode === 'relevance') return filteredResults;
    return [...filteredResults].sort((a, b) => {
      const aMs = a.published_at ? new Date(a.published_at).getTime() : 0;
      const bMs = b.published_at ? new Date(b.published_at).getTime() : 0;
      return bMs - aMs;
    });
  }, [filteredResults, sortMode]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    searchMutation.mutate();
  };

  if (isSimple) {
    return <SimpleNewsView dailyNews={dailyNews} />;
  }

  return (
    <ProNewsView
      dailyNews={dailyNews}
      searchResults={searchResults}
      isSearchPending={searchMutation.isPending}
      isSearchError={searchMutation.isError}
      query={query}
      setQuery={setQuery}
      ticker={ticker}
      setTicker={setTicker}
      onSearch={handleSearch}
      sourceFilter={sourceFilter}
      setSourceFilter={setSourceFilter}
      sortMode={sortMode}
      setSortMode={setSortMode}
      displayResults={displayResults}
    />
  );
}
