import { Star } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { LatestRankingSnapshot, StockRead } from '@/lib/api/stocks';

interface Props {
  stock: StockRead;
  ranking: LatestRankingSnapshot | null;
}

export function StockHeader({ stock, ranking }: Props) {
  return (
    <Card>
      <CardContent className="py-5">
        <div className="flex items-start justify-between gap-4">
          {/* Left: ticker + name + meta */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-base px-2 py-0.5">
                {stock.ticker}
              </Badge>
              {ranking?.is_sweet_spot && (
                <Badge variant="default" className="flex items-center gap-1">
                  <Star className="h-3 w-3" />
                  Sweet Spot
                </Badge>
              )}
            </div>
            <h1 className="text-2xl font-bold tracking-tight">{stock.name}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {stock.sector && <span>{stock.sector}</span>}
              {stock.sector && stock.country && <span>·</span>}
              {stock.country && <span>{stock.country}</span>}
              {stock.currency && (
                <>
                  <span>·</span>
                  <span>{stock.currency}</span>
                </>
              )}
            </div>
          </div>

          {/* Right: total rank */}
          {ranking?.total_rank != null && (
            <div className="text-right">
              <div className="text-4xl font-bold tabular-nums">
                #{ranking.total_rank}
              </div>
              <div className="text-xs text-muted-foreground">Gesamtrang</div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
