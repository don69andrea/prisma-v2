import { apiFetch } from './client';

export type TriggerType = 'PRICE_CHANGE' | 'SIGNAL_CHANGE';
export type ChannelType = 'EMAIL' | 'WEBHOOK';

export interface AlertCreateRequest {
  ticker: string;
  trigger_type: TriggerType;
  threshold: number;
  channel: ChannelType;
  target: string;
}

export interface Alert {
  id: string;
  ticker: string;
  trigger_type: TriggerType;
  threshold: number;
  channel: ChannelType;
  target: string;
  is_active: boolean;
  created_at: string;
  last_triggered_at: string | null;
  last_signal: string | null;
  baseline_price: number | null;
}

export interface AlertListResponse {
  alerts: Alert[];
  total: number;
}

export async function listAlerts(): Promise<AlertListResponse> {
  return apiFetch<AlertListResponse>('/api/v1/alerts');
}

export async function createAlert(req: AlertCreateRequest): Promise<Alert> {
  return apiFetch<Alert>('/api/v1/alerts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}

export async function deleteAlert(id: string): Promise<void> {
  await apiFetch<void>(`/api/v1/alerts/${id}`, { method: 'DELETE' });
}
