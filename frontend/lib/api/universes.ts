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

export async function listUniverses(): Promise<UniverseListResponse> {
  return apiFetch<UniverseListResponse>('/api/v1/universes');
}

export async function getUniverse(id: string): Promise<UniverseRead> {
  return apiFetch<UniverseRead>(`/api/v1/universes/${id}`);
}

export async function createUniverse(data: UniverseCreateRequest): Promise<UniverseRead> {
  return apiFetch<UniverseRead>('/api/v1/universes', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
