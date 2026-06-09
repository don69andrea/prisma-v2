import { apiFetch } from './client';

export interface FundamentalsData {
  ticker: string;
  pe_ratio: number | null;
  pb_ratio: number | null;
  eps_chf: number | null;
  dividend_yield_pct: number | null;
  disclaimer: string;
}

export function getFundamentals(ticker: string): Promise<FundamentalsData> {
  return apiFetch<FundamentalsData>(`/api/v1/stocks/${ticker}/fundamentals`);
}
