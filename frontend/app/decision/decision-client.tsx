'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Download, ChevronDown, ChevronUp } from 'lucide-react';

import Link from 'next/link';
import { listUniverses } from '@/lib/api/universes';
import { listDecisions, type SignalType, type DecisionSignal } from '@/lib/api/decisions';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { SignalBadge } from '@/components/ui/SignalBadge';
import { cn } from '@/lib/utils';

const FILTER_CHIP_CONFIG: Record<
  'BUY' | 'HOLD' | 'WATCH',
  { label: string; dot: string }
> = {
  BUY:   { label: 'BUY',   dot: 'bg-[#7ee787]' },
  HOLD:  { label: 'HOLD',  dot: 'bg-[#ffa657]' },
  WATCH: { label: 'WATCH', dot: 'bg-[#8b949e]'  },
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 65 ? 'bg-[#7ee787]' : pct >= 40 ? 'bg-[#ffa657]' : 'bg-[#8b949e]';

  return (
    <div className="w-full" title={`${pct}%`}>
      <div className="h-1.5 w-full rounded-full bg-[#21262d] overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[10px] text-[#8b949e] mt-0.5 text-right">{pct}%</p>
    </div>
  );
}

function AuditTrail({ item }: { item: DecisionSignal }) {
  const rows: { label: string; score: number; weight: number; contribution: number }[] = [
    { label: 'Quant-Score',   score: item.quant_score,  weight: 0.45, contribution: item.quant_score  * 0.45 },
    { label: 'ML-Prediction', score: item.ml_score,     weight: 0.35, contribution: item.ml_score     * 0.35 },
    { label: 'Makro-Kontext', score: item.macro_score,  weight: 0.20, contribution: item.macro_score  * 0.20 },
  ];
  const total = rows.reduce((s, r) => s + r.contribution, 0);
  const signalThreshold = item.signal === 'BUY' ? '≥ 65' : item.signal === 'HOLD' ? '40–64' : '< 40';

  return (
    <div className="mt-1 pt-2 border-t border-[#21262d] space-y-2 text-[11px]">
      <p className="text-[#8b949e] font-medium uppercase tracking-wide text-[10px]">
        Audit-Trail — Signal-Herleitung
      </p>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center gap-2">
          <span className="text-[#8b949e] w-28 shrink-0">{r.label}</span>
          <div className="flex-1 h-1.5 rounded-full bg-[#21262d] overflow-hidden">
            <div
              className="h-full rounded-full bg-[#58a6ff]/60"
              style={{ width: `${Math.min(r.score, 100)}%` }}
            />
          </div>
          <span className="text-[#e6edf3] w-6 text-right tabular-nums">{r.score.toFixed(0)}</span>
          <span className="text-[#8b949e]">×{r.weight}</span>
          <span className="text-[#bc8cff] w-7 text-right tabular-nums">{r.contribution.toFixed(1)}</span>
        </div>
      ))}
      <div className="flex justify-between pt-1 border-t border-[#21262d] font-semibold">
        <span className="text-[#8b949e]">Gesamt-Score</span>
        <span className="text-[#e6edf3]">
          {total.toFixed(1)} → {item.signal} ({signalThreshold})
        </span>
      </div>
    </div>
  );
}

