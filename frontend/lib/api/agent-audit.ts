import { apiFetch } from './client';

// Types mirror backend/interfaces/rest/schemas/crypto_dashboard.py

export interface AgentRunDetail {
  technical?: {
    coin: string;
    stance: 'BULLISH' | 'NEUTRAL' | 'BEARISH';
    consensus: string;
    key_signals: string[];
    confidence: number;
    reasoning: string;
  };
  onchain?: {
    coin: string;
    valuation: 'CHEAP' | 'FAIR' | 'EXPENSIVE';
    network_health: 'STRONG' | 'NEUTRAL' | 'WEAK';
    confidence: number;
    reasoning: string;
  };
  sentiment?: {
    coin: string;
    score: number;
    regime: 'FEAR' | 'NEUTRAL' | 'GREED';
    news_surprise: boolean | null;
    veto: boolean;
    reasoning: string;
    sources: string[];
  };
  macro?: {
    regime: 'RISK_ON' | 'NEUTRAL' | 'RISK_OFF';
    drivers: string[];
    confidence: number;
    reasoning: string;
  };
  bull?: {
    thesis: string;
    strongest_points: string[];
    risks_acknowledged: string[];
  };
  bear?: {
    thesis: string;
    strongest_points: string[];
    counter_to_bull: string[];
  };
  risk?: {
    approve: boolean;
    max_size: number;
    breaches: string[];
    reasoning: string;
  };
}

export interface AgentAuditResponse {
  audit_trail_id: string;
  coin: string;
  asof: string;
  agent_run: AgentRunDetail;
  created_at: string;
}

export interface HitlConfirmRequest {
  audit_trail_id: string;
  decision: 'proceed' | 'abort';
}

export interface HitlConfirmResponse {
  id: string;
  audit_trail_id: string;
  coin: string;
  decision: 'proceed' | 'abort';
  decided_at: string;
}

export function getAgentAudit(coin: string): Promise<AgentAuditResponse> {
  return apiFetch<AgentAuditResponse>(`/api/v1/crypto/${encodeURIComponent(coin)}/agent-audit`);
}

export function confirmHitl(coin: string, body: HitlConfirmRequest): Promise<HitlConfirmResponse> {
  return apiFetch<HitlConfirmResponse>(`/api/v1/crypto/${encodeURIComponent(coin)}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}
