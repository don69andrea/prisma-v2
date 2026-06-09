import { apiFetch } from './client';

export interface ViacFondsItem {
  name: string;
  description: string;
  equity_ratio: number;
}

export interface FondsPosition {
  ticker: string;
  weight: number;
}

export interface FondsVergleichRequest {
  fonds_name: string;
  positions: FondsPosition[];
  lookback_years?: number;
}

export interface PortfolioMetrics {
  expected_return_pa: string;
  volatility_pa: string;
  sharpe_ratio: string | null;
  max_drawdown: string;
}

export interface FondsVergleichResponse {
  fonds_name: string;
  fonds_metrics: PortfolioMetrics;
  custom_metrics: PortfolioMetrics;
  snapshot_date: string;
  disclaimer: string;
}

export async function listFonds(): Promise<ViacFondsItem[]> {
  return apiFetch<ViacFondsItem[]>('/api/v1/fonds');
}

export async function compareFonds(req: FondsVergleichRequest): Promise<FondsVergleichResponse> {
  return apiFetch<FondsVergleichResponse>('/api/v1/fonds/vergleich', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
