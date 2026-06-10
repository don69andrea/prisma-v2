'use client';

import { XCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { listStocks } from '@/lib/api/stocks';
import { StocksListClient } from '@/components/stocks-list-client';

function StocksSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
      ))}
    </div>
  );
}

export default function StocksPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['stocks'],
    queryFn: () => listStocks(200),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Aktien</h1>
        <p className="text-sm text-muted-foreground">
          Alle verfügbaren Aktien durchsuchen und filtern.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">
            {data ? `${data.items.length} Aktien` : 'Aktien-Universum'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <StocksSkeleton />}

          {isError && (
            <div className="flex items-center gap-2 py-4 text-sm text-destructive">
              <XCircle className="h-4 w-4 shrink-0" />
              <span>
                Aktien konnten nicht geladen werden:{' '}
                {error instanceof Error ? error.message : 'Unbekannter Fehler'}
              </span>
            </div>
          )}

          {!isLoading && !isError && data && (
            <StocksListClient stocks={data.items} />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
