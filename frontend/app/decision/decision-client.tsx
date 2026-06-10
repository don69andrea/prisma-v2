'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download } from 'lucide-react';

import Link from 'next/link';
import { listUniverses } from '@/lib/api/universes';
import { listDecisions, type SignalType, type DecisionSignal } from '@/lib/api/decisions';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const SIGNAL_CONFIG: Record<
  SignalType,
  { label: string; variant: 'success' | 'warning' | 'outline'; dot: string }
> = {
  BUY:   { label: 'BUY',   variant: 'success',  dot: 'bg-emerald-500' },
  HOLD:  { label: 'HOLD',  variant: 'warning',   dot: 'bg-amber-500'   },
  WATCH: { label: 'WATCH', variant: 'outline',   dot: 'bg-slate-400'   },
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 65 ? 'bg-emerald-500' : pct >= 40 ? 'bg-amber-500' : 'bg-slate-400';

  return (
    <div className="w-full" title={`${pct}%`}>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[10px] text-muted-foreground mt-0.5 text-right">{pct}%</p>
    </div>
  );
}

function SignalCard({ item }: { item: DecisionSignal }) {
  const cfg = SIGNAL_CONFIG[item.signal] ?? SIGNAL_CONFIG.WATCH;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link
            href={`/stocks/${item.ticker}`}
            className="font-semibold text-base leading-none hover:underline"
          >
            {item.ticker}
          </Link>
          <p className="text-xs text-muted-foreground mt-0.5">
            {new Date(item.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant={cfg.variant} className="flex items-center gap-1">
            <span className={cn('h-1.5 w-1.5 rounded-full', cfg.dot)} />
            {cfg.label}
          </Badge>
          {item.is_3a_eligible && (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0">3a</Badge>
          )}
        </div>
      </div>

      <ConfidenceBar value={item.confidence} />

      <div className="grid grid-cols-3 gap-1 text-[11px]">
        <div className="text-center">
          <p className="text-muted-foreground">Quant</p>
          <p className="font-medium">{item.quant_score.toFixed(1)}</p>
        </div>
        <div className="text-center">
          <p className="text-muted-foreground">ML</p>
          <p className="font-medium">{item.ml_score.toFixed(0)}</p>
        </div>
        <div className="text-center">
          <p className="text-muted-foreground">Macro</p>
          <p className="font-medium">{item.macro_score.toFixed(0)}</p>
        </div>
      </div>
    </div>
  );
}

function exportDecisionCsv(signals: DecisionSignal[]) {
  const rows = [
    ['Ticker', 'Signal', 'Confidence%', 'Quant-Score', 'ML-Score', 'Macro-Score', '3a-eligible', 'Datum'],
    ...signals.map((s) => [
      s.ticker,
      s.signal,
      Math.round(s.confidence * 100).toString(),
      s.quant_score.toFixed(1),
      s.ml_score.toFixed(0),
      s.macro_score.toFixed(0),
      s.is_3a_eligible ? 'ja' : 'nein',
      new Date(s.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' }),
    ]),
  ];
  const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `signale-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const LS_DECISION_KEY = 'prisma_decision_filters';

function loadStoredDecision() {
  try {
    const raw = localStorage.getItem(LS_DECISION_KEY);
    if (raw) return JSON.parse(raw) as {
      signalFilter: SignalType | '';
      eligibleOnly: boolean;
      minConfidence: number;
      sortKey: 'confidence' | 'quant_score' | 'ml_score' | 'ticker';
    };
  } catch {}
  return null;
}

export function DecisionClient() {
  const [selectedUniverse, setSelectedUniverse] = useState<string>('');
  const [signalFilter, setSignalFilter] = useState<SignalType | ''>(() => loadStoredDecision()?.signalFilter ?? '');
  const [eligibleOnly, setEligibleOnly] = useState(() => loadStoredDecision()?.eligibleOnly ?? false);
  const [sortKey, setSortKey] = useState<'confidence' | 'quant_score' | 'ml_score' | 'ticker'>(() => loadStoredDecision()?.sortKey ?? 'confidence');
  const [minConfidence, setMinConfidence] = useState(() => loadStoredDecision()?.minConfidence ?? 0);

  useEffect(() => {
    localStorage.setItem(LS_DECISION_KEY, JSON.stringify({ signalFilter, eligibleOnly, minConfidence, sortKey }));
  }, [signalFilter, eligibleOnly, minConfidence, sortKey]);

  const hasActiveFilters = signalFilter !== '' || eligibleOnly || minConfidence > 0;

  function resetFilters() {
    setSignalFilter('');
    setEligibleOnly(false);
    setMinConfidence(0);
  }

  const { data: universesData, isLoading: uLoading } = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
  });

  const universes = universesData?.items ?? [];

  const {
    data: decisionsData,
    isLoading: dLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['decisions', selectedUniverse, signalFilter, eligibleOnly],
    queryFn: () =>
      listDecisions(
        selectedUniverse,
        signalFilter || undefined,
        eligibleOnly || undefined,
      ),
    enabled: !!selectedUniverse,
  });

  const { data: decisionsAllData } = useQuery({
    queryKey: ['decisions-all', selectedUniverse, eligibleOnly],
    queryFn: () => listDecisions(selectedUniverse, undefined, eligibleOnly || undefined),
    enabled: !!selectedUniverse,
    staleTime: 5 * 60 * 1000,
  });

  const signals = decisionsData?.items ?? [];

  const filteredSignals = useMemo(() => {
    if (minConfidence === 0) return signals;
    return signals.filter((s) => s.confidence * 100 >= minConfidence);
  }, [signals, minConfidence]);

  const sortedSignals = useMemo(() => {
    return [...filteredSignals].sort((a, b) => {
      if (sortKey === 'ticker') return a.ticker.localeCompare(b.ticker);
      return b[sortKey] - a[sortKey];
    });
  }, [filteredSignals, sortKey]);

  const counts = useMemo(() => {
    const all = decisionsAllData?.items ?? [];
    return {
      BUY:   all.filter((s) => s.signal === 'BUY').length,
      HOLD:  all.filter((s) => s.signal === 'HOLD').length,
      WATCH: all.filter((s) => s.signal === 'WATCH').length,
    };
  }, [decisionsAllData]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground font-medium">Universum</label>
          <select
            className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring min-w-[180px]"
            value={selectedUniverse}
            onChange={(e) => setSelectedUniverse(e.target.value)}
            disabled={uLoading}
          >
            <option value="">— wählen —</option>
            {universes.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground font-medium">Signal</label>
          <select
            className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            value={signalFilter}
            onChange={(e) => setSignalFilter(e.target.value as SignalType | '')}
          >
            <option value="">Alle</option>
            <option value="BUY">BUY</option>
            <option value="HOLD">HOLD</option>
            <option value="WATCH">WATCH</option>
          </select>
        </div>

        <div className="flex items-center gap-2 self-end h-9">
          <input
            type="checkbox"
            id="eligible-only"
            checked={eligibleOnly}
            onChange={(e) => setEligibleOnly(e.target.checked)}
            className="h-4 w-4 rounded border"
          />
          <label htmlFor="eligible-only" className="text-sm select-none cursor-pointer">
            Nur 3a-eligible
          </label>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground font-medium">Min. Konfidenz (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            className="h-9 w-24 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            data-testid="decision-min-confidence-input"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-muted-foreground font-medium">Sortierung</label>
          <select
            className="h-9 rounded-md border bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as typeof sortKey)}
            data-testid="decision-sort-select"
          >
            <option value="confidence">Confidence ↓</option>
            <option value="quant_score">Quant-Score ↓</option>
            <option value="ml_score">ML-Score ↓</option>
            <option value="ticker">Ticker A–Z</option>
          </select>
        </div>
        {hasActiveFilters && (
          <button
            onClick={resetFilters}
            className="inline-flex items-center gap-1.5 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive hover:bg-destructive/10 transition-colors self-end"
            data-testid="decision-reset-filters-btn"
          >
            Alle Filter zurücksetzen
          </button>
        )}
      </div>

      {/* Signal-Zusammenfassung */}
      {selectedUniverse && decisionsAllData && (
        <div className="flex flex-wrap gap-2" data-testid="signal-summary">
          {(['BUY', 'HOLD', 'WATCH'] as const).map((sig) => {
            const cfg = SIGNAL_CONFIG[sig];
            const active = signalFilter === sig;
            return (
              <button
                key={sig}
                onClick={() => setSignalFilter(active ? '' : sig)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  active
                    ? 'border-transparent bg-foreground text-background'
                    : 'bg-background hover:bg-muted'
                }`}
                data-testid={`signal-chip-${sig}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
                {cfg.label}
                <span className="tabular-nums">{counts[sig]}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Content */}
      {!selectedUniverse && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Bitte ein Universum wählen.
        </p>
      )}

      {selectedUniverse && dLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-36 w-full rounded-lg" />
          ))}
        </div>
      )}

      {selectedUniverse && isError && (
        <div className="space-y-3">
          <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            Signale konnten nicht geladen werden.
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Erneut versuchen
          </Button>
        </div>
      )}

      {selectedUniverse && !dLoading && !isError && sortedSignals.length === 0 && (
        <p className="text-sm text-muted-foreground py-8 text-center">
          Keine Signale gefunden (Marktdaten werden berechnet oder Filter zu eng).
        </p>
      )}

      {sortedSignals.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground" data-testid="decision-signals-count">
              {sortedSignals.length !== signals.length
                ? `${sortedSignals.length} von ${signals.length} Signalen`
                : `${sortedSignals.length} Signal${sortedSignals.length !== 1 ? 'e' : ''} gefunden`}
            </p>
            <button
              onClick={() => exportDecisionCsv(sortedSignals)}
              className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium hover:bg-muted transition-colors"
              data-testid="decision-csv-export-btn"
            >
              <Download className="h-3 w-3" />
              CSV
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {sortedSignals.map((item) => (
              <SignalCard key={item.ticker} item={item} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
