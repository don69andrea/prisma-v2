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
  sector_hint?: string | null;
  investment_amount?: "under_10k" | "10k_100k" | "over_100k";
  esg_preference?: "yes" | "no" | "indifferent";
  income_preference?: "dividends" | "growth" | "balanced";
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

// --- Conversational Discovery Session API ---

export interface DiscoverySessionResponse {
  session_id: string;
}

export interface PartialProfile {
  session_id: string;
  risk_profile: string;
  sector_affinity: string[];
  time_horizon: string;
  investment_goal: string;
  confidence_score: number;
  onboarding_complete: boolean;
  sector_hint?: string | null;
  investment_amount?: "under_10k" | "10k_100k" | "over_100k";
  esg_preference?: "yes" | "no" | "indifferent";
  income_preference?: "dividends" | "growth" | "balanced";
}

export interface AnswerResponse {
  session_id: string;
  next_turn: number | null;
  confidence: number;
  partial_profile: PartialProfile;
}

export interface CompleteDiscoveryResponse {
  profile: PartialProfile;
  recommended_stocks: DiscoveredStock[];
}

export async function createDiscoverySession(): Promise<DiscoverySessionResponse> {
  return apiFetch<DiscoverySessionResponse>('/api/v1/discovery/session', {
    method: 'POST',
  });
}

export async function submitAnswer(
  sessionId: string,
  turn: number,
  answer: string | string[],
  extra?: { brand_data?: Record<string, Record<string, unknown>> },
): Promise<AnswerResponse> {
  return apiFetch<AnswerResponse>('/api/v1/discovery/answer', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, turn, answer, ...extra }),
  });
}

export async function completeDiscovery(sessionId: string): Promise<CompleteDiscoveryResponse> {
  return apiFetch<CompleteDiscoveryResponse>('/api/v1/discovery/complete', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}

// --- Legacy profile save / personalized stocks ---

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
