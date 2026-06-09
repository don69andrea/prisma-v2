'use client';

import { useQuery } from '@tanstack/react-query';
import { BrainCircuit } from 'lucide-react';

import { getMLPrediction, type MLSignal } from '@/lib/api/ml';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const SIGNAL_CONFIG: Record<MLSignal, { variant: 'success' | 'warning' | 'outline'; label: string }> = {
  OUTPERFORM:   { variant: 'success',  label: 'Outperform' },
  NEUTRAL:      { variant: 'warning',  label: 'Neutral' },
  UNDERPERFORM: { variant: 'outline',  label: 'Underperform' },
};

function ProbBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

interface Props {
  ticker: string;
}

export function MLPanel({ ticker }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['ml-predict', ticker],
    queryFn: () => getMLPrediction(ticker),
    retry: false,
  });

  const cfg = data ? SIGNAL_CONFIG[data.signal] ?? SIGNAL_CONFIG.NEUTRAL : null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-muted-foreground" />
          ML-Prediction
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <div className="h-20 rounded-lg bg-muted animate-pulse" />}
        {isError && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Kein ML-Modell verfügbar oder keine Marktdaten.
          </p>
        )}
        {data && cfg && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant={cfg.variant}>{cfg.label}</Badge>
              <span className="text-xs text-muted-foreground">
                {new Date(data.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })} ·{' '}
                Konfidenz {Math.round(data.confidence * 100)}%
              </span>
            </div>
            <div className="space-y-2">
              <ProbBar label="Outperform (Top 25%)" value={data.prob_top} color="bg-emerald-500" />
              <ProbBar label="Neutral (Mid 50%)"    value={data.prob_mid} color="bg-amber-500" />
              <ProbBar label="Underperform (Bot 25%)" value={data.prob_bottom} color="bg-slate-400" />
            </div>
            <p className="text-[10px] text-muted-foreground border-t pt-2">
              ML-Modell ({data.model_type}) — keine Anlageberatung.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
