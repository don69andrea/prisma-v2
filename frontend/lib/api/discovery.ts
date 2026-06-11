import { apiFetch } from './client';

export interface InvestorProfilePayload {
  session_id: string;
  risk_profile: 'conservative' | 'moderate' | 'aggressive';
  sector_affinity: string[];
  time_horizon: 'short' | 'medium' | 'long';
  investment_goal: 'housing' | 'retirement' | 'freedom' | 'beat_savings' | 'other';
  profession?: string;
  known_tickers: string[];
}

export interface InvestorProfileResponse {
  session_id: string;
  risk_profile: string;
  sector_affinity: string[];
  time_horizon: string;
  investment_goal: string;
  confidence_score: number;
  onboarding_complete: boolean;
}

export interface DiscoveredStock {
  ticker: string;
  name: string;
  sector: string | null;
  market_cap_chf: string | null;
  exchange: string;
}

export interface DiscoveryResponse {
  session_id: string;
  total: number;
  stocks: DiscoveredStock[];
}

export async function saveProfile(
  payload: InvestorProfilePayload,
): Promise<InvestorProfileResponse> {
  return apiFetch<InvestorProfileResponse>('/api/v1/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getPersonalizedStocks(sessionId: string): Promise<DiscoveryResponse> {
  return apiFetch<DiscoveryResponse>(`/api/v1/discover?session_id=${encodeURIComponent(sessionId)}`);
}
