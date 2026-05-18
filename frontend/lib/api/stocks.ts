import { apiFetch } from './client';

// ---- Types ----------------------------------------------------------------

export interface StockRead {
  id: string;
  ticker: string;
  name: string;
  isin: string | null;
  sector: string | null;
  country: string | null;
  currency: string;
}

export interface LatestRankingSnapshot {
  total_rank: number | null;
  weighted_avg: number | null;
  is_sweet_spot: boolean;
  per_model_ranks: Record<string, number | null>;
}

export interface StockFactsheet {
  stock: StockRead;
  latest_ranking: LatestRankingSnapshot | null;
}

export interface PricePoint {
  date: string;   // ISO-8601, e.g. "2025-05-18"
  close: number;
}

export interface PriceSeriesResponse {
  ticker: string;
  prices: PricePoint[];
}

// ---- API functions --------------------------------------------------------

export function getFactsheet(ticker: string): Promise<StockFactsheet> {
  return apiFetch<StockFactsheet>(`/api/v1/stocks/${ticker}/factsheet`);
}

export function getPrices(ticker: string, days = 252): Promise<PriceSeriesResponse> {
  return apiFetch<PriceSeriesResponse>(`/api/v1/stocks/${ticker}/prices?days=${days}`);
}
