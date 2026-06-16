import { apiFetch } from './client';

export type SignalType = 'BUY' | 'HOLD' | 'SELL';

export interface DecisionSignal {
  ticker: string;
  snapshot_date: string;
  signal: SignalType;
  confidence: number;
  weighted_score: number;
  quant_score: number;
  ml_score: number;
  macro_score: number;
  is_3a_eligible: boolean;
  signal_reason: string;
}

export interface DecisionListResponse {
  items: DecisionSignal[];
  total: number;
}

export async function listDecisions(
  universeId: string,
  signal?: SignalType,
  eligibleOnly?: boolean,
): Promise<DecisionListResponse> {
  const params = new URLSearchParams({ universe_id: universeId });
  if (signal) params.set('signal', signal);
  if (eligibleOnly) params.set('eligible_only', 'true');
  return apiFetch<DecisionListResponse>(`/api/v1/decisions?${params.toString()}`);
}

export interface ExplainRequest {
  ticker: string;
  signal: string;
  confidence: number;
  quant_score: number;
  ml_score: number;
  macro_score: number;
  weighted_score: number;
}

export interface ExplainResponse {
  ticker: string;
  overall: string;
  quant_why: string;
  ml_why: string;
  macro_why: string;
  risk_note: string;
}

export async function explainDecision(body: ExplainRequest): Promise<ExplainResponse> {
  return apiFetch<ExplainResponse>('/api/v1/decisions/explain', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function liveDecisions(
  tickers: string[],
  signal?: SignalType,
  eligibleOnly?: boolean,
): Promise<DecisionListResponse> {
  if (tickers.length > 12) {
    throw new Error(`Maximal 12 Ticker erlaubt (${tickers.length} übergeben)`)
  }
  const params = new URLSearchParams({ tickers: tickers.join(',') });
  if (signal) params.set('signal', signal);
  if (eligibleOnly) params.set('eligible_only', 'true');
  return apiFetch<DecisionListResponse>(`/api/v1/decisions/live?${params.toString()}`);
}
