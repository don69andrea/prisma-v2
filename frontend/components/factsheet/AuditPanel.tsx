'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, RefreshCw } from 'lucide-react';

import { getAuditTrail, computeAndSaveAudit, type AuditRecord } from '@/lib/api/audit';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { InfoTooltip } from '@/components/ui/InfoTooltip';
import { cn } from '@/lib/utils';

const SIGNAL_VARIANT: Record<string, 'success' | 'warning' | 'destructive'> = {
  BUY:  'success',
  HOLD: 'warning',
  SELL: 'destructive',
};

function scoreInterpretation(score: number): { label: string; color: string } {
  if (score >= 80) return { label: 'Ausgezeichnet', color: 'text-emerald-600 dark:text-emerald-400' };
  if (score >= 65) return { label: 'Gut', color: 'text-green-600 dark:text-green-400' };
  if (score >= 50) return { label: 'Durchschnittlich', color: 'text-amber-600 dark:text-amber-400' };
  if (score >= 35) return { label: 'Schwach', color: 'text-orange-600 dark:text-orange-400' };
  return { label: 'Sehr schwach', color: 'text-red-600 dark:text-red-400' };
}

function ScoreBar({
  label,
  value,
  max = 100,
  tooltip,
  showInterpretation = false,
}: {
  label: string;
  value: number;
  max?: number;
  tooltip?: string;
  showInterpretation?: boolean;
}) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  const color =
    pct >= 65 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-slate-400';
  const interp = showInterpretation ? scoreInterpretation(value) : null;

  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="inline-flex items-center gap-1 text-muted-foreground">
          {label}
          {tooltip && <InfoTooltip text={tooltip} side="top" />}
        </span>
        <div className="flex items-center gap-1.5">
          {interp && (
            <span className={cn('text-[10px] font-medium', interp.color)}>{interp.label}</span>
          )}
          <span className="font-medium tabular-nums">{value.toFixed(1)}</span>
        </div>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function AuditCard({ record }: { record: AuditRecord }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={SIGNAL_VARIANT[record.signal] ?? 'outline'}>{record.signal}</Badge>
          {record.is_3a_eligible && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">3a</Badge>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(record.computed_at).toLocaleDateString('de-CH', { dateStyle: 'short' })}
        </span>
      </div>

      <div className="space-y-2">
        <ScoreBar
          label="Gesamt-Score"
          value={record.weighted_score}
          tooltip="Gesamtbewertung von 0–100 aus allen Dimensionen. ≥70 = BUY, 40–69 = HOLD, <40 = SELL."
          showInterpretation
        />
        <ScoreBar
          label="Quant (45%)"
          value={record.quant_score}
          tooltip="Quantitativer Score aus Value (KGV/KBV), Quality (Eigenkapitalrendite, Verschuldung) und Income (Dividendenrendite/-wachstum)."
          showInterpretation
        />
        <ScoreBar
          label="KI-Score (35%)"
          value={record.ml_score}
          tooltip="Prognose des Machine-Learning-Modells (LightGBM) basierend auf 23 historischen Merkmalen. Zeigt die Outperform-Wahrscheinlichkeit."
          showInterpretation
        />
        <ScoreBar
          label="Makro (20%)"
          value={record.macro_score}
          tooltip="Bewertet das makroökonomische Umfeld: SNB-Zinssatz, EUR/CHF-Kurs, globale PMI-Daten. Hoher Wert = günstiges Umfeld."
          showInterpretation
        />
      </div>

      {record.explanation_de && (
        <p className="text-xs text-muted-foreground leading-relaxed border-t pt-2">
          {record.explanation_de}
        </p>
      )}
    </div>
  );
}

interface Props {
  ticker: string;
}

export function AuditPanel({ ticker }: Props) {
  const queryClient = useQueryClient();
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['audit', ticker],
    queryFn: () => getAuditTrail(ticker),
  });

  const mutation = useMutation({
    mutationFn: () => computeAndSaveAudit(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['audit', ticker] }),
  });

  const records = data?.records ?? [];
  const displayed = showAll ? records : records.slice(0, 1);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-muted-foreground" />
            Entscheidungs-Audit
            <InfoTooltip
              text="Transparente Aufschlüsselung wie das BUY/HOLD/SELL-Signal berechnet wird. Zeigt Quant-Score (45%), KI-Score (35%) und Makro-Score (20%) mit Gewichtung."
              side="top"
            />
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            <RefreshCw className={cn('h-3 w-3 mr-1', mutation.isPending && 'animate-spin')} />
            Neu berechnen
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && <div className="h-24 rounded-lg bg-muted animate-pulse" />}
        {isError && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Kein Audit-Trail verfügbar. Signal neu berechnen.
          </p>
        )}
        {!isLoading && !isError && records.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-4">
            Noch kein Signal berechnet.
          </p>
        )}
        {displayed.map((r) => (
          <AuditCard key={r.id} record={r} />
        ))}
        {records.length > 1 && (
          <Button
            size="sm"
            variant="ghost"
            className="mt-2 text-xs w-full"
            onClick={() => setShowAll((v) => !v)}
          >
            {showAll ? 'Weniger anzeigen' : `${records.length - 1} weitere Einträge`}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
