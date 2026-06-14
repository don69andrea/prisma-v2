'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, Download } from 'lucide-react';

import Link from 'next/link';
import { listUniverses } from '@/lib/api/universes';
import { listDecisions, liveDecisions, explainDecision, type DecisionSignal, type SignalType, type ExplainResponse } from '@/lib/api/decisions';
import { getMLPrediction } from '@/lib/api/ml';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { SignalBadge } from '@/components/ui/SignalBadge';
import { AuditTrail } from '@/components/ui/AuditTrail';
import { SignalBreakdown } from '@/components/ui/SignalBreakdown';
import { WeightSensitivity } from '@/components/ui/WeightSensitivity';
import { SHAPMiniBreakdown } from '@/components/ui/SHAPMiniBreakdown';
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


// ---------------------------------------------------------------------------
// Explain Modal
// ---------------------------------------------------------------------------

const METRIC_DEFS = [
  {
    key: 'quant' as const,
    label: 'Quant-Score',
    weight: '×0.45',
    color: '#58a6ff',
    definition: 'Fundamentale Stärke: Bewertung (KGV, EV/EBITDA), Dividendenrendite und Cashflow-Qualität — kalibriert an SMI-Bändern.',
    whyKey: 'quant_why' as const,
  },
  {
    key: 'ml' as const,
    label: 'ML-Prediction',
    weight: '×0.35',
    color: '#bc8cff',
    definition: 'LightGBM-Modell: OUTPERFORM=85 / NEUTRAL=50 / UNDERPERFORM=15 — basierend auf historischen Preis- und Fundamental-Features.',
    whyKey: 'ml_why' as const,
  },
  {
    key: 'macro' as const,
    label: 'Makro-Kontext',
    weight: '×0.20',
    color: '#7ee787',
    definition: 'Geldpolitisches Umfeld: SNB-Leitzins, CHF/EUR-Kurs, Inflation. Niedriger Zins = hoher Score (Aktien attraktiver als Anleihen).',
    whyKey: 'macro_why' as const,
  },
];

function ExplainMetricRow({
  def,
  score,
  explanation,
}: {
  def: typeof METRIC_DEFS[0];
  score: number;
  explanation?: string;
}) {
  const pct = Math.round(score);
  return (
    <div className="space-y-1.5 pb-3 border-b border-[#21262d] last:border-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold" style={{ color: def.color }}>{def.label}</span>
          <span className="text-[10px] text-[#8b949e]">{def.weight}</span>
        </div>
        <span className="text-xs font-bold text-[#e6edf3] tabular-nums">{pct}/100</span>
      </div>
      {/* Bar */}
      <div className="h-1.5 w-full rounded-full bg-[#21262d] overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: def.color, opacity: 0.8 }}
        />
      </div>
      {/* Definition */}
      <p className="text-[10px] text-[#8b949e] leading-relaxed">{def.definition}</p>
      {/* LLM Why */}
      {explanation && (
        <p className="text-[11px] text-[#e6edf3] leading-relaxed bg-[#0d1117]/60 rounded-md px-2.5 py-2">
          {explanation}
        </p>
      )}
    </div>
  );
}

