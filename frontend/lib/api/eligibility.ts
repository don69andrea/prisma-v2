import { apiFetch } from './client';

export type EligibilityReason = 'exchange_not_recognized' | 'market_cap_too_low';

export interface EligibilityResponse {
  ticker: string;
  eligible: boolean;
  reasons: EligibilityReason[];
}

export async function getEligibility(ticker: string): Promise<EligibilityResponse> {
  return apiFetch<EligibilityResponse>(`/api/v1/stocks/${encodeURIComponent(ticker)}/3a-eligibility`);
}
