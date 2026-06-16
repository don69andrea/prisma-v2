import { apiFetch } from './client';

export type BacktestMode = 'quant_only' | 'quant_ml' | 'full';

export interface PortfolioMetrics {
  total_return: number;
  cagr: number;
  annual_vol: number;
  sharpe: number;
  max_drawdown: number;
}

export interface BacktestResult {
  id: string;
  model_run_id: string;
  start_date: string;
  end_date: string;
  /** Tatsächlich abgedecktes Fenster der Marktdaten (kann kürzer sein als start_date/end_date). */
  actual_start_date: string;
  actual_end_date: string;
  top_n: number;
  benchmark_ticker: string;
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
  mode?: BacktestMode;
}): Promise<BacktestResult> {
  return apiFetch<BacktestResult>('/api/v1/backtests', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
