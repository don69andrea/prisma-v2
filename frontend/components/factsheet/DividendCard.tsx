'use client';

import { TrendingUp } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { DividendData } from '@/lib/api/dividends';

function yieldColor(pct: number): string {
  if (pct >= 3.0) return 'text-emerald-600 dark:text-emerald-400';
  if (pct >= 1.5) return 'text-amber-600 dark:text-amber-400';
  return 'text-muted-foreground';
}

interface Props {
  data: DividendData;
}

export function DividendCard({ data }: Props) {
  const { last_dividend_chf, ex_date, dividend_yield_pct, history, disclaimer } = data;

  return (
    <Card data-testid="dividend-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Dividende</CardTitle>
          </div>
          {dividend_yield_pct != null ? (
            <span
              className={`text-2xl font-bold tabular-nums ${yieldColor(dividend_yield_pct)}`}
              data-testid="dividend-yield"
            >
              {dividend_yield_pct.toFixed(1)}
              <span className="text-sm font-normal text-muted-foreground">%</span>
            </span>
          ) : (
            <span className="text-lg text-muted-foreground">—</span>
          )}
        </div>
        <CardDescription className="text-xs">Dividendenrendite (Yahoo Finance)</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">Letzte Ausschüttung</dt>
          <dd className="font-medium">
            {last_dividend_chf != null ? `CHF ${last_dividend_chf.toFixed(2)}` : '—'}
          </dd>
          <dt className="text-muted-foreground">Ex-Datum</dt>
          <dd>{ex_date ?? '—'}</dd>
        </dl>

        {history.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Ausschüttungshistorie
            </p>
            <table className="w-full text-xs" data-testid="dividend-history">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="py-1 text-left font-normal">Datum</th>
                  <th className="py-1 text-right font-normal">CHF</th>
                </tr>
              </thead>
              <tbody>
                {[...history].reverse().map((entry) => (
                  <tr key={entry.date} className="border-b last:border-0">
                    <td className="py-1 tabular-nums">{entry.date}</td>
                    <td className="py-1 text-right tabular-nums font-medium">
                      {entry.amount_chf.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-muted-foreground">{disclaimer}</p>
      </CardContent>
    </Card>
  );
}
