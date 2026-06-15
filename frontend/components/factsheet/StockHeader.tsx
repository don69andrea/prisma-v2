import { Star } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { LatestRankingSnapshot, StockRead } from '@/lib/api/stocks';
import { SwissBadge } from '@/components/ui/swiss-badge';
import { ExportReportButton } from './ExportReportButton';

function formatMarketCap(value: string): string {
  const n = Number(value);
  if (n >= 1e12) return `CHF ${(n / 1e12).toFixed(1)} Bio.`;
  if (n >= 1e9) return `CHF ${(n / 1e9).toFixed(1)} Mrd.`;
  if (n >= 1e6) return `CHF ${(n / 1e6).toFixed(0)} Mio.`;
  return `CHF ${n.toFixed(0)}`;
}

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
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className="font-mono text-base px-2 py-0.5">
                {stock.ticker}
              </Badge>
              <SwissBadge exchange={stock.exchange} />
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
              {stock.exchange === 'XSWX' && (
                <>
                  <span>·</span>
                  <a
                    href={`https://www.six-group.com/en/products-services/the-swiss-stock-exchange/market-data/shares/share-explorer/share-details.html#id=${stock.ticker}SW`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline text-sky-600 dark:text-sky-400"
                  >
                    SIX Profil ↗
                  </a>
                </>
              )}
            </div>
          </div>

          {/* Right: total rank + export */}
          <div className="flex flex-col items-end gap-3">
            {ranking?.total_rank != null && (
              <div className="text-right">
                <div className="text-4xl font-bold tabular-nums">
                  #{ranking.total_rank}
                </div>
                <div className="text-xs text-muted-foreground">Gesamtrang</div>
              </div>
            )}
            <ExportReportButton ticker={stock.ticker} />
          </div>
        </div>
        {stock.market_cap_chf != null && (
          <div className="mt-2 text-sm text-muted-foreground">
            Marktkapitalisierung:{' '}
            <span className="font-medium text-foreground">
              {formatMarketCap(stock.market_cap_chf)}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
