import { apiFetch } from './client';

export type Anlegerprofil = 'privatperson' | 'vorsorge_3a' | 'vorsorge_2a' | 'institution';

export interface SteuerAnfrageRequest {
  ticker: string;
  anlegerprofil: Anlegerprofil;
  halteperiode_jahre: number;
}

export interface SteuerEinschaetzungResponse {
  ticker: string;
  anlegerprofil: string;
  halteperiode_jahre: number;
  steuerarten: string[];
  pflichten: string[];
  hinweise: string[];
  quellen: string[];
  disclaimer: string;
  generated_at: string;
  model_version: string;
}

export async function getSteuerEinschaetzung(
  req: SteuerAnfrageRequest,
): Promise<SteuerEinschaetzungResponse> {
  return apiFetch<SteuerEinschaetzungResponse>('/api/v1/steuer/einschaetzung', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
