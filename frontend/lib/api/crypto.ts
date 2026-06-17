import { apiFetch } from './client';

export interface CryptoSignal {
  ticker: string;
  name: string;
  signal: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL';
  score: number;
  score_components: {
    momentum: number;
    trend: number;
    sentiment: number;
    markt: number;
    risiko: number;
  };
  signal_reason_de: string;
  price_chf: number | null;
  market_cap_chf: number | null;
  price_change_24h_pct: number | null;
  price_change_7d_pct: number | null;
  ath_change_pct: number | null;
  market_cap_rank: number | null;
  rsi_14: number;
  macd_signal: 'bullish' | 'bearish';
  volatility_30d_pct: number;
  correlation_smi_1y: number;
  fear_greed_value: number;
  fear_greed_label: string;
  has_six_etp: boolean;
  timestamp: string;
}

export interface FearGreedData {
  value: number;
  label: string;
  timestamp: string;
}

export async function getCryptoSignals(): Promise<CryptoSignal[]> {
  return apiFetch<CryptoSignal[]>('/api/v1/crypto/signals');
}

export async function getCryptoSignal(ticker: string): Promise<CryptoSignal> {
  return apiFetch<CryptoSignal>(`/api/v1/crypto/signals/${ticker}`);
}

export async function getFearGreed(): Promise<FearGreedData> {
  return apiFetch<FearGreedData>('/api/v1/crypto/fear-greed');
}

export function signalColor(signal: CryptoSignal['signal']): string {
  switch (signal) {
    case 'STRONG_BUY': return '#00c853';
    case 'BUY':        return '#7ee787';
    case 'HOLD':       return '#ffa657';
    case 'SELL':       return '#f85149';
    case 'STRONG_SELL': return '#da3633';
  }
}

export function signalLabel(signal: CryptoSignal['signal']): string {
  switch (signal) {
    case 'STRONG_BUY': return 'STRONG BUY';
    case 'BUY':        return 'BUY';
    case 'HOLD':       return 'HOLD';
    case 'SELL':       return 'SELL';
    case 'STRONG_SELL': return 'STRONG SELL';
  }
}

export function fearGreedLabel(value: number): string {
  if (value <= 25) return 'Extreme Angst';
  if (value <= 40) return 'Angst';
  if (value <= 60) return 'Neutral';
  if (value <= 75) return 'Gier';
  return 'Extreme Gier';
}

export function fearGreedColor(value: number): string {
  if (value <= 25) return '#7ee787';
  if (value <= 40) return '#a5f3b4';
  if (value <= 60) return '#ffa657';
  if (value <= 75) return '#f85149';
  return '#da3633';
}

export interface CryptoHistoryPoint {
  date: string;
  signal: string;
  score: number;
  price_chf: number | null;
  fear_greed_value: number;
  rsi_14: number;
  detected_patterns: string[];
  pattern_score: number;
}

export async function getCryptoHistory(ticker: string, days: number): Promise<CryptoHistoryPoint[]> {
  return apiFetch<CryptoHistoryPoint[]>(`/api/v1/crypto/history/${ticker}?days=${days}`);
}
