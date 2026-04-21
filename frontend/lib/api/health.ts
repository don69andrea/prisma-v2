import { apiFetch } from './client';

export interface HealthResponse {
  status: string;
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}
