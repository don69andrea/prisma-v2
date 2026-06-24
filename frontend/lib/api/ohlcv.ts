import { apiFetch } from './client';

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OHLCVResponse {
  coin: string;
  symbol: string;
  bars: OHLCVBar[];
}

export function getOHLCV(coin: string, days = 120): Promise<OHLCVResponse> {
  return apiFetch<OHLCVResponse>(`/api/v1/crypto/${encodeURIComponent(coin)}/ohlcv?days=${days}`);
}
