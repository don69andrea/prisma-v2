'use client';

import { useQuery } from '@tanstack/react-query';
import { Newspaper } from 'lucide-react';

import { retrieveNews } from '@/lib/api/news';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

const SOURCE_LABEL: Record<string, string> = {
  nzz: 'NZZ',
  srf: 'SRF',
};

interface NewsPanelProps {
  ticker: string;
}

export function NewsPanel({ ticker }: NewsPanelProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['news', ticker],
    queryFn: () => retrieveNews({ query: '', k: 5, ticker }),
    staleTime: 5 * 60 * 1_000,
    retry: false,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Newspaper className="h-4 w-4" />
            Aktuelle News
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-1">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  if (!data || data.results.length === 0) return null;

  return (
    <Card data-testid="news-panel">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Newspaper className="h-4 w-4" />
          Aktuelle News
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.results.map((item) => (
          <div key={item.chunk_id} className="border-b pb-3 last:border-0 last:pb-0">
            <p className="text-sm font-medium leading-snug">{item.title}</p>
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {SOURCE_LABEL[item.source] ?? item.source}
              </Badge>
              {item.published_at && (
                <span>
                  {new Date(item.published_at).toLocaleDateString('de-CH', { dateStyle: 'short' })}
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground line-clamp-2 leading-relaxed">
              {item.content}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
