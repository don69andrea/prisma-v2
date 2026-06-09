import { apiFetch } from './client';

export interface DividendEntry {
  date: string;
  amount_chf: number;
}

export interface DividendData {
  ticker: string;
  last_dividend_chf: number | null;
  ex_date: string | null;
  dividend_yield_pct: number | null;
  history: DividendEntry[];
  disclaimer: string;
}

export function getDividends(ticker: string): Promise<DividendData> {
  return apiFetch<DividendData>(`/api/v1/stocks/${ticker}/dividends`);
}
