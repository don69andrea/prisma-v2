'use client';

import { useState } from 'react';
import { Loader2, BarChart3, Info } from 'lucide-react';

import { allocatePortfolio, type PortfolioAllocation } from '@/lib/api/portfolio';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Method = 'score_weighted' | 'risk_parity' | 'mean_variance';

interface MethodMeta {
  id: Method;
  label: string;
  subtitle: string;
  color: string;
  headerBg: string;
}

const METHODS: MethodMeta[] = [
  {
    id: 'score_weighted',
    label: 'Score-Weighted',
    subtitle: 'Gewichtung nach PRISMA-Score',
    color: 'text-blue-600 dark:text-blue-400',
    headerBg: 'bg-blue-50 dark:bg-blue-950/30',
  },
  {
    id: 'risk_parity',
    label: 'Risk-Parity',
    subtitle: 'Gleichgewichtet nach Volatilität',
    color: 'text-emerald-600 dark:text-emerald-400',
    headerBg: 'bg-emerald-50 dark:bg-emerald-950/30',
  },
  {
    id: 'mean_variance',
    label: 'Mean-Variance',
    subtitle: 'Markowitz-Optimierung (max. Sharpe)',
    color: 'text-violet-600 dark:text-violet-400',
    headerBg: 'bg-violet-50 dark:bg-violet-950/30',
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pctFmt(weight: number): string {
  return (weight * 100).toFixed(1) + '%';
}

function WeightBar({ weight }: { weight: number }) {
  const pct = Math.min(weight * 100, 100);
  return (
    <div className="w-full h-1 rounded-full bg-muted mt-0.5">
      <div
        className="h-1 rounded-full bg-current opacity-40"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single method column
// ---------------------------------------------------------------------------

interface MethodColumnProps {
  meta: MethodMeta;
  allocation: PortfolioAllocation | null;
  loading: boolean;
  error: string | null;
  allTickers: string[];
}

function MethodColumn({ meta, allocation, loading, error, allTickers }: MethodColumnProps) {
  const [showRationale, setShowRationale] = useState(false);

  const weightMap: Record<string, number> = {};
  const scoreMap: Record<string, number> = {};
  const eligibleMap: Record<string, boolean> = {};

  if (allocation) {
    for (const pos of allocation.positions) {
      weightMap[pos.ticker] = pos.weight;
      scoreMap[pos.ticker] = pos.quant_score;
      eligibleMap[pos.ticker] = pos.is_3a_eligible;
    }
  }

  return (
    <div className="flex flex-col min-w-0 flex-1">
      {/* Column header */}
      <div className={`rounded-t-lg px-3 py-2 border border-b-0 ${meta.headerBg}`}>
        <p className={`font-semibold text-sm ${meta.color}`}>{meta.label}</p>
        <p className="text-xs text-muted-foreground leading-tight mt-0.5">{meta.subtitle}</p>
      </div>

      {/* Loading / error states */}
      {loading && (
        <div className="flex items-center justify-center border border-t-0 rounded-b-lg py-8 text-muted-foreground text-sm gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Berechne…
        </div>
      )}

      {!loading && error && (
        <div className="border border-t-0 rounded-b-lg px-3 py-4 text-xs text-destructive">
          {error}
        </div>
      )}

      {/* Allocation table */}
      {!loading && !error && allocation && (
        <div className="border border-t-0 rounded-b-lg overflow-hidden">
          <table className="w-full text-xs">
            <tbody className="divide-y">
              {allTickers.map((ticker) => {
                const weight = weightMap[ticker];
                const score = scoreMap[ticker];
                const eligible = eligibleMap[ticker];
                const inMethod = weight !== undefined;

                return (
                  <tr
                    key={ticker}
                    className={`transition-colors ${inMethod ? 'hover:bg-muted/30' : 'opacity-40'}`}
                    data-testid={`comparison-row-${meta.id}-${ticker}`}
                  >
                    <td className="px-2 py-1.5 font-mono font-medium">
                      <div className="flex items-center gap-1">
                        {ticker}
                        {eligible && (
                          <Badge
                            variant="secondary"
                            className="text-[9px] px-1 py-0 h-3.5"
                          >
                            3a
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {inMethod ? (
                        <div className={`font-semibold ${meta.color}`}>
                          {pctFmt(weight)}
                          <WeightBar weight={weight} />
                        </div>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground hidden sm:table-cell">
                      {score !== undefined ? score.toFixed(2) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* LLM rationale toggle */}
          <div className="border-t px-2 py-1.5">
            <button
              type="button"
              onClick={() => setShowRationale((v) => !v)}
              className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              data-testid={`rationale-toggle-${meta.id}`}
            >
              <Info className="h-3 w-3" />
              {showRationale ? 'Begründung ausblenden' : 'Begründung anzeigen'}
            </button>
            {showRationale && (
              <p className="mt-1 text-[10px] text-muted-foreground leading-relaxed">
                {allocation.overall_rationale_de}
              </p>
            )}
          </div>

          <div className="px-2 pb-1.5 text-[9px] text-muted-foreground">
            {allocation.total_positions} Pos. · Keine Anlageberatung.
          </div>
        </div>
      )}

      {/* Empty / not loaded state */}
      {!loading && !error && !allocation && (
        <div className="border border-t-0 rounded-b-lg px-3 py-6 text-center text-xs text-muted-foreground">
          Noch nicht berechnet
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Unified ticker list (union of all allocated tickers, sorted by avg weight)
// ---------------------------------------------------------------------------

function buildTickerList(allocations: (PortfolioAllocation | null)[]): string[] {
  const weightSums: Record<string, number> = {};
  const counts: Record<string, number> = {};

  for (const alloc of allocations) {
    if (!alloc) continue;
    for (const pos of alloc.positions) {
      weightSums[pos.ticker] = (weightSums[pos.ticker] ?? 0) + pos.weight;
      counts[pos.ticker] = (counts[pos.ticker] ?? 0) + 1;
    }
  }

  return Object.keys(weightSums).sort((a, b) => {
    const avgA = weightSums[a] / counts[a];
    const avgB = weightSums[b] / counts[b];
    return avgB - avgA;
  });
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

interface AllocationComparisonPanelProps {
  runId: string;
}

interface MethodState {
  allocation: PortfolioAllocation | null;
  loading: boolean;
  error: string | null;
}

const INITIAL_STATE: MethodState = { allocation: null, loading: false, error: null };

export function AllocationComparisonPanel({ runId }: AllocationComparisonPanelProps) {
  const [states, setStates] = useState<Record<Method, MethodState>>({
    score_weighted: { ...INITIAL_STATE },
    risk_parity: { ...INITIAL_STATE },
    mean_variance: { ...INITIAL_STATE },
  });
  const [started, setStarted] = useState(false);

  function patchState(method: Method, patch: Partial<MethodState>) {
    setStates((prev) => ({
      ...prev,
      [method]: { ...prev[method], ...patch },
    }));
  }

  async function fetchMethod(method: Method) {
    patchState(method, { loading: true, error: null, allocation: null });
    try {
      const result = await allocatePortfolio({ run_id: runId, top_n: 10, method });
      patchState(method, { allocation: result, loading: false });
    } catch (err) {
      patchState(method, {
        loading: false,
        error: err instanceof Error ? err.message : 'Fehler bei der Berechnung',
      });
    }
  }

  async function handleCompare() {
    setStarted(true);
    // Fire all 3 in parallel
    await Promise.allSettled(METHODS.map((m) => fetchMethod(m.id)));
  }

  const allAllocations = METHODS.map((m) => states[m.id].allocation);
  const allTickers = buildTickerList(allAllocations);

  const anyLoading = METHODS.some((m) => states[m.id].loading);

  return (
    <Card data-testid="allocation-comparison-panel">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <BarChart3 className="h-4 w-4" />
          Methoden-Vergleich
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Alle 3 Allokations-Methoden auf einen Blick
        </p>
      </CardHeader>

      <CardContent className="space-y-4">
        {!started && (
          <Button
            variant="outline"
            onClick={handleCompare}
            disabled={anyLoading}
            data-testid="compare-methods-btn"
          >
            <BarChart3 className="mr-2 h-4 w-4" />
            Alle 3 Methoden vergleichen
          </Button>
        )}

        {started && (
          <>
            {/* Column header row with table sub-headers */}
            <div className="overflow-x-auto -mx-1 px-1">
              <div className="flex gap-3 min-w-[600px]">
                {METHODS.map((meta) => (
                  <MethodColumn
                    key={meta.id}
                    meta={meta}
                    allocation={states[meta.id].allocation}
                    loading={states[meta.id].loading}
                    error={states[meta.id].error}
                    allTickers={allTickers}
                  />
                ))}
              </div>
            </div>

            {/* Sub-header legend */}
            <div className="flex items-center gap-4 text-[10px] text-muted-foreground pt-1 border-t">
              <span>Spalten: Ticker · Gewicht · Quant-Score</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-2 text-[10px] ml-auto"
                onClick={handleCompare}
                disabled={anyLoading}
                data-testid="compare-refresh-btn"
              >
                {anyLoading ? (
                  <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : null}
                Aktualisieren
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
