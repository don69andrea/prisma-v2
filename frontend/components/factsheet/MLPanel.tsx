'use client';

import { useQuery } from '@tanstack/react-query';
import { BrainCircuit, Sparkles } from 'lucide-react';

import { getMLPrediction, type MLSignal } from '@/lib/api/ml';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { SHAPWaterfallChart } from './SHAPWaterfallChart';

const SIGNAL_CONFIG: Record<MLSignal, { variant: 'success' | 'warning' | 'outline'; label: string; glow: string }> = {
  OUTPERFORM:   { variant: 'success',  label: 'Outperform',   glow: 'shadow-[0_0_20px_rgba(0,255,136,0.3)]' },
  NEUTRAL:      { variant: 'warning',  label: 'Neutral',      glow: 'shadow-[0_0_20px_rgba(255,170,0,0.3)]' },
  UNDERPERFORM: { variant: 'outline',  label: 'Underperform', glow: 'shadow-[0_0_20px_rgba(255,68,102,0.3)]' },
};

function ConfidenceRing({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const r = 16;
  const circumference = 2 * Math.PI * r;
  const dash = (pct / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center w-10 h-10">
      <svg width="40" height="40" className="-rotate-90">
        <circle cx="20" cy="20" r={r} fill="none" stroke="#334155" strokeWidth="3" />
        <circle
          cx="20" cy="20" r={r} fill="none"
          stroke="#a855f7"
          strokeWidth="3"
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round"
          style={{ filter: 'drop-shadow(0 0 4px #a855f7)' }}
        />
      </svg>
      <span className="absolute text-[9px] font-bold text-purple-300">{pct}%</span>
    </div>
  );
}

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
    <Card className={cn('transition-shadow duration-500', cfg?.glow)}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-muted-foreground" />
          ML-Prediction
          {data?.shap_values && data.shap_values.length > 0 && (
            <Sparkles className="h-3 w-3 text-purple-400 ml-auto" />
          )}
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
              <div className="flex items-center gap-2">
                <ConfidenceRing confidence={data.confidence} />
                <span className="text-xs text-muted-foreground">
                  {new Date(data.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}
                </span>
              </div>
            </div>
            <div className="space-y-2">
              <ProbBar label="Outperform (Top 25%)" value={data.prob_top}     color="bg-emerald-500" />
              <ProbBar label="Neutral (Mid 50%)"    value={data.prob_mid}     color="bg-amber-500" />
              <ProbBar label="Underperform (Bot 25%)" value={data.prob_bottom} color="bg-slate-400" />
            </div>
            {data.shap_values && data.shap_values.length > 0 && (
              <SHAPWaterfallChart
                shapValues={data.shap_values}
                expectedValue={data.shap_expected_value}
                signal={data.signal}
              />
            )}
            <p className="text-[10px] text-muted-foreground border-t pt-2">
              ML-Modell ({data.model_type}) — keine Anlageberatung.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
