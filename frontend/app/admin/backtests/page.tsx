'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { listRuns } from '@/lib/api/runs';
import { runBacktest, type BacktestResult, type PortfolioMetrics } from '@/lib/api/backtests';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

function pct(v: number) {
  return `${(v * 100).toFixed(2)}%`;
}

function MetricsTable({
  prisma,
  universe,
  benchmark,
}: {
  prisma: PortfolioMetrics;
  universe: PortfolioMetrics;
  benchmark: PortfolioMetrics;
}) {
  const rows: { label: string; key: keyof PortfolioMetrics; format: (v: number) => string }[] = [
    { label: 'Total Return', key: 'total_return', format: pct },
    { label: 'CAGR', key: 'cagr', format: pct },
    { label: 'Volatilität (p.a.)', key: 'annual_vol', format: pct },
    { label: 'Sharpe Ratio', key: 'sharpe', format: (v) => v.toFixed(2) },
    { label: 'Max Drawdown', key: 'max_drawdown', format: pct },
  ];

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-border text-left text-muted-foreground">
          <th className="pb-2 pr-4 font-medium">Kennzahl</th>
          <th className="pb-2 pr-4 font-medium text-indigo-400">PRISMA</th>
          <th className="pb-2 pr-4 font-medium text-purple-400">Universum</th>
          <th className="pb-2 font-medium text-muted-foreground">Benchmark</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key} className="border-b border-border/50 last:border-0">
            <td className="py-2 pr-4 text-muted-foreground">{r.label}</td>
            <td className="py-2 pr-4 font-mono font-medium text-indigo-400">{r.format(prisma[r.key])}</td>
            <td className="py-2 pr-4 font-mono text-purple-400">{r.format(universe[r.key])}</td>
            <td className="py-2 font-mono text-muted-foreground">{r.format(benchmark[r.key])}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function AdminBacktestsPage() {
  const today = new Date().toISOString().slice(0, 10);
  const oneYearAgo = new Date(Date.now() - 365 * 86400 * 1000).toISOString().slice(0, 10);

  const [form, setForm] = useState({
    runId: '',
    startDate: oneYearAgo,
    endDate: today,
    topN: 3,
    benchmark: '^SSMI',
    mode: 'full' as 'quant_only' | 'quant_ml' | 'full',
  });

  const { data: runs } = useQuery({
    queryKey: ['admin-runs'],
    queryFn: () => listRuns(50),
  });

  const completedRuns = runs?.filter((r) => r.status === 'completed') ?? [];

  const mutation = useMutation({
    mutationFn: () =>
      runBacktest({
        model_run_id: form.runId,
        start_date: form.startDate,
        end_date: form.endDate,
        top_n: form.topN,
        benchmark_ticker: form.benchmark,
        mode: form.mode,
      }),
  });

  const result: BacktestResult | undefined = mutation.data;

  const chartData = result
    ? result.series.dates.map((date, i) => ({
        date: new Date(date).toLocaleDateString('de-CH', { month: 'short', year: '2-digit' }),
        PRISMA: +(result.series.prisma[i] * 100).toFixed(2),
        Universum: +(result.series.universe[i] * 100).toFixed(2),
        Benchmark: +(result.series.benchmark[i] * 100).toFixed(2),
      }))
    : [];

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Backtests</h1>

      {/* Form */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-4">
        <h2 className="text-sm font-medium">Backtest konfigurieren</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Ranking-Run</label>
            <select
              value={form.runId}
              onChange={(e) => setForm((p) => ({ ...p, runId: e.target.value }))}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            >
              <option value="">Run wählen…</option>
              {completedRuns.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.universe_name} · {new Date(r.created_at).toLocaleDateString('de-CH')}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Start-Datum</label>
            <input
              type="date"
              value={form.startDate}
              onChange={(e) => setForm((p) => ({ ...p, startDate: e.target.value }))}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">End-Datum</label>
            <input
              type="date"
              value={form.endDate}
              onChange={(e) => setForm((p) => ({ ...p, endDate: e.target.value }))}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Top-N</label>
            <input
              type="number"
              min={1}
              max={20}
              value={form.topN}
              onChange={(e) => setForm((p) => ({ ...p, topN: parseInt(e.target.value) || 3 }))}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Benchmark</label>
            <input
              type="text"
              value={form.benchmark}
              onChange={(e) => setForm((p) => ({ ...p, benchmark: e.target.value }))}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background font-mono"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-muted-foreground">Modus</label>
            <select
              value={form.mode}
              onChange={(e) => setForm((p) => ({ ...p, mode: e.target.value as typeof form.mode }))}
              className="w-full text-sm px-3 py-2 rounded border border-border bg-background"
            >
              <option value="full">Full (Quant + ML + Makro)</option>
              <option value="quant_ml">Quant + ML</option>
              <option value="quant_only">Nur Quant</option>
            </select>
          </div>
        </div>

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || !form.runId}
          className="text-sm px-4 py-2 rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          {mutation.isPending ? 'Backtest läuft…' : 'Backtest starten'}
        </button>

        {mutation.isError && (
          <p className="text-xs text-destructive">Fehler beim Backtest — Run überprüfen.</p>
        )}
      </div>

      {/* Results */}
      {result && (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">PRISMA Return</p>
              <p className={`text-2xl font-bold mt-1 ${result.prisma_metrics.total_return >= 0 ? 'text-emerald-500' : 'text-destructive'}`}>
                {pct(result.prisma_metrics.total_return)}
              </p>
              <p className="text-xs text-muted-foreground">
                Benchmark: {pct(result.benchmark_metrics.total_return)}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">PRISMA Sharpe</p>
              <p className="text-2xl font-bold mt-1">{result.prisma_metrics.sharpe.toFixed(2)}</p>
              <p className="text-xs text-muted-foreground">
                Benchmark: {result.benchmark_metrics.sharpe.toFixed(2)}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground uppercase tracking-wide">Max Drawdown</p>
              <p className="text-2xl font-bold mt-1 text-destructive">
                {pct(result.prisma_metrics.max_drawdown)}
              </p>
              <p className="text-xs text-muted-foreground">
                Benchmark: {pct(result.benchmark_metrics.max_drawdown)}
              </p>
            </div>
          </div>

          {/* Line Chart */}
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h2 className="text-sm font-medium">Performance-Verlauf (kumuliert, %)</h2>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}%`} width={48} />
                <Tooltip formatter={(v: number) => [`${v.toFixed(2)}%`]} />
                <Legend />
                <Line type="monotone" dataKey="PRISMA" stroke="#6366f1" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="Universum" stroke="#a78bfa" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                <Line type="monotone" dataKey="Benchmark" stroke="#71717a" strokeWidth={1.5} dot={false} strokeDasharray="2 2" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Metrics Table */}
          <div className="rounded-lg border border-border bg-card p-4 space-y-3">
            <h2 className="text-sm font-medium">Kennzahlen-Vergleich</h2>
            <MetricsTable
              prisma={result.prisma_metrics}
              universe={result.universe_metrics}
              benchmark={result.benchmark_metrics}
            />
          </div>
        </>
      )}
    </div>
  );
}
