import { apiFetch, ApiError } from './client';

// Mirrors backend/domain/entities/research_memo.py:ContradictionItem
export interface ContradictionItem {
  model_a: string;
  model_b: string;
  description: string;
}

// Mirrors backend/interfaces/rest/routers/memos.py:MemoResponse
export interface Memo {
  id: string;
  stock_id: string;
  model_run_id: string;
  language: 'de' | 'en';
  one_liner: string;
  ranking_interpretation: string;
  sweet_spot: boolean;
  sweet_spot_explanation: string | null;
  contradictions: ContradictionItem[];
  key_strengths: string[];
  key_risks: string[];
  confidence: 'low' | 'medium' | 'high';
  model_version: string;
  created_at: string;
  is_error: boolean;
}

/** Returns null on 404 (no memo exists), throws on other errors. */
export async function getMemo(stockId: string, runId: string): Promise<Memo | null> {
  try {
    return await apiFetch<Memo>(`/api/v1/memos/${stockId}/${runId}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function generateMemo(
  stockId: string,
  modelRunId: string,
  language: 'de' | 'en' = 'de',
): Promise<Memo> {
  return apiFetch<Memo>('/api/v1/memos/generate', {
    method: 'POST',
    body: JSON.stringify({ stock_id: stockId, model_run_id: modelRunId, language }),
  });
}