function SignalCard({ item }: { item: DecisionSignal }) {
  const [auditOpen, setAuditOpen] = useState(false);

  return (
    <div className="glass-card p-4 space-y-3 hover:border-[#58a6ff]/30 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link
            href={`/stocks/${item.ticker}`}
            className="font-semibold text-base leading-none text-[#e6edf3] hover:text-[#58a6ff] transition-colors"
          >
            {item.ticker}
          </Link>
          <p className="text-xs text-[#8b949e] mt-0.5">
            {new Date(item.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <SignalBadge
            signal={item.signal as 'BUY' | 'HOLD' | 'WATCH'}
            confidence={item.confidence}
            animated={item.signal === 'BUY'}
          />
          {item.is_3a_eligible && (
            <span className="text-[10px] text-[#8b949e] border border-[#21262d] rounded px-1.5 py-0.5">
              3a
            </span>
          )}
        </div>
      </div>

      <ConfidenceBar value={item.confidence} />

      <div className="grid grid-cols-3 gap-1 text-[11px]">
        <div className="text-center">
          <p className="text-[#8b949e]">Quant</p>
          <p className="font-medium text-[#e6edf3]">{item.quant_score.toFixed(1)}</p>
        </div>
        <div className="text-center">
          <p className="text-[#8b949e]">ML</p>
          <p className="font-medium text-[#e6edf3]">{item.ml_score.toFixed(0)}</p>
        </div>
        <div className="text-center">
          <p className="text-[#8b949e]">Makro</p>
          <p className="font-medium text-[#e6edf3]">{item.macro_score.toFixed(0)}</p>
        </div>
      </div>

      <button
        onClick={() => setAuditOpen((o) => !o)}
        className="flex items-center gap-1 text-[11px] text-[#8b949e] hover:text-[#58a6ff] transition-colors w-full"
        data-testid="audit-trail-toggle"
        aria-expanded={auditOpen}
      >
        {auditOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        Audit-Trail {auditOpen ? 'schliessen' : 'anzeigen'}
      </button>

      {auditOpen && <AuditTrail item={item} />}
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
  const searchParams = useSearchParams();
  const [selectedUniverse, setSelectedUniverse] = useState<string>(
    () => searchParams.get('universe') ?? '',
  );
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
          <label className="text-xs text-[#8b949e] font-medium">Universum</label>
          <select
            className="h-9 rounded-md border border-[#21262d] bg-[#161b22] text-[#e6edf3] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[#58a6ff] min-w-[180px]"
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
          <label className="text-xs text-[#8b949e] font-medium">Signal</label>
          <select
            className="h-9 rounded-md border border-[#21262d] bg-[#161b22] text-[#e6edf3] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[#58a6ff]"
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
            className="h-4 w-4 rounded border border-[#21262d] accent-[#58a6ff]"
          />
          <label htmlFor="eligible-only" className="text-sm text-[#e6edf3] select-none cursor-pointer">
            Nur 3a-eligible
          </label>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#8b949e] font-medium">Min. Konfidenz (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            className="h-9 w-24 rounded-md border border-[#21262d] bg-[#161b22] text-[#e6edf3] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[#58a6ff]"
            data-testid="decision-min-confidence-input"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[#8b949e] font-medium">Sortierung</label>
          <select
            className="h-9 rounded-md border border-[#21262d] bg-[#161b22] text-[#e6edf3] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[#58a6ff]"
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
            className="inline-flex items-center gap-1.5 rounded-md border border-[#f85149]/40 px-3 py-2 text-sm text-[#f85149] hover:bg-[#f85149]/10 transition-colors self-end"
            data-testid="decision-reset-filters-btn"
          >
            Filter zurücksetzen
          </button>
        )}
      </div>

      {/* Signal-Zusammenfassung */}
      {selectedUniverse && decisionsAllData && (
        <div className="flex flex-wrap gap-2" data-testid="signal-summary">
          {(['BUY', 'HOLD', 'WATCH'] as const).map((sig) => {
            const cfg = FILTER_CHIP_CONFIG[sig];
            const active = signalFilter === sig;
            return (
              <button
                key={sig}
                onClick={() => setSignalFilter(active ? '' : sig)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                  active
                    ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[#58a6ff]'
                    : 'border-[#21262d] bg-[#161b22] text-[#8b949e] hover:border-[#58a6ff]/40'
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
        <p className="text-sm text-[#8b949e] py-8 text-center">
          Bitte ein Universum wählen.
        </p>
      )}

      {selectedUniverse && dLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-lg bg-[#161b22]" />
          ))}
        </div>
      )}

      {selectedUniverse && isError && (
        <div className="space-y-3">
          <div className="rounded-md border border-[#f85149]/50 bg-[#f85149]/10 p-4 text-sm text-[#f85149]">
            Signale konnten nicht geladen werden.
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Erneut versuchen
          </Button>
        </div>
      )}

      {selectedUniverse && !dLoading && !isError && sortedSignals.length === 0 && (
        <p className="text-sm text-[#8b949e] py-8 text-center">
          Keine Signale gefunden (Marktdaten werden berechnet oder Filter zu eng).
        </p>
      )}

      {sortedSignals.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-[#8b949e]" data-testid="decision-signals-count">
              {sortedSignals.length !== signals.length
                ? `${sortedSignals.length} von ${signals.length} Signalen`
                : `${sortedSignals.length} Signal${sortedSignals.length !== 1 ? 'e' : ''} gefunden`}
            </p>
            <button
              onClick={() => exportDecisionCsv(sortedSignals)}
              className="inline-flex items-center gap-1.5 rounded-md border border-[#21262d] px-2.5 py-1 text-xs font-medium text-[#8b949e] hover:bg-[#21262d] hover:text-[#e6edf3] transition-colors"
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