function ExplainModal({ item, onClose }: { item: DecisionSignal; onClose: () => void }) {
  const [data, setData] = useState<ExplainResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    explainDecision({
      ticker: item.ticker,
      signal: item.signal,
      confidence: item.confidence,
      quant_score: item.quant_score,
      ml_score: item.ml_score,
      macro_score: item.macro_score,
      weighted_score: item.weighted_score,
    })
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [item]);

  const signalColor = item.signal === 'BUY' ? '#7ee787' : item.signal === 'HOLD' ? '#ffa657' : '#8b949e';

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl overflow-hidden"
        style={{ background: '#161b22', border: '1px solid #21262d', maxHeight: '88vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: '1px solid #21262d' }}
        >
          <div>
            <div className="flex items-center gap-2">
              {/* Lightbulb icon */}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={signalColor} strokeWidth="1.5" strokeLinecap="round">
                <path d="M12 2a7 7 0 0 1 7 7c0 3-1.7 5.4-4 6.7V17a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.3C6.7 14.4 5 12 5 9a7 7 0 0 1 7-7Z"/>
                <path d="M9 21h6M10 17v1M14 17v1"/>
              </svg>
              <span className="text-sm font-bold text-[#e6edf3]">{item.ticker} · PRISMA erklärt</span>
            </div>
            <p className="text-[11px] text-[#8b949e] mt-0.5 ml-5">
              Warum{' '}
              <span className="font-semibold" style={{ color: signalColor }}>{item.signal}</span>
              {' '}mit {Math.round(item.confidence * 100)}% Konfidenz?
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[#8b949e] hover:text-[#e6edf3] transition-colors rounded-md p-1"
            aria-label="Schliessen"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto px-5 py-4 space-y-4" style={{ maxHeight: 'calc(88vh - 72px)' }}>
          {loading && (
            <div className="flex flex-col items-center gap-3 py-8">
              <style>{`@keyframes explainDot{0%,80%,100%{opacity:.15}40%{opacity:1}}`}</style>
              {/* Lightbulb spinner */}
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={signalColor} strokeWidth="1.5" strokeLinecap="round"
                style={{ animation: 'prismaSpin 2s linear infinite' }}>
                <path d="M12 2a7 7 0 0 1 7 7c0 3-1.7 5.4-4 6.7V17a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.3C6.7 14.4 5 12 5 9a7 7 0 0 1 7-7Z"/>
                <path d="M9 21h6"/>
              </svg>
              <p className="text-sm text-[#8b949e]">
                PRISMA analysiert{' '}
                <span style={{ animation: 'explainDot 1.4s 0s infinite' }}>.</span>
                <span style={{ animation: 'explainDot 1.4s 0.2s infinite' }}>.</span>
                <span style={{ animation: 'explainDot 1.4s 0.4s infinite' }}>.</span>
              </p>
            </div>
          )}

          {error && (
            <p className="text-sm text-[#f85149] text-center py-6">
              Erklärung temporär nicht verfügbar.
            </p>
          )}

          {data && !loading && (
            <>
              {/* Overall */}
              <div
                className="rounded-xl px-4 py-3"
                style={{ background: `${signalColor}0d`, border: `1px solid ${signalColor}33` }}
              >
                <p className="text-[11px] font-semibold uppercase tracking-widest mb-1" style={{ color: signalColor }}>
                  Gesamtsignal
                </p>
                <p className="text-sm text-[#e6edf3] leading-relaxed">{data.overall}</p>
              </div>

              {/* Metrics with definitions + WHY */}
              <div className="space-y-3">
                {METRIC_DEFS.map((def) => (
                  <ExplainMetricRow
                    key={def.key}
                    def={def}
                    score={def.key === 'quant' ? item.quant_score : def.key === 'ml' ? item.ml_score : item.macro_score}
                    explanation={data[def.whyKey]}
                  />
                ))}
              </div>

              {/* Risk note */}
              <p className="text-[10px] text-[#8b949e] leading-relaxed border-t border-[#21262d] pt-3">
                {data.risk_note} · PRISMA Modell v1 · {new Date(item.snapshot_date).toLocaleDateString('de-CH')}
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function SignalCard({ item }: { item: DecisionSignal }) {
  const [auditOpen, setAuditOpen] = useState(false);
  const [explainOpen, setExplainOpen] = useState(false);

  const { data: mlData } = useQuery({
    queryKey: ['ml-predict', item.ticker],
    queryFn: () => getMLPrediction(item.ticker),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  const shapValues = mlData?.shap_values ?? [];
  const shapSignal = mlData?.signal ?? 'NEUTRAL';

  return (
    <>
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

        <SignalBreakdown
          quantScore={item.quant_score}
          mlScore={item.ml_score}
          macroScore={item.macro_score}
          finalScore={item.weighted_score}
          signal={item.signal as 'BUY' | 'HOLD' | 'WATCH'}
        />

        <WeightSensitivity
          quantScore={item.quant_score}
          mlScore={item.ml_score}
          macroScore={item.macro_score}
          standardScore={item.weighted_score}
          standardSignal={item.signal as 'BUY' | 'HOLD' | 'WATCH'}
        />

        {shapValues.length > 0 && (
          <SHAPMiniBreakdown shapValues={shapValues} signal={shapSignal} />
        )}
        {/* Action row */}
        <div className="flex items-center justify-between gap-2 pt-0.5">
          <button
            onClick={() => setAuditOpen((o) => !o)}
            className="flex items-center gap-1 text-[11px] text-[#8b949e] hover:text-[#58a6ff] transition-colors"
            data-testid="audit-trail-toggle"
            aria-expanded={auditOpen}
          >
            {auditOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Audit-Trail {auditOpen ? 'schliessen' : 'anzeigen'}
          </button>

          {/* Explain button */}
          <button
            onClick={() => setExplainOpen(true)}
            className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors hover:bg-[#58a6ff]/10"
            style={{ borderColor: 'rgba(88,166,255,0.3)', color: '#58a6ff' }}
            title="Wieso diese Entscheidung?"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 2a7 7 0 0 1 7 7c0 3-1.7 5.4-4 6.7V17a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.3C6.7 14.4 5 12 5 9a7 7 0 0 1 7-7Z"/>
              <path d="M9 21h6"/>
            </svg>
            Erklärung
          </button>
        </div>

        {auditOpen && (
          <AuditTrail
            quantScore={item.quant_score}
            mlScore={item.ml_score}
            macroScore={item.macro_score}
            signal={item.signal}
            snapshotDate={item.snapshot_date}
            className="mt-1 pt-2 border-t border-[#21262d]"
          />
        )}
      </div>

      {explainOpen && <ExplainModal item={item} onClose={() => setExplainOpen(false)} />}
    </>
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
    if (raw) {
      return JSON.parse(raw) as {
        signalFilter: SignalType | '';
        eligibleOnly: boolean;
        minConfidence: number;
        sortKey: 'confidence' | 'quant_score' | 'ml_score' | 'ticker';
      };
    }
  } catch {
    // ignore
  }
  return null;
}

export function DecisionClient() {
  const searchParams = useSearchParams();

  // tickers param = Discovery-Flow: direkte Ticker ohne universe_id
  const tickersParam = searchParams.get('tickers');
  const liveTickers = useMemo(
    () => (tickersParam ? tickersParam.split(',').filter(Boolean) : null),
    [tickersParam],
  );
  const isLiveMode = liveTickers !== null && liveTickers.length > 0;

  const [selectedUniverse, setSelectedUniverse] = useState<string>(
    () => searchParams.get('universe') ?? '',
  );
  const [signalFilter, setSignalFilter] = useState<SignalType | ''>(() => loadStoredDecision()?.signalFilter ?? '');
  const [eligibleOnly, setEligibleOnly] = useState(() => loadStoredDecision()?.eligibleOnly ?? false);
  const [sortKey, setSortKey] = useState<'confidence' | 'quant_score' | 'ml_score' | 'ticker'>(
    () => loadStoredDecision()?.sortKey ?? 'confidence',
  );
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
    enabled: !isLiveMode,
  });

  const universes = universesData?.items ?? [];

  useEffect(() => {
    if (!isLiveMode && !selectedUniverse && universes.length > 0) {
      setSelectedUniverse(universes[0].id);
    }
  }, [universes, selectedUniverse, isLiveMode]);

  // Live-Modus: EINMALIGER Request — alle Signale, Filterung client-seitig
  // (zwei parallele Requests auf denselben Ticker triggern yfinance-Rate-Limits)
  const {
    data: liveAllData,
    isLoading: liveLoading,
    isError: liveError,
    refetch: liveRefetch,
  } = useQuery({
    queryKey: ['decisions-live', liveTickers],
    queryFn: () => liveDecisions(liveTickers!),
    enabled: isLiveMode,
    staleTime: 5 * 60 * 1000,
  });

  // Universum-Modus: klassisch via universe_id
  const {
    data: decisionsData,
    isLoading: dLoading,
    isError: dError,
    refetch: dRefetch,
  } = useQuery({
    queryKey: ['decisions', selectedUniverse, signalFilter, eligibleOnly],
    queryFn: () => listDecisions(selectedUniverse, signalFilter || undefined, eligibleOnly || undefined),
    enabled: !isLiveMode && !!selectedUniverse,
  });

  const { data: decisionsAllData } = useQuery({
    queryKey: ['decisions-all', selectedUniverse, eligibleOnly],
    queryFn: () => listDecisions(selectedUniverse, undefined, eligibleOnly || undefined),
    enabled: !isLiveMode && !!selectedUniverse,
    staleTime: 5 * 60 * 1000,
  });

  const isLoading = isLiveMode ? liveLoading : dLoading;
  const isError   = isLiveMode ? liveError   : dError;
  const refetch   = isLiveMode ? liveRefetch  : dRefetch;
  const isReady   = isLiveMode ? true : !!selectedUniverse;

  // Im Live-Modus: alle Signale vom einmaligen Request, dann client-seitig filtern
  const allSignals = useMemo(
    () => (isLiveMode ? liveAllData?.items : decisionsAllData?.items) ?? [],
    [isLiveMode, liveAllData, decisionsAllData],
  );

  const signals = useMemo(() => {
    if (isLiveMode) {
      let filtered = allSignals;
      if (signalFilter) filtered = filtered.filter((s) => s.signal === signalFilter);
      if (eligibleOnly) filtered = filtered.filter((s) => s.is_3a_eligible);
      return filtered;
    }
    return (decisionsData?.items) ?? [];
  }, [isLiveMode, allSignals, signalFilter, eligibleOnly, decisionsData]);

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

  const counts = useMemo(() => ({
    BUY:   allSignals.filter((s) => s.signal === 'BUY').length,
    HOLD:  allSignals.filter((s) => s.signal === 'HOLD').length,
    WATCH: allSignals.filter((s) => s.signal === 'WATCH').length,
  }), [allSignals]);

  return (
    <div className="space-y-4">
      {/* Live-Mode Banner */}
      {isLiveMode && (
        <>
          <style>{`
            @keyframes liveDotBlue {
              0%, 100% { box-shadow: 0 0 4px 2px #58a6ff; }
              50%       { box-shadow: 0 0 9px 4px #58a6ff; }
            }
            @keyframes liveGlowBlue {
              0%, 100% { box-shadow: 0 0 4px 1px rgba(88,166,255,0.35); }
              50%       { box-shadow: 0 0 10px 3px rgba(88,166,255,0.7); }
            }
            @keyframes liveDotOrange {
              0%, 100% { box-shadow: 0 0 4px 2px #f59e0b; }
              50%       { box-shadow: 0 0 9px 4px #f59e0b; }
            }
            @keyframes liveGlowOrange {
              0%, 100% { box-shadow: 0 0 4px 1px rgba(245,158,11,0.35); }
              50%       { box-shadow: 0 0 10px 3px rgba(245,158,11,0.7); }
            }
          `}</style>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span
                className="inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1 text-[11px] font-bold tracking-widest"
                style={
                  isLoading
                    ? {
                        color: '#f59e0b',
                        borderColor: 'rgba(245,158,11,0.45)',
                        background: 'rgba(245,158,11,0.08)',
                        animation: 'liveGlowOrange 1.4s ease-in-out infinite',
                      }
                    : {
                        color: '#58a6ff',
                        borderColor: 'rgba(88,166,255,0.45)',
                        background: 'rgba(88,166,255,0.08)',
                        animation: 'liveGlowBlue 2s ease-in-out infinite',
                      }
                }
              >
                <span
                  className="h-2 w-2 rounded-full"
                  style={
                    isLoading
                      ? { background: '#f59e0b', animation: 'liveDotOrange 1s ease-in-out infinite' }
                      : { background: '#58a6ff', animation: 'liveDotBlue 1.4s ease-in-out infinite' }
                  }
                />
                {isLoading ? 'LADEN' : 'LIVE'}
              </span>
              <span className="text-[11px] text-[#8b949e]">
                {liveTickers!.length} Titel · {liveTickers!.join(', ')}
              </span>
            </div>
            <Link href="/discover" className="text-xs text-[#58a6ff] hover:underline whitespace-nowrap">
              Zurück →
            </Link>
          </div>
        </>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        {/* Universe-Dropdown nur im klassischen Modus */}
        {!isLiveMode && (
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
        )}

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
      {isReady && allSignals.length > 0 && (
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
      {!isLiveMode && !selectedUniverse && !uLoading && universes.length === 0 && (
        <div className="rounded-xl border border-[#21262d] p-8 text-center space-y-3">
          <p className="text-sm font-medium text-[#e6edf3]">Kein Universum vorhanden</p>
          <p className="text-xs text-[#8b949e]">
            Erstelle zuerst ein Universum unter{' '}
            <a href="/universes" className="text-[#58a6ff] hover:underline">Universen</a>.
          </p>
        </div>
      )}
      {!isLiveMode && !selectedUniverse && !uLoading && universes.length > 0 && (
        <p className="text-sm text-[#8b949e] py-8 text-center">
          Bitte ein Universum wählen.
        </p>
      )}

      {isReady && isLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: isLiveMode ? (liveTickers?.length ?? 6) : 8 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-lg bg-[#161b22]" />
          ))}
        </div>
      )}

      {isReady && isError && (
        <div className="space-y-3">
          <div className="rounded-md border border-[#f85149]/50 bg-[#f85149]/10 p-4 text-sm text-[#f85149]">
            Signale konnten nicht geladen werden.
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Erneut versuchen
          </Button>
        </div>
      )}

      {isReady && !isLoading && !isError && sortedSignals.length === 0 && (
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
