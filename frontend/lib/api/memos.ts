import { apiFetch } from './client';

export interface Memo {
  id: string;
  stock_id: string;
  model_run_id: string;
  content: string;
  language: string;
  created_at: string;
}

export function generateMemo(stockId: string, modelRunId: string): Promise<Memo> {
  return apiFetch<Memo>('/api/v1/memos/generate', {
    method: 'POST',
    body: JSON.stringify({ stock_id: stockId, model_run_id: modelRunId }),
  });
}
