import { apiFetch } from './client';

// Types mirror backend/interfaces/rest/schemas/signals.py

export type CryptoAction = 'BUY' | 'HOLD' | 'SELL';

export interface SignalVector {
  coin: string;
  asof: string; // ISO date
  action: CryptoAction;
  size_factor: number; // 0.0–1.5
  consensus: string; // e.g. "3/3", "2/3"
  sub_scores: Record<string, number>; // ma_signal, macd_signal, rsi_signal, vol_pred, momentum_rank, onchain_score
  confidence: number; // 0.0–1.0
  disclaimer: string;
}

export interface BacktestReport {
  coin: string;
  cagr: number;
  sharpe: number;
  max_dd: number; // negative float
  calmar: number;
  beats_exposure_matched: boolean;
  n_trades: number;
  equity_curve: [string, number][]; // [ISO date, portfolio value]
}

export interface PortfolioCoinStats {
  avg_weight: number;
  days_in_portfolio: number;
}

export interface PortfolioBacktestReport {
  coins: string[];
  sharpe: number;
  calmar: number;
  max_dd: number;
  cagr: number;
  avg_exposure: number;
  n_rebalances: number;
  beats_equal_weight_bh: boolean;
  beats_exposure_matched: boolean;
  equity_curve: [string, number][];
  per_coin_stats: Record<string, PortfolioCoinStats>;
  pit_universe: Record<string, string>;
  costs: number;
}

export interface MetaLabelReport {
  coin: string;
  label_method: 'triple_barrier' | 'trend_scan';
  classifier: 'logreg' | 'lgbm';
  n_folds: number;
  oos_precision: number;
  oos_recall: number;
  always_trade_sharpe: number;
  always_trade_calmar: number;
  meta_filtered_sharpe: number;
  meta_filtered_calmar: number;
  n_trades_always: number;
  n_trades_filtered: number;
  beats_baseline: boolean;
  finding: 'positive' | 'secondary_pass' | 'negative';
  finding_reason: string;
}

export interface TradeSignal {
  coin: string;
  action: CryptoAction;
  size_factor: number;
  confidence: number;
  rationale_by_layer: Record<string, string>;
  audit_trail_id: string; // UUID string
  disclaimer: string;
}

// --- Fetch functions ---

export function listSignals(): Promise<SignalVector[]> {
  return apiFetch<SignalVector[]>('/api/v1/signals');
}

export function getSignal(coin: string): Promise<SignalVector> {
  return apiFetch<SignalVector>(`/api/v1/signals/${encodeURIComponent(coin)}`);
}

export function getBacktest(coin: string): Promise<BacktestReport> {
  return apiFetch<BacktestReport>(`/api/v1/backtest/${encodeURIComponent(coin)}`);
}

export function getPortfolioBacktest(): Promise<PortfolioBacktestReport> {
  return apiFetch<PortfolioBacktestReport>('/api/v1/backtest/portfolio');
}

export function getMetaLabel(coin: string): Promise<MetaLabelReport> {
  return apiFetch<MetaLabelReport>(`/api/v1/signals/${encodeURIComponent(coin)}/meta-label`);
}

export function getAgentSignal(coin: string): Promise<TradeSignal> {
  return apiFetch<TradeSignal>(`/api/v1/agent-signal/${encodeURIComponent(coin)}`);
}
