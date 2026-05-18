'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { runBacktest, type BacktestResult } from '@/lib/api/backtest';

function BacktestContent() {
  const searchParams = useSearchParams();
  const [runId, setRunId] = useState(searchParams.get('run_id') ?? '');
  const [startDate, setStartDate] = useState('2025-01-01');
  const [endDate, setEndDate] = useState('2025-12-31');
  const [topN, setTopN] = useState(3);
  const [benchmark, setBenchmark] = useState('^SSMI');
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest-Fehler');
    } finally {
      setLoading(false);
    }
  };

  const chartData =
    result?.series.dates.map((d, i) => ({
      date: d,
      PRISMA: parseFloat(result.series.prisma[i]),
      Universum: parseFloat(result.series.universe[i]),
      Benchmark: parseFloat(result.series.benchmark[i]),
    })) ?? [];

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Backtest</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit}
            className="grid grid-cols-2 gap-4"
            data-testid="backtest-form"
          >
            <div>
              <label className="mb-1 block text-sm font-medium">Run ID</label>
              <Input
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
                placeholder="UUID des Ranking-Runs"
                data-testid="backtest-run-id"
              />
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
            <div className="flex items-end">
              <Button
                type="submit"
                disabled={loading || !runId}
                className="w-full"
                data-testid="start-backtest-btn"
              >
                {loading ? 'Läuft…' : 'Backtest starten'}
              </Button>
            </div>
          </form>
          {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Performance-Vergleich</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
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
