import { apiFetch } from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InvestorProfileResponse {
  beruf: string;
  ziel: 'housing' | 'retirement' | 'freedom' | 'beat_savings';
  risiko: 'conservative' | 'moderate' | 'aggressive';
  brands: string[];
}

export interface DiscoveredStock {
  ticker: string;
  name: string;
  score: number;
  reason: string;
}

export interface SessionResponse {
  session_id: string;
}

export interface AnswerResponse {
  session_id: string;
  next_turn: number | null;
  confidence: number;
  partial_profile: InvestorProfileResponse;
}

export interface CompleteResponse {
  profile: InvestorProfileResponse;
  recommended_stocks: DiscoveredStock[];
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export function createDiscoverySession(): Promise<SessionResponse> {
  return apiFetch<SessionResponse>('/api/v1/discovery/session', {
    method: 'POST',
  });
}

export function submitAnswer(
  sessionId: string,
  turn: number,
  answer: string | string[],
): Promise<AnswerResponse> {
  return apiFetch<AnswerResponse>('/api/v1/discovery/answer', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, turn, answer }),
  });
}

export function completeDiscovery(sessionId: string): Promise<CompleteResponse> {
  return apiFetch<CompleteResponse>('/api/v1/discovery/complete', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId }),
  });
}
