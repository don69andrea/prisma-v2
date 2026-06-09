import { apiFetch } from './client';

export type RebalancingAction = 'BUY' | 'SELL' | 'HOLD';

export interface RebalancingRequest {
  total_portfolio_value_chf: number;
  current_weights: Record<string, number>;
  target_weights: Record<string, number>;
  is_3a_account?: boolean;
  transaction_cost_rate?: number;
}

export interface RebalancingStep {
  ticker: string;
  action: RebalancingAction;
  current_weight: number;
  target_weight: number;
  delta_weight: number;
  estimated_value_chf: number;
  transaction_cost_chf: number;
  is_3a_eligible: boolean;
}

export interface RebalancingPlan {
  plan_id: string;
  steps: RebalancingStep[];
  total_portfolio_value_chf: number;
  total_transaction_cost_chf: number;
  is_3a_account: boolean;
  computed_at: string;
  disclaimer: string;
}

export async function computeRebalancingPlan(req: RebalancingRequest): Promise<RebalancingPlan> {
  return apiFetch<RebalancingPlan>('/api/v1/portfolio/rebalance', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
