import { apiFetch } from './client';

export interface PortfolioMetrics {
  total_return: string;
  cagr: string;
  annual_vol: string;
  sharpe: string;
  max_drawdown: string;
}

export interface BacktestResult {
  id: string;
  model_run_id: string;
  series: {
    dates: string[];
    prisma: number[];
    universe: number[];
    benchmark: number[];
  };
  prisma_metrics: PortfolioMetrics;
  universe_metrics: PortfolioMetrics;
  benchmark_metrics: PortfolioMetrics;
}

export function runBacktest(params: {
  model_run_id: string;
  start_date: string;
  end_date: string;
  top_n: number;
  benchmark_ticker: string;
}): Promise<BacktestResult> {
  return apiFetch<BacktestResult>('/api/v1/backtests', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
