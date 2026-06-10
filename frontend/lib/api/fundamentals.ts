import { apiFetch } from './client';

export interface FundamentalsRead {
  ticker: string;
  pe_ratio: number | null;
  pb_ratio: number | null;
  fcf_yield: number | null;
  operating_margin: number | null;
  dividend_yield: number | null;
  disclaimer: string;
}

export function getFundamentals(ticker: string): Promise<FundamentalsRead> {
  return apiFetch<FundamentalsRead>(`/api/v1/stocks/${ticker}/fundamentals`);
}
