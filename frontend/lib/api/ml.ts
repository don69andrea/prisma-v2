import { apiFetch } from './client';

export type MLSignal = 'OUTPERFORM' | 'NEUTRAL' | 'UNDERPERFORM';

export interface MLPredictResponse {
  ticker: string;
  snapshot_date: string;
  predicted_class: number;
  signal: MLSignal;
  prob_bottom: number;
  prob_mid: number;
  prob_top: number;
  confidence: number;
  model_type: string;
  features: Record<string, number>;
}

export async function getMLPrediction(ticker: string): Promise<MLPredictResponse> {
  return apiFetch<MLPredictResponse>('/api/v1/ml/predict', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker }),
  });
}
