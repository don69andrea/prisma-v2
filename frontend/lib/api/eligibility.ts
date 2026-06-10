import { apiFetch } from './client';

export interface EligibilityRead {
  ticker: string;
  eligible: boolean;
  reasons: string[];
  disclaimer: string;
}

export function getEligibility(ticker: string): Promise<EligibilityRead> {
  return apiFetch<EligibilityRead>(`/api/v1/stocks/${ticker}/3a-eligibility`);
}
