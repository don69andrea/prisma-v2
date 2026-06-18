import { apiFetch } from './client';

export interface RunBacktestRequest {
  model_run_id: string;
  start_date: string;
  end_date: string;
  top_n?: number;
  benchmark_ticker?: string;
  mode?: 'quant_only' | 'quant_ml' | 'full';
}

export interface PortfolioMetrics {
  total_return: number;
  cagr: number;
  annual_vol: number;
  sharpe: number;
  max_drawdown: number;
}

export interface BacktestSeries {
  dates: string[];
  prisma: number[];
  universe: number[];
  benchmark: number[];
}

export interface BacktestResult {
  id: string;
  model_run_id: string;
  start_date: string;
  end_date: string;
  top_n: number;
  benchmark_ticker: string;
  mode: string;
  prisma_metrics: PortfolioMetrics;
  universe_metrics: PortfolioMetrics;
  benchmark_metrics: PortfolioMetrics;
  series: BacktestSeries;
  created_at: string;
}

export async function runBacktest(body: RunBacktestRequest): Promise<BacktestResult> {
  return apiFetch<BacktestResult>('/api/v1/backtests', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getBacktest(id: string): Promise<BacktestResult> {
  return apiFetch<BacktestResult>(`/api/v1/backtests/${id}`);
}
