import { apiFetch } from './client';

export interface HoldingWeightInput {
  ticker: string;
  weight: number;
}

export interface MonteCarloRequest {
  holdings: HoldingWeightInput[];
  monthly_contribution: number;
  years: number;
  initial_value?: number;
  n_simulations?: number;
}

export interface MonteCarloResponse {
  p5: number[];
  p50: number[];
  p95: number[];
  final_distribution: number[];
  prob_positive_return: number;
  prob_500k: number;
  contribution_total: number;
  months: number;
}

export async function runMonteCarlo(req: MonteCarloRequest): Promise<MonteCarloResponse> {
  return apiFetch<MonteCarloResponse>('/api/v1/portfolio/monte-carlo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
