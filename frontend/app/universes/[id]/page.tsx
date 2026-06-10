'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { ArrowLeft, Play } from 'lucide-react';

import { getUniverse } from '@/lib/api/universes';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';

export default function UniverseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [rankingOpen, setRankingOpen] = useState(false);

  const { data: universe, isLoading, isError } = useQuery({
    queryKey: ['universe', id],
    queryFn: () => getUniverse(id),
    staleTime: 5 * 60 * 1_000,
    retry: false,
  });

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/universes"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Zurück zu Universen
      </Link>

      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-48 w-full rounded-xl" />
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive py-8 text-center">
          Universum konnte nicht geladen werden.
        </p>
      )}

      {universe && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle data-testid="universe-detail-name">{universe.name}</CardTitle>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant="outline">{universe.region}</Badge>
                    <span className="text-sm text-muted-foreground">
                      {universe.tickers.length} Ticker
                    </span>
                  </div>
                </div>
                <Button
                  onClick={() => setRankingOpen(true)}
                  data-testid="universe-detail-ranking-btn"
                >
                  <Play className="mr-1 h-4 w-4" />
                  Ranking starten
                </Button>
              </div>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Ticker</CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className="flex flex-wrap gap-2"
                data-testid="universe-detail-tickers"
              >
                {universe.tickers.map((ticker) => (
                  <Link
                    key={ticker}
                    href={`/stocks/${ticker}`}
                    className="rounded-md border bg-muted px-2.5 py-1 text-xs font-mono font-medium hover:bg-accent hover:text-accent-foreground transition-colors"
                  >
                    {ticker}
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>

          <StartRankingDialog
            universe={rankingOpen ? { id: universe.id, name: universe.name } : null}
            onClose={() => setRankingOpen(false)}
          />
        </>
      )}
    </div>
  );
}
