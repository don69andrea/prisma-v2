'use client';

import {
  LineChart, Line, CartesianGrid, XAxis, YAxis,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { BacktestReport } from '@/lib/api/crypto-signals';

interface ChartDataPoint {
  date: string;
  strategy: number;
  buyhold: number;
  exposure_matched: number;
}

interface Props {
  report: BacktestReport;
  /** Optional B&H equity curve for comparison (same date range) */
  buyholdCurve?: [string, number][];
  /** Optional exposure-matched curve */
  exposureMatchedCurve?: [string, number][];
  title?: string;
}

export function CryptoEquityChart({ report, buyholdCurve, exposureMatchedCurve, title }: Props) {
  // Build aligned chart data
  const data: ChartDataPoint[] = report.equity_curve.map(([date, val], i) => ({
    date,
    strategy: val,
    buyhold: buyholdCurve?.[i]?.[1] ?? val,
    exposure_matched: exposureMatchedCurve?.[i]?.[1] ?? val,
  }));

  const beats = report.beats_exposure_matched;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{title ?? `${report.coin} — Walk-Forward Backtest`}</CardTitle>
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground mt-1">
            <span>Sharpe <strong>{report.sharpe.toFixed(2)}</strong></span>
            <span>Calmar <strong>{report.calmar.toFixed(2)}</strong></span>
            <span>MaxDD <strong className="text-red-600">{(report.max_dd * 100).toFixed(1)}%</strong></span>
            <span>CAGR <strong>{(report.cagr * 100).toFixed(1)}%</strong></span>
            <span>Trades <strong>{report.n_trades}</strong></span>
            <span className={beats ? 'text-emerald-600 font-semibold' : 'text-red-600 font-semibold'}>
              {beats ? '✓ schlägt Baseline' : '✗ schlägt Baseline nicht'}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} tickLine={false} />
              <YAxis tick={{ fontSize: 10 }} tickLine={false} tickFormatter={(v: number) => `${v.toFixed(1)}×`} />
              <Tooltip
                formatter={(value: number, name: string) => [`${value.toFixed(3)}×`, name]}
                labelStyle={{ fontSize: 11 }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="strategy" name="Strategie" stroke="#2563eb" strokeWidth={2} dot={false} />
              {buyholdCurve && (
                <Line type="monotone" dataKey="buyhold" name="Buy & Hold" stroke="#9ca3af" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              )}
              {exposureMatchedCurve && (
                <Line type="monotone" dataKey="exposure_matched" name="Exposure-Matched" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="2 2" />
              )}
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      {/* Honest Caveats — required by AGENTS.md Wissenschaftliche Ehrlichkeit */}
      <Card className="border-amber-200 dark:border-amber-800/40 bg-amber-50/50 dark:bg-amber-950/10">
        <CardContent className="pt-4 pb-3">
          <p className="text-xs font-semibold text-amber-700 dark:text-amber-400 mb-2">
            ⚠ Ehrliche Einschränkungen (Pflicht-Disclosure)
          </p>
          <ul className="text-xs text-amber-700/80 dark:text-amber-400/80 space-y-1 list-disc list-inside">
            <li>Edge ist <strong>regime-abhängig</strong> — in Bärenmärkten und Whipsaw-Phasen deutlich geringer oder negativ.</li>
            <li>Edge verschwindet bei Transaktionskosten ≥ 0.5 % (hier: {(report as any).costs !== undefined ? `${((report as any).costs * 100).toFixed(2)}%` : '0.1%'} simuliert).</li>
            <li>Out-of-Sample Walk-Forward, aber <strong>historisch</strong> — kein Versprechen zukünftiger Renditen.</li>
            <li>Backtest ≠ Live: Slippage, API-Ausfälle und echte Geld-Psychologie sind nicht modelliert.</li>
            <li>Vor echtem Einsatz: Paper-Trading über mindestens einen vollen Marktzyklus.</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
