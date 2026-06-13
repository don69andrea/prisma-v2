'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { listRuns } from '@/lib/api/runs';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { runBacktest, type BacktestMode, type BacktestResult, type PortfolioMetrics } from '@/lib/api/backtest';

const METRIC_ROWS: Array<{ label: string; key: keyof PortfolioMetrics; pct: boolean }> = [
  { label: 'Total Return',  key: 'total_return', pct: true  },
  { label: 'CAGR',          key: 'cagr',         pct: true  },
  { label: 'Volatilität',   key: 'annual_vol',   pct: true  },
  { label: 'Sharpe Ratio',  key: 'sharpe',       pct: false },
  { label: 'Max. Drawdown', key: 'max_drawdown', pct: true  },
];

const MODE_LABELS: Record<BacktestMode, string> = {
  quant_only: 'Quant only',
  quant_ml: 'Quant+ML',
  full: 'Quant+ML+Makro',
};

const MODE_COLORS: Record<BacktestMode, string> = {
  quant_only: '#6366f1',
  quant_ml: '#a855f7',
  full: '#10b981',
};

function fmtMetric(v: string, pct: boolean): string {
  const n = parseFloat(v);
  if (isNaN(n)) return '—';
  return pct ? `${(n * 100).toFixed(1)}%` : n.toFixed(2);
}

