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

export interface PortfolioAllocateRequest {
  run_id: string;
  top_n?: number;
  eligible_only?: boolean;
  method?: 'score_weighted' | 'risk_parity' | 'mean_variance';
}

export interface PortfolioPosition {
  ticker: string;
  weight: number;
  quant_score: number;
  is_3a_eligible: boolean;
  rationale_de: string;
}

export interface PortfolioAllocation {
  run_id: string;
  method: string;
  positions: PortfolioPosition[];
  overall_rationale_de: string;
  computed_at: string;
  eligible_only: boolean;
  total_positions: number;
}

export async function allocatePortfolio(req: PortfolioAllocateRequest): Promise<PortfolioAllocation> {
  return apiFetch<PortfolioAllocation>('/api/v1/portfolio/allocate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
}
