'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { getPortfolioBacktest } from '@/lib/api/crypto-signals';
import { CryptoEquityChart } from '@/components/crypto/CryptoEquityChart';

export function PortfolioClient() {
  const { data: report, isLoading } = useQuery({
    queryKey: ['portfolio-backtest'],
    queryFn: getPortfolioBacktest,
    staleTime: 60 * 60_000,
  });

  return (
    <div className="space-y-4">
      {isLoading && <Skeleton className="h-80 w-full" />}
      {report && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Sharpe', value: report.sharpe.toFixed(2) },
              { label: 'Calmar', value: report.calmar.toFixed(2) },
              { label: 'MaxDD', value: `${(report.max_dd * 100).toFixed(1)}%` },
              { label: 'ø Exposure', value: `${(report.avg_exposure * 100).toFixed(0)}%` },
            ].map(m => (
              <Card key={m.label} className="text-center p-3">
                <div className="text-xs text-muted-foreground">{m.label}</div>
                <div className="text-lg font-bold mt-0.5">{m.value}</div>
              </Card>
            ))}
          </div>

          <Card className={`border ${report.avg_exposure < 0.5 ? 'border-amber-300 bg-amber-50/50 dark:border-amber-800/40 dark:bg-amber-950/10' : ''}`}>
            <CardContent className="pt-3 pb-3 text-sm">
              <strong>Drawdown-Bremse:</strong>{' '}
              {report.avg_exposure < 0.5
                ? `Aktiv — durchschnittliche Exposure ${(report.avg_exposure * 100).toFixed(0)}% (Bremse reduziert Exposure bei Drawdown)`
                : `Inaktiv — volle Exposure ${(report.avg_exposure * 100).toFixed(0)}%`}
            </CardContent>
          </Card>

          <CryptoEquityChart
            report={{
              ...report,
              coin: 'Portfolio',
              n_trades: report.n_rebalances,
              beats_exposure_matched: report.beats_exposure_matched,
            } as Parameters<typeof CryptoEquityChart>[0]['report']}
            title="Portfolio — Strategie vs Buy&Hold-Korb vs Exposure-Matched"
          />

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-base">Allokation je Coin (Ø-Gewicht)</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-1">
                {report.coins.map(c => {
                  const stats = report.per_coin_stats[c];
                  const pct = stats ? (stats.avg_weight * 100).toFixed(1) : '—';
                  return (
                    <div key={c} className="flex items-center gap-2 text-sm">
                      <span className="w-12 font-mono">{c}</span>
                      <div className="flex-1 h-2 bg-muted rounded overflow-hidden">
                        <div className="h-full bg-primary/60 rounded" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-xs text-muted-foreground w-10 text-right">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
