import { apiFetch } from './client';

export type RankingRunStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface RunResponse {
  id: string;
  status: RankingRunStatus;
  universe_id: string;
  created_at: string;
}

export interface RankingItem {
  ticker: string;
  total_rank: number | null;
  weighted_avg: number | null;
  is_sweet_spot: boolean;
  per_model_ranks: Record<string, number | null>;
}

export async function createRun(universeId: string): Promise<RunResponse> {
  return apiFetch<RunResponse>('/api/v1/runs', {
    method: 'POST',
    body: JSON.stringify({ universe_id: universeId }),
  });
}

export async function getRun(runId: string): Promise<RunResponse> {
  return apiFetch<RunResponse>(`/api/v1/runs/${runId}`);
}

export async function getRankings(runId: string): Promise<RankingItem[]> {
  return apiFetch<RankingItem[]>(`/api/v1/runs/${runId}/rankings`);
}

export async function listRuns(limit = 50, offset = 0): Promise<RunResponse[]> {
  return apiFetch<RunResponse[]>(`/api/v1/runs?limit=${limit}&offset=${offset}`);
}
