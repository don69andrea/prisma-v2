'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { TrendingUp, TrendingDown, Minus, Plus, Trash2 } from 'lucide-react';

import {
  computeRebalancingPlan,
  type RebalancingPlan,
  type RebalancingStep,
  type RebalancingAction,
} from '@/lib/api/portfolio';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const ACTION_CONFIG: Record<
  RebalancingAction,
  { label: string; icon: React.ReactNode; color: string }
> = {
  BUY:  { label: 'BUY',  icon: <TrendingUp className="h-3 w-3" />,   color: 'text-emerald-600 dark:text-emerald-400' },
  SELL: { label: 'SELL', icon: <TrendingDown className="h-3 w-3" />, color: 'text-red-600 dark:text-red-400'     },
  HOLD: { label: 'HOLD', icon: <Minus className="h-3 w-3" />,        color: 'text-muted-foreground'               },
};

interface PositionRow {
  ticker: string;
  current: string;
  target: string;
}

function chfFormat(v: number): string {
  return v.toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pctFormat(v: number): string {
  return (v * 100).toFixed(1) + '%';
}

function RebalancingStepRow({ step }: { step: RebalancingStep }) {
  const cfg = ACTION_CONFIG[step.action];
  return (
    <tr className="border-b last:border-0 hover:bg-muted/30 transition-colors">
      <td className="py-2 px-3 font-medium">{step.ticker}</td>
      <td className="py-2 px-3">
        <span className={cn('flex items-center gap-1 font-semibold text-sm', cfg.color)}>
          {cfg.icon} {cfg.label}
        </span>
      </td>
      <td className="py-2 px-3 text-right text-sm">{pctFormat(step.current_weight)}</td>
      <td className="py-2 px-3 text-right text-sm">{pctFormat(step.target_weight)}</td>
      <td className={cn('py-2 px-3 text-right text-sm font-medium', cfg.color)}>
        {step.delta_weight > 0 ? '+' : ''}{pctFormat(step.delta_weight)}
      </td>
      <td className="py-2 px-3 text-right text-sm">CHF {chfFormat(step.estimated_value_chf)}</td>
      <td className="py-2 px-3 text-right text-xs text-muted-foreground">
        CHF {chfFormat(step.transaction_cost_chf)}
      </td>
      {step.is_3a_eligible && (
        <td className="py-2 px-3">
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">3a</Badge>
        </td>
      )}
      {!step.is_3a_eligible && <td />}
    </tr>
  );
}

function PlanResult({ plan }: { plan: RebalancingPlan }) {
  const buys = plan.steps.filter((s) => s.action === 'BUY').length;
  const sells = plan.steps.filter((s) => s.action === 'SELL').length;
  const holds = plan.steps.filter((s) => s.action === 'HOLD').length;

  return (
    <div className="space-y-4" data-testid="rebalancing-result">
      <div className="flex flex-wrap gap-3">
        <div className="rounded-lg border bg-card px-4 py-2 text-sm">
          <p className="text-muted-foreground text-xs">Portfoliowert</p>
          <p className="font-semibold">CHF {chfFormat(plan.total_portfolio_value_chf)}</p>
        </div>
        <div className="rounded-lg border bg-card px-4 py-2 text-sm">
          <p className="text-muted-foreground text-xs">Gesamtkosten</p>
          <p className="font-semibold text-amber-600 dark:text-amber-400">
            CHF {chfFormat(plan.total_transaction_cost_chf)}
          </p>
        </div>
        <div className="rounded-lg border bg-card px-4 py-2 text-sm">
          <p className="text-muted-foreground text-xs">Trades</p>
          <p className="font-semibold">
            <span className="text-emerald-600 dark:text-emerald-400">{buys} BUY</span>
            {' · '}
            <span className="text-red-600 dark:text-red-400">{sells} SELL</span>
            {' · '}
            <span className="text-muted-foreground">{holds} HOLD</span>
          </p>
        </div>
        {plan.is_3a_account && (
          <div className="rounded-lg border bg-card px-4 py-2 text-sm">
            <p className="text-muted-foreground text-xs">Konto</p>
            <Badge variant="secondary">3a BVV2</Badge>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-xs text-muted-foreground">
              <th className="py-2 px-3 text-left">Ticker</th>
              <th className="py-2 px-3 text-left">Aktion</th>
              <th className="py-2 px-3 text-right">Ist</th>
              <th className="py-2 px-3 text-right">Soll</th>
              <th className="py-2 px-3 text-right">Delta</th>
              <th className="py-2 px-3 text-right">CHF-Wert</th>
              <th className="py-2 px-3 text-right">Kosten</th>
              <th className="py-2 px-3" />
            </tr>
          </thead>
          <tbody>
            {plan.steps.map((step) => (
              <RebalancingStepRow key={step.ticker} step={step} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted-foreground border-t pt-3">{plan.disclaimer}</p>
    </div>
  );
}

export function PortfolioClient() {
  const [totalValue, setTotalValue] = useState('100000');
  const [is3a, setIs3a] = useState(false);
  const [positions, setPositions] = useState<PositionRow[]>([
    { ticker: 'NESN', current: '30', target: '25' },
    { ticker: 'NOVN', current: '25', target: '30' },
    { ticker: 'ROG',  current: '20', target: '20' },
    { ticker: 'ABBN', current: '25', target: '25' },
  ]);
  const [error, setError] = useState('');

  const mutation = useMutation({
    mutationFn: computeRebalancingPlan,
    onError: () => setError('Rebalancing konnte nicht berechnet werden.'),
  });

  function addPosition() {
    setPositions((p) => [...p, { ticker: '', current: '0', target: '0' }]);
  }

  function removePosition(i: number) {
    setPositions((p) => p.filter((_, idx) => idx !== i));
  }

  function updatePosition(i: number, field: keyof PositionRow, value: string) {
    setPositions((p) => p.map((row, idx) => (idx === i ? { ...row, [field]: value } : row)));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    const total = parseFloat(totalValue);
    if (isNaN(total) || total <= 0) {
      setError('Gesamtwert muss grösser als 0 sein.');
      return;
    }
    const currentWeights: Record<string, number> = {};
    const targetWeights: Record<string, number> = {};
    for (const pos of positions) {
      if (!pos.ticker) continue;
      currentWeights[pos.ticker.toUpperCase()] = parseFloat(pos.current) / 100;
      targetWeights[pos.ticker.toUpperCase()] = parseFloat(pos.target) / 100;
    }
    if (Object.keys(currentWeights).length === 0) {
      setError('Mindestens eine Position erforderlich.');
      return;
    }
    mutation.mutate({ total_portfolio_value_chf: total, current_weights: currentWeights, target_weights: targetWeights, is_3a_account: is3a });
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="rounded-lg border bg-card p-4 space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="space-y-1">
            <label htmlFor="portfolio-total-value" className="text-xs text-muted-foreground">Portfoliowert (CHF)</label>
            <input
              id="portfolio-total-value"
              className="w-40 rounded border bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-primary"
              type="number"
              min="1"
              step="1000"
              value={totalValue}
              onChange={(e) => setTotalValue(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="rounded"
              checked={is3a}
              onChange={(e) => setIs3a(e.target.checked)}
            />
            Säule-3a-Konto (BVV2)
          </label>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground border-b">
                <th className="py-1 pr-3 text-left">Ticker</th>
                <th className="py-1 pr-3 text-right">Ist-Gewicht (%)</th>
                <th className="py-1 pr-3 text-right">Soll-Gewicht (%)</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {positions.map((pos, i) => (
                <tr key={i} className="border-b last:border-0">
                  <td className="py-1.5 pr-3">
                    <input
                      className="w-20 rounded border bg-background px-2 py-1 text-sm uppercase focus:outline-none focus:ring-1 focus:ring-primary"
                      value={pos.ticker}
                      placeholder="NESN"
                      onChange={(e) => updatePosition(i, 'ticker', e.target.value)}
                    />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input
                      className="w-20 rounded border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-primary"
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={pos.current}
                      onChange={(e) => updatePosition(i, 'current', e.target.value)}
                    />
                  </td>
                  <td className="py-1.5 pr-3">
                    <input
                      className="w-20 rounded border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-primary"
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={pos.target}
                      onChange={(e) => updatePosition(i, 'target', e.target.value)}
                    />
                  </td>
                  <td className="py-1.5">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      onClick={() => removePosition(i)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={addPosition}>
            <Plus className="h-3.5 w-3.5 mr-1" /> Position
          </Button>
          <Button type="submit" size="sm" disabled={mutation.isPending} data-testid="plan-submit-btn">
            {mutation.isPending ? 'Berechne…' : 'Plan berechnen'}
          </Button>
        </div>

        {error && <p className="text-xs text-destructive" data-testid="portfolio-error">{error}</p>}
      </form>

      {mutation.data && <PlanResult plan={mutation.data} />}
    </div>
  );
}
