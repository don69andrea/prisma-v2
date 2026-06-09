'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Search } from 'lucide-react';

import { retrieveNews, type NewsChunkResult } from '@/lib/api/news';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const SOURCE_LABEL: Record<string, string> = {
  nzz: 'NZZ',
  srf: 'SRF',
};

function NewsResultCard({ item }: { item: NewsChunkResult }) {
  const similarityPct = Math.round(item.similarity * 100);

  return (
    <div className="rounded-lg border bg-card p-4 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium text-sm leading-snug">{item.title}</p>
        <Badge variant="outline" className="shrink-0 text-[10px]">
          {similarityPct}%
        </Badge>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="font-medium">{SOURCE_LABEL[item.source] ?? item.source}</span>
        {item.published_at && (
          <>
            <span>·</span>
            <span>
              {new Date(item.published_at).toLocaleDateString('de-CH', { dateStyle: 'short' })}
            </span>
          </>
        )}
        {item.tickers.length > 0 && (
          <>
            <span>·</span>
            <span>{item.tickers.join(', ')}</span>
          </>
        )}
      </div>
      <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
        {item.content}
      </p>
    </div>
  );
}

export function NewsClient() {
  const [query, setQuery] = useState('');
  const [ticker, setTicker] = useState('');
  const [results, setResults] = useState<NewsChunkResult[] | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      retrieveNews({ query, k: 10, ticker: ticker.trim() || undefined }),
    onSuccess: (data) => setResults(data.results),
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    mutation.mutate();
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>News-Suche</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex flex-col gap-3 sm:flex-row">
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
            <Input
              placeholder="Ticker (optional)"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              className="w-full sm:w-28"
              data-testid="news-ticker-input"
            />
            <Button
              type="submit"
              disabled={mutation.isPending || !query.trim()}
              data-testid="news-search-btn"
            >
              {mutation.isPending ? 'Suche…' : 'Suchen'}
            </Button>
          </form>
          {mutation.isError && (
            <p className="mt-3 text-sm text-destructive">
              Suche fehlgeschlagen. Bitte erneut versuchen.
            </p>
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
                {results.length} Ergebnis{results.length !== 1 ? 'se' : ''}
              </p>
              {results.map((r) => (
                <NewsResultCard key={r.chunk_id} item={r} />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