function exportMetricsCsv(
  prisma: PortfolioMetrics,
  universum: PortfolioMetrics,
  benchmark: PortfolioMetrics,
) {
  const rows = [
    ['Metrik', 'PRISMA', 'Universum', 'Benchmark'],
    ...METRIC_ROWS.map(({ label, key, pct }) => [
      label,
      fmtMetric(prisma[key], pct),
      fmtMetric(universum[key], pct),
      fmtMetric(benchmark[key], pct),
    ]),
  ];
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `backtest-metriken-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function exportSeriesCsv(result: BacktestResult) {
  const rows = [
    ['Datum', 'PRISMA%', 'Universum%', 'Benchmark%'],
    ...result.series.dates.map((d, i) => [
      d,
      `${((result.series.prisma[i] - 1) * 100).toFixed(2)}`,
      `${((result.series.universe[i] - 1) * 100).toFixed(2)}`,
      `${((result.series.benchmark[i] - 1) * 100).toFixed(2)}`,
    ]),
  ];
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `backtest-zeitreihe-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function MetricsTable({
  prisma,
  universum,
  benchmark,
}: {
  prisma: PortfolioMetrics;
  universum: PortfolioMetrics;
  benchmark: PortfolioMetrics;
}) {
  return (
    <Table data-testid="backtest-metrics-table">
      <TableHeader>
        <TableRow>
          <TableHead>Metrik</TableHead>
          <TableHead className="text-right text-indigo-600 dark:text-indigo-400">PRISMA</TableHead>
          <TableHead className="text-right text-emerald-600 dark:text-emerald-400">Universum</TableHead>
          <TableHead className="text-right text-amber-600 dark:text-amber-400">Benchmark</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {METRIC_ROWS.map(({ label, key, pct }) => (
          <TableRow key={label}>
            <TableCell className="text-muted-foreground text-sm">{label}</TableCell>
            <TableCell className="text-right font-medium tabular-nums">{fmtMetric(prisma[key], pct)}</TableCell>
            <TableCell className="text-right tabular-nums">{fmtMetric(universum[key], pct)}</TableCell>
            <TableCell className="text-right tabular-nums">{fmtMetric(benchmark[key], pct)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

// ---- Multi-mode comparison metrics table ----
function ComparisonMetricsTable({
  results,
}: {
  results: Partial<Record<BacktestMode, BacktestResult>>;
}) {
  const modes: BacktestMode[] = ['quant_only', 'quant_ml', 'full'];
  const presentModes = modes.filter((m) => results[m]);

  return (
    <Table data-testid="comparison-metrics-table">
      <TableHeader>
        <TableRow>
          <TableHead>Metrik</TableHead>
          {presentModes.map((m) => (
            <TableHead
              key={m}
              className="text-right"
              style={{ color: MODE_COLORS[m] }}
            >
              {MODE_LABELS[m]}
            </TableHead>
          ))}
          <TableHead className="text-right text-amber-600 dark:text-amber-400">SMI Benchmark</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {METRIC_ROWS.map(({ label, key, pct }) => (
          <TableRow key={label}>
            <TableCell className="text-muted-foreground text-sm">{label}</TableCell>
            {presentModes.map((m) => {
              const r = results[m]!;
              return (
                <TableCell key={m} className="text-right font-medium tabular-nums">
                  {fmtMetric(r.prisma_metrics[key], pct)}
                </TableCell>
              );
            })}
            {/* Benchmark from the first available result */}
            <TableCell className="text-right tabular-nums">
              {presentModes.length > 0
                ? fmtMetric(results[presentModes[0]]!.benchmark_metrics[key], pct)
                : '—'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

const LS_KEY = 'prisma_backtest_config';

function loadStoredConfig() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return JSON.parse(raw) as { startDate: string; endDate: string; topN: number; benchmark: string };
  } catch {}
  return null;
}

type TabMode = 'single' | 'comparison';

function BacktestContent() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<TabMode>('single');
  const [runId, setRunId] = useState(searchParams.get('run_id') ?? '');
  const [startDate, setStartDate] = useState(() => searchParams.get('start') ?? loadStoredConfig()?.startDate ?? '2025-01-01');
  const [endDate, setEndDate] = useState(() => searchParams.get('end') ?? loadStoredConfig()?.endDate ?? '2025-12-31');
  const [topN, setTopN] = useState(() => Number(searchParams.get('top_n') ?? String(loadStoredConfig()?.topN ?? 3)));
  const [benchmark, setBenchmark] = useState(() => searchParams.get('benchmark') ?? loadStoredConfig()?.benchmark ?? '^SSMI');

  // Single-mode state
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Comparison state
  const [compResults, setCompResults] = useState<Partial<Record<BacktestMode, BacktestResult>>>({});
  const [compLoading, setCompLoading] = useState(false);
  const [compError, setCompError] = useState<string | null>(null);

  const [shareCopied, setShareCopied] = useState(false);

  function handleShare() {
    const params = new URLSearchParams({
      ...(runId ? { run_id: runId } : {}),
      start: startDate,
      end: endDate,
      top_n: String(topN),
      benchmark,
    });
    const url = `${window.location.origin}/backtest?${params.toString()}`;
    navigator.clipboard.writeText(url).then(() => {
      setShareCopied(true);
      setTimeout(() => setShareCopied(false), 2000);
    });
  }

  const runsQuery = useQuery({
    queryKey: ['runs', 'backtest'],
    queryFn: () => listRuns(50, 0),
  });
  const completedRuns = (runsQuery.data ?? []).filter((r) => r.status === 'completed');
  const runDateFmt = new Intl.DateTimeFormat('de-CH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await runBacktest({
        model_run_id: runId,
        start_date: startDate,
        end_date: endDate,
        top_n: topN,
        benchmark_ticker: benchmark,
        mode: 'full',
      });
      setResult(data);
      try { localStorage.setItem(LS_KEY, JSON.stringify({ startDate, endDate, topN, benchmark })); } catch {}
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest-Fehler');
    } finally {
      setLoading(false);
    }
  };

  const handleComparisonSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCompLoading(true);
    setCompError(null);
    setCompResults({});
    try {
      const modes: BacktestMode[] = ['quant_only', 'quant_ml', 'full'];
      const commonParams = {
        model_run_id: runId,
        start_date: startDate,
        end_date: endDate,
        top_n: topN,
        benchmark_ticker: benchmark,
      };
      const [r1, r2, r3] = await Promise.all(
        modes.map((mode) => runBacktest({ ...commonParams, mode }))
      );
      setCompResults({ quant_only: r1, quant_ml: r2, full: r3 });
      try { localStorage.setItem(LS_KEY, JSON.stringify({ startDate, endDate, topN, benchmark })); } catch {}
    } catch (err) {
      setCompError(err instanceof Error ? err.message : 'Vergleichs-Backtest fehlgeschlagen');
    } finally {
      setCompLoading(false);
    }
  };

  // Build single-mode chart data
  const chartData =
    result?.series.dates.map((d, i) => ({
      date: d,
      PRISMA: result.series.prisma[i],
      Universum: result.series.universe[i],
      Benchmark: result.series.benchmark[i],
    })) ?? [];

  // Build comparison chart data — merge all three modes on dates from quant_only
  const compChartData = (() => {
    const base = compResults.quant_only;
    if (!base) return [];
    return base.series.dates.map((d, i) => {
      const point: Record<string, number | string> = { date: d };
      if (compResults.quant_only) point['Quant only'] = compResults.quant_only.series.prisma[i];
      if (compResults.quant_ml) point['Quant+ML'] = compResults.quant_ml.series.prisma[i] ?? 1;
      if (compResults.full) point['Quant+ML+Makro'] = compResults.full.series.prisma[i] ?? 1;
      if (compResults.quant_only) point['SMI Benchmark'] = compResults.quant_only.series.benchmark[i];
      return point;
    });
  })();

  const sharedFormFields = (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <label className="mb-1 block text-sm font-medium">Run</label>
        <select
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          disabled={runsQuery.isLoading}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          data-testid="backtest-run-id"
        >
          <option value="">
            {runsQuery.isLoading
              ? 'Lädt Runs…'
              : completedRuns.length === 0
                ? 'Keine abgeschlossenen Runs'
                : '— Run wählen —'}
          </option>
          {runId && !completedRuns.some((r) => r.id === runId) && (
            <option value={runId}>{runId} (aus Link)</option>
          )}
          {completedRuns.map((r) => (
            <option key={r.id} value={r.id}>
              {runDateFmt.format(new Date(r.created_at))} · {r.universe_name}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium">Top N</label>
        <Input
          type="number"
          value={topN}
          onChange={(e) => setTopN(Number(e.target.value))}
          min={1}
          max={10}
          data-testid="backtest-top-n"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium">Von</label>
        <Input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          data-testid="backtest-start-date"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium">Bis</label>
        <Input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          data-testid="backtest-end-date"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium">Benchmark</label>
        <Input
          value={benchmark}
          onChange={(e) => setBenchmark(e.target.value)}
          data-testid="backtest-benchmark"
        />
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Tab switcher */}
      <div className="flex gap-2 border-b pb-0">
        <button
          type="button"
          onClick={() => setTab('single')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'single'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Einzelner Backtest
        </button>
        <button
          type="button"
          onClick={() => setTab('comparison')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            tab === 'comparison'
              ? 'border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
          data-testid="comparison-tab-btn"
        >
          Modell-Vergleich
        </button>
      </div>

      {/* ---- Single backtest tab ---- */}
      {tab === 'single' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Backtest</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleSubmit}
                className="space-y-4"
                data-testid="backtest-form"
              >
                {sharedFormFields}
                <div className="flex items-center gap-2 pt-2">
                  <Button
                    type="submit"
                    disabled={loading || !runId}
                    className="flex-1"
                    data-testid="start-backtest-btn"
                  >
                    {loading ? 'Läuft…' : 'Backtest starten'}
                  </Button>
                  <button
                    type="button"
                    onClick={handleShare}
                    disabled={!runId}
                    className="shrink-0 inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm hover:bg-muted transition-colors disabled:opacity-40"
                    data-testid="backtest-share-btn"
                  >
                    {shareCopied ? 'Kopiert!' : 'Link teilen'}
                  </button>
                </div>
              </form>
              {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
            </CardContent>
          </Card>

          {result && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div>
                  <CardTitle>Performance-Vergleich</CardTitle>
                  <CardDescription data-testid="backtest-result-meta">
                    {startDate} – {endDate} · Top {topN} · {benchmark}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => exportSeriesCsv(result)}
                    className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
                    data-testid="backtest-series-csv-btn"
                  >
                    <Download className="h-3 w-3" />
                    Zeitreihe CSV
                  </button>
                  <button
                    onClick={() => exportMetricsCsv(result.prisma_metrics, result.universe_metrics, result.benchmark_metrics)}
                    className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
                    data-testid="backtest-metrics-csv-btn"
                  >
                    <Download className="h-3 w-3" />
                    CSV
                  </button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                <div data-testid="backtest-chart" className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis
                        tickFormatter={(v: number) => `${((v - 1) * 100).toFixed(0)}%`}
                      />
                      <Tooltip
                        formatter={(v: number) => `${((v - 1) * 100).toFixed(2)}%`}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="PRISMA"
                        stroke="#6366f1"
                        dot={false}
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="Universum"
                        stroke="#10b981"
                        dot={false}
                        strokeWidth={2}
                      />
                      <Line
                        type="monotone"
                        dataKey="Benchmark"
                        stroke="#f59e0b"
                        dot={false}
                        strokeWidth={2}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <MetricsTable
                  prisma={result.prisma_metrics}
                  universum={result.universe_metrics}
                  benchmark={result.benchmark_metrics}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* ---- Comparison tab ---- */}
      {tab === 'comparison' && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Modell-Vergleich</CardTitle>
              <CardDescription>
                Führt drei Backtests parallel aus: Quant only, Quant+ML und Quant+ML+Makro.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form
                onSubmit={handleComparisonSubmit}
                className="space-y-4"
                data-testid="comparison-form"
              >
                {sharedFormFields}
                <div className="pt-2">
                  <Button
                    type="submit"
                    disabled={compLoading || !runId}
                    className="w-full"
                    data-testid="start-comparison-btn"
                  >
                    {compLoading ? 'Vergleich läuft…' : 'Vergleich starten'}
                  </Button>
                </div>
              </form>
              {compError && <p className="mt-4 text-sm text-destructive">{compError}</p>}
            </CardContent>
          </Card>

          {Object.keys(compResults).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Modell-Vergleich: Performance</CardTitle>
                <CardDescription data-testid="comparison-result-meta">
                  {startDate} – {endDate} · Top {topN} · Benchmark: {benchmark}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Combined line chart */}
                <div data-testid="comparison-chart" className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={compChartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis
                        tickFormatter={(v: number) => `${((v - 1) * 100).toFixed(0)}%`}
                      />
                      <Tooltip
                        formatter={(v: number) => `${((v - 1) * 100).toFixed(2)}%`}
                      />
                      <Legend />
                      {compResults.quant_only && (
                        <Line
                          type="monotone"
                          dataKey="Quant only"
                          stroke={MODE_COLORS.quant_only}
                          dot={false}
                          strokeWidth={2}
                        />
                      )}
                      {compResults.quant_ml && (
                        <Line
                          type="monotone"
                          dataKey="Quant+ML"
                          stroke={MODE_COLORS.quant_ml}
                          dot={false}
                          strokeWidth={2}
                        />
                      )}
                      {compResults.full && (
                        <Line
                          type="monotone"
                          dataKey="Quant+ML+Makro"
                          stroke={MODE_COLORS.full}
                          dot={false}
                          strokeWidth={2}
                        />
                      )}
                      <Line
                        type="monotone"
                        dataKey="SMI Benchmark"
                        stroke="#9ca3af"
                        dot={false}
                        strokeWidth={1.5}
                        strokeDasharray="4 4"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* Sharpe Ratio highlight cards */}
                <div className="grid grid-cols-3 gap-4" data-testid="comparison-sharpe-cards">
                  {(['quant_only', 'quant_ml', 'full'] as BacktestMode[]).map((m) => {
                    const r = compResults[m];
                    if (!r) return null;
                    const sharpe = parseFloat(r.prisma_metrics.sharpe);
                    return (
                      <div
                        key={m}
                        className="rounded-lg border p-4 text-center"
                        style={{ borderColor: MODE_COLORS[m] }}
                      >
                        <p className="text-xs text-muted-foreground mb-1">{MODE_LABELS[m]}</p>
                        <p
                          className="text-2xl font-bold tabular-nums"
                          style={{ color: MODE_COLORS[m] }}
                        >
                          {isNaN(sharpe) ? '—' : sharpe.toFixed(2)}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">Sharpe Ratio</p>
                      </div>
                    );
                  })}
                </div>

                {/* Full metrics comparison table */}
                <ComparisonMetricsTable results={compResults} />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

export default function BacktestPage() {
  return (
    <Suspense>
      <BacktestContent />
    </Suspense>
  );
}
