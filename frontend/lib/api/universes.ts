import { apiFetch } from './client';

export interface UniverseRead {
  id: string;
  name: string;
  region: string;
  tickers: string[];
}

export interface UniverseListResponse {
  items: UniverseRead[];
  total: number;
}

export interface UniverseCreateRequest {
  name: string;
  region: string;
  tickers: string[];
}

/** Alias used in pages that pre-date the typed request object. */
export type Universe = UniverseRead;

export async function listUniverses(): Promise<UniverseListResponse> {
  return apiFetch<UniverseListResponse>('/api/v1/universes');
}

export async function getUniverse(id: string): Promise<UniverseRead> {
  return apiFetch<UniverseRead>(`/api/v1/universes/${id}`);
}

export async function createUniverse(
  nameOrRequest: string | UniverseCreateRequest,
  tickers?: string[],
  region = 'US',
): Promise<UniverseRead> {
  const body: UniverseCreateRequest =
    typeof nameOrRequest === 'string'
      ? { name: nameOrRequest, tickers: tickers ?? [], region }
      : nameOrRequest;
  return apiFetch<UniverseRead>('/api/v1/universes', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export interface UniverseSuggestion {
  name: string;
  region: string;
  tickers: string[];
  reasoning: string;
  available_tickers: string[];
}

export function suggestUniverse(description: string): Promise<UniverseSuggestion> {
  return apiFetch<UniverseSuggestion>('/api/v1/universes/suggest', {
    method: 'POST',
    body: JSON.stringify({ description }),
  });
}
