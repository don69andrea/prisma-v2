import { apiFetch } from './client';

export type SignalType = 'BUY' | 'HOLD' | 'WATCH';

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
