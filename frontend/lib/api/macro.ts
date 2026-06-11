import { apiFetch } from './client';

export type MacroClimate = 'EXPANSIV' | 'NEUTRAL' | 'RESTRIKTIV';

export interface MacroContextResponse {
  leitzins: number;
  chf_eur: number;
  inflation_ch: number | null;
  pmi_ch: number | null;
  snapshot_date: string;
  climate: MacroClimate;
  narrative_de: string;
  narrative_en: string;
}

export interface MacroScoreResponse {
  ticker: string;
  score: number;
  leitzins: number;
  chf_eur: number;
  climate: MacroClimate;
  rag_context_used: boolean;
}

export async function getMacroContext(): Promise<MacroContextResponse> {
  return apiFetch<MacroContextResponse>('/api/v1/macro/context');
}

export async function getMacroScore(ticker: string): Promise<MacroScoreResponse> {
  return apiFetch<MacroScoreResponse>(`/api/v1/macro/score/${encodeURIComponent(ticker)}`);
}
