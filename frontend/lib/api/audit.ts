import { apiFetch } from './client';

export type SignalType = 'BUY' | 'HOLD' | 'SELL';

export interface AuditRecord {
  id: string;
  ticker: string;
  signal: SignalType;
  weighted_score: number;
  quant_score: number;
  ml_score: number;
  macro_score: number;
  is_3a_eligible: boolean;
  snapshot_date: string;
  computed_at: string;
  explanation_de: string;
}

export interface AuditListResponse {
  ticker: string;
  records: AuditRecord[];
  total: number;
}

export async function getAuditTrail(ticker: string): Promise<AuditListResponse> {
  return apiFetch<AuditListResponse>(`/api/v1/decisions/${encodeURIComponent(ticker)}/audit`);
}

export async function computeAndSaveAudit(ticker: string): Promise<AuditRecord> {
  return apiFetch<AuditRecord>(`/api/v1/decisions/${encodeURIComponent(ticker)}/audit`, {
    method: 'POST',
  });
}
