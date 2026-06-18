'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { BarChart2, ChevronDown, ChevronUp, Download } from 'lucide-react';

import Link from 'next/link';
import { InfoPopover } from '@/components/InfoPopover';
import { listUniverses } from '@/lib/api/universes';
import { listDecisions, liveDecisions, explainDecision, type DecisionSignal, type SignalType, type ExplainResponse } from '@/lib/api/decisions';
import { getMLPrediction } from '@/lib/api/ml';
import { getMacroContext, type MacroContextResponse } from '@/lib/api/macro';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { SignalBadge } from '@/components/ui/SignalBadge';
import { AuditTrail } from '@/components/ui/AuditTrail';
import { SignalBreakdown } from '@/components/ui/SignalBreakdown';
import { WeightSensitivity } from '@/components/ui/WeightSensitivity';
import { SHAPMiniBreakdown } from '@/components/ui/SHAPMiniBreakdown';
import { cn } from '@/lib/utils';
import { usePrismaMode } from '@/hooks/usePrismaMode';

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

const SIGNAL_STYLES: Record<'BUY' | 'HOLD' | 'SELL', { bg: string; text: string; border: string }> = {
  BUY:  { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  HOLD: { bg: 'bg-amber-500/15',   text: 'text-amber-400',   border: 'border-amber-500/30'   },
  SELL: { bg: 'bg-red-500/15',     text: 'text-red-400',     border: 'border-red-500/30'     },
};

const FILTER_CHIP_CONFIG: Record<
  'BUY' | 'HOLD' | 'SELL',
  { label: string; dot: string }
> = {
  BUY:  { label: 'BUY',  dot: 'bg-[var(--prisma-green)]' },
  HOLD: { label: 'HOLD', dot: 'bg-[var(--prisma-orange)]' },
  SELL: { label: 'SELL', dot: 'bg-[var(--prisma-red)]'  },
};

// ---------------------------------------------------------------------------
// ConfidenceBar
// ---------------------------------------------------------------------------

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 65 ? 'bg-[var(--prisma-green)]' : pct >= 40 ? 'bg-[var(--prisma-orange)]' : 'bg-[var(--prisma-muted)]';

  return (
    <div className="w-full" title={`${pct}%`}>
      <div className="h-1.5 w-full rounded-full bg-[var(--prisma-border)] overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
      </div>
      <p className="text-[10px] text-[var(--prisma-muted)] mt-0.5 text-right">{pct}%</p>
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
    <div className="space-y-1.5 pb-3 border-b border-[var(--prisma-border)] last:border-0 last:pb-0">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold" style={{ color: def.color }}>{def.label}</span>
          <span className="text-[10px] text-[var(--prisma-muted)]">{def.weight}</span>
        </div>
        <span className="text-xs font-bold text-[var(--prisma-text)] tabular-nums">{pct}/100</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--prisma-border)] overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, background: def.color, opacity: 0.8 }}
        />
      </div>
      <p className="text-[10px] text-[var(--prisma-muted)] leading-relaxed">{def.definition}</p>
      {explanation && (
        <p className="text-[11px] text-[var(--prisma-text)] leading-relaxed bg-[var(--prisma-bg)]/60 rounded-md px-2.5 py-2">
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
  const [auditOpen, setAuditOpen] = useState(false);

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

  const signalColor = item.signal === 'BUY' ? '#7ee787' : item.signal === 'HOLD' ? '#ffa657' : '#f85149';

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div
        className="w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl overflow-hidden"
        style={{ background: 'var(--prisma-surface)', border: '1px solid var(--prisma-border)', maxHeight: '88vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: '1px solid var(--prisma-border)' }}
        >
          <div>
            <div className="flex items-center gap-2">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={signalColor} strokeWidth="1.5" strokeLinecap="round">
                <path d="M12 2a7 7 0 0 1 7 7c0 3-1.7 5.4-4 6.7V17a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.3C6.7 14.4 5 12 5 9a7 7 0 0 1 7-7Z"/>
                <path d="M9 21h6M10 17v1M14 17v1"/>
              </svg>
              <span className="text-sm font-bold text-[var(--prisma-text)]">{item.ticker} · PRISMA erklärt</span>
            </div>
            <p className="text-[11px] text-[var(--prisma-muted)] mt-0.5 ml-5">
              Warum{' '}
              <span className="font-semibold" style={{ color: signalColor }}>{item.signal}</span>
              {' '}mit {Math.round(item.confidence * 100)}% Konfidenz?
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[var(--prisma-muted)] hover:text-[var(--prisma-text)] transition-colors rounded-md p-1"
            aria-label="Schliessen"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div className="overflow-y-auto px-5 py-4 space-y-4" style={{ maxHeight: 'calc(88vh - 72px)' }}>
          {loading && (
            <div className="flex flex-col items-center gap-3 py-8">
              <style>{`@keyframes explainDot{0%,80%,100%{opacity:.15}40%{opacity:1}}`}</style>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke={signalColor} strokeWidth="1.5" strokeLinecap="round"
                style={{ animation: 'prismaSpin 2s linear infinite' }}>
                <path d="M12 2a7 7 0 0 1 7 7c0 3-1.7 5.4-4 6.7V17a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-1.3C6.7 14.4 5 12 5 9a7 7 0 0 1 7-7Z"/>
                <path d="M9 21h6"/>
              </svg>
              <p className="text-sm text-[var(--prisma-muted)]">
                PRISMA analysiert{' '}
                <span style={{ animation: 'explainDot 1.4s 0s infinite' }}>.</span>
                <span style={{ animation: 'explainDot 1.4s 0.2s infinite' }}>.</span>
                <span style={{ animation: 'explainDot 1.4s 0.4s infinite' }}>.</span>
              </p>
            </div>
          )}

          {error && (
            <p className="text-sm text-[var(--prisma-red)] text-center py-6">
              Erklärung temporär nicht verfügbar.
            </p>
          )}

          {data && !loading && (
            <>
              <div
                className="rounded-xl px-4 py-3"
                style={{ background: `${signalColor}0d`, border: `1px solid ${signalColor}33` }}
              >
                <p className="text-[11px] font-semibold uppercase tracking-widest mb-1" style={{ color: signalColor }}>
                  Gesamtsignal
                </p>
                <p className="text-sm text-[var(--prisma-text)] leading-relaxed">{data.overall}</p>
              </div>

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

              <p className="text-[10px] text-[var(--prisma-muted)] leading-relaxed border-t border-[var(--prisma-border)] pt-3">
                {data.risk_note} · PRISMA Modell v1 · {new Date(item.snapshot_date).toLocaleDateString('de-CH')}
              </p>
            </>
          )}
        </div>
      </div>

      <button
        onClick={() => setAuditOpen((o) => !o)}
        className="flex items-center gap-1 text-[11px] text-[var(--prisma-muted)] hover:text-[var(--prisma-blue)] transition-colors w-full"
        data-testid="audit-trail-toggle"
        aria-expanded={auditOpen}
      >
        {auditOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        Audit-Trail {auditOpen ? 'schliessen' : 'anzeigen'}
      </button>

      {auditOpen && (
        <AuditTrail
          quantScore={item.quant_score}
          mlScore={item.ml_score}
          macroScore={item.macro_score}
          signal={item.signal}
          snapshotDate={item.snapshot_date}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode: SignalCard (full detail card, existing behaviour)
// ---------------------------------------------------------------------------

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
              className="font-semibold text-base leading-none text-[var(--prisma-text)] hover:text-[var(--prisma-blue)] transition-colors"
            >
              {item.ticker}
            </Link>
            <p className="text-xs text-[var(--prisma-muted)] mt-0.5">
              {new Date(item.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <SignalBadge
              signal={item.signal as 'BUY' | 'HOLD' | 'SELL'}
              confidence={item.confidence}
              animated={item.signal === 'BUY'}
            />
            {item.is_3a_eligible && (
              <span className="text-[10px] text-[var(--prisma-muted)] border border-[var(--prisma-border)] rounded px-1.5 py-0.5">
                3a
              </span>
            )}
          </div>
        </div>

        {item.signal_reason && (
          <p className="text-xs text-muted-foreground mt-1">{item.signal_reason}</p>
        )}

        <div>
          <div className="flex items-center gap-1 mb-0.5">
            <span className="text-[10px] text-[var(--prisma-muted)] font-medium uppercase tracking-wide">Konfidenz</span>
            <InfoPopover ariaLabel="Was bedeutet Konfidenz?">
              <p>Konfidenz gibt an wie sicher das Modell bei dieser Empfehlung ist. &gt;80% = sehr sicher, 60–80% = sicher, &lt;60% = unsicher.</p>
            </InfoPopover>
          </div>
          <ConfidenceBar value={item.confidence} />
        </div>

        <div>
          <div className="flex items-center gap-1 mb-0.5">
            <span className="text-[10px] text-[var(--prisma-muted)] font-medium uppercase tracking-wide">PRISMA Score</span>
            <InfoPopover ariaLabel="Was ist der PRISMA Score?">
              <p>Der PRISMA-Score kombiniert technische Analyse (45%), KI-Prognose (35%) und Makroökonomie (20%) auf einer Skala von 0–100.</p>
            </InfoPopover>
          </div>
          <SignalBreakdown
            quantScore={item.quant_score}
            mlScore={item.ml_score}
            macroScore={item.macro_score}
            finalScore={item.weighted_score}
            signal={item.signal as 'BUY' | 'HOLD' | 'SELL'}
          />
        </div>

        <WeightSensitivity
          quantScore={item.quant_score}
          mlScore={item.ml_score}
          macroScore={item.macro_score}
          standardScore={item.weighted_score}
          standardSignal={item.signal as 'BUY' | 'HOLD' | 'SELL'}
        />

        {shapValues.length > 0 && (
          <div>
            <div className="flex items-center gap-1 mb-0.5">
              <span className="text-[10px] text-[var(--prisma-muted)] font-medium uppercase tracking-wide">SHAP</span>
              <InfoPopover ariaLabel="Was ist SHAP?">
                <p>SHAP erklärt welche Faktoren den Score am stärksten beeinflusst haben. Positive Werte = positiver Einfluss auf das Signal.</p>
              </InfoPopover>
            </div>
            <SHAPMiniBreakdown shapValues={shapValues} signal={shapSignal} />
          </div>
        )}

        <div className="flex items-center justify-between gap-2 pt-0.5">
          <button
            onClick={() => setAuditOpen((o) => !o)}
            className="flex items-center gap-1 text-[11px] text-[var(--prisma-muted)] hover:text-[var(--prisma-blue)] transition-colors"
            data-testid="audit-trail-toggle"
            aria-expanded={auditOpen}
          >
            {auditOpen ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            Audit-Trail {auditOpen ? 'schliessen' : 'anzeigen'}
          </button>

          <button
            onClick={() => setExplainOpen(true)}
            className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors hover:bg-[var(--prisma-blue)]/10"
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
            className="mt-1 pt-2 border-t border-[var(--prisma-border)]"
          />
        )}
      </div>

      {explainOpen && <ExplainModal item={item} onClose={() => setExplainOpen(false)} />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Simple Mode: HeroCard
// ---------------------------------------------------------------------------

function HeroCard({ item, signal }: { item: DecisionSignal | undefined; signal: 'BUY' | 'HOLD' | 'SELL' }) {
  const styles = SIGNAL_STYLES[signal];

  if (!item) {
    return (
      <div className={`rounded-xl border p-5 flex flex-col gap-3 ${styles.border} ${styles.bg} opacity-40`}>
        <div className="flex items-center justify-between">
          <span className={`text-sm font-bold uppercase px-2 py-1 rounded-lg ${styles.bg} ${styles.text}`}>{signal}</span>
          <span className="text-2xl font-bold text-muted-foreground">—</span>
        </div>
        <div className="font-bold text-muted-foreground text-lg">Kein Signal</div>
        <p className="text-sm text-muted-foreground italic leading-relaxed">Kein {signal}-Signal vorhanden.</p>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border p-5 flex flex-col gap-3 ${styles.border} ${styles.bg}`}>
      <div className="flex items-center justify-between">
        <span className={`text-sm font-bold uppercase px-2 py-1 rounded-lg ${styles.bg} ${styles.text}`}>{signal}</span>
        <span className="text-2xl font-bold text-foreground">{Math.round(item.weighted_score)}</span>
      </div>
      <div className="font-bold text-foreground text-lg">{item.ticker}</div>
      <p className="text-sm text-muted-foreground italic leading-relaxed">&ldquo;{item.signal_reason ?? 'Kein Kommentar verfügbar.'}&rdquo;</p>
      <Link href={`/stocks/${item.ticker}`} className="text-xs text-blue-400 hover:text-blue-300">Details ansehen →</Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Simple Mode: AllSignalsTable (expandable)
// ---------------------------------------------------------------------------

function AllSignalsTable({ signals }: { signals: DecisionSignal[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-sm text-[var(--prisma-muted)] hover:text-[var(--prisma-text)] transition-colors"
      >
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        {open ? 'Signale ausblenden' : `Alle ${signals.length} Signale anzeigen`}
      </button>

      {open && (
        <div className="mt-3 overflow-x-auto rounded-xl border border-[var(--prisma-border)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--prisma-border)] bg-[var(--prisma-surface)]">
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Name</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Signal</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Score</th>
                <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Begründung</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((item) => {
                const sig = item.signal as 'BUY' | 'HOLD' | 'SELL';
                const styles = SIGNAL_STYLES[sig] ?? SIGNAL_STYLES['HOLD'];
                return (
                  <tr key={item.ticker} className="border-b border-[var(--prisma-border)] last:border-0 hover:bg-[var(--prisma-surface)]/50 transition-colors">
                    <td className="px-4 py-3 font-medium text-[var(--prisma-text)]">
                      <Link href={`/stocks/${item.ticker}`} className="hover:text-[var(--prisma-blue)] transition-colors">
                        {item.ticker}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-block text-xs font-bold uppercase px-2 py-0.5 rounded-md ${styles.bg} ${styles.text}`}>
                        {sig}
                      </span>
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[var(--prisma-text)]">{Math.round(item.weighted_score)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground max-w-xs">{item.signal_reason ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode: full table view
// ---------------------------------------------------------------------------

function ProTable({ signals }: { signals: DecisionSignal[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--prisma-border)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--prisma-border)] bg-[var(--prisma-surface)]">
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Ticker</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Signal</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Score</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Faktor</th>
            <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-[var(--prisma-muted)]">Begründung</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((item) => {
            const sig = item.signal as 'BUY' | 'HOLD' | 'SELL';
            const styles = SIGNAL_STYLES[sig] ?? SIGNAL_STYLES['HOLD'];
            return (
              <tr key={item.ticker} className="border-b border-[var(--prisma-border)] last:border-0 hover:bg-[var(--prisma-surface)]/50 transition-colors">
                <td className="px-4 py-3 font-semibold text-[var(--prisma-text)]">
                  <Link href={`/stocks/${item.ticker}`} className="hover:text-[var(--prisma-blue)] transition-colors">
                    {item.ticker}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-block text-xs font-bold uppercase px-2 py-0.5 rounded-md ${styles.bg} ${styles.text}`}>
                    {sig}
                  </span>
                </td>
                <td className="px-4 py-3 tabular-nums text-[var(--prisma-text)]">{Math.round(item.weighted_score)}</td>
                <td className="px-4 py-3 text-xs text-[var(--prisma-muted)]">—</td>
                <td className="px-4 py-3 text-xs text-muted-foreground max-w-xs">{item.signal_reason ?? '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode: signal breakdown panel
// ---------------------------------------------------------------------------

function ProSignalBreakdownPanel({ counts }: { counts: { BUY: number; HOLD: number; SELL: number } }) {
  const total = counts.BUY + counts.HOLD + counts.SELL || 1;
  const bars: { sig: 'BUY' | 'HOLD' | 'SELL'; label: string; color: string }[] = [
    { sig: 'BUY',  label: 'BUY',  color: 'bg-emerald-500' },
    { sig: 'HOLD', label: 'HOLD', color: 'bg-amber-500'   },
    { sig: 'SELL', label: 'SELL', color: 'bg-red-500'     },
  ];

  return (
    <div className="rounded-xl border border-[var(--prisma-border)] bg-[var(--prisma-surface)] p-5 space-y-4">
      <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--prisma-muted)]">Signal-Breakdown</h3>
      <div className="space-y-3">
        {bars.map(({ sig, label, color }) => {
          const pct = Math.round((counts[sig] / total) * 100);
          return (
            <div key={sig} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-[var(--prisma-text)]">{label}</span>
                <span className="tabular-nums text-[var(--prisma-muted)]">{counts[sig]} ({pct}%)</span>
              </div>
              <div className="h-2 w-full rounded-full bg-[var(--prisma-border)] overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode: makro context panel
// ---------------------------------------------------------------------------

function ProMakroPanel() {
  const { data, isLoading } = useQuery<MacroContextResponse>({
    queryKey: ['macro-context'],
    queryFn: getMacroContext,
    staleTime: 30 * 60 * 1000,
    retry: 1,
  });

  const climateColor: Record<string, string> = {
    EXPANSIV:   'text-emerald-400',
    NEUTRAL:    'text-amber-400',
    RESTRIKTIV: 'text-red-400',
  };

  return (
    <div className="rounded-xl border border-[var(--prisma-border)] bg-[var(--prisma-surface)] p-5 space-y-3">
      <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--prisma-muted)]">Makro-Kontext</h3>
      {isLoading ? (
        <div className="space-y-2">
          {[1,2,3,4].map(i => <div key={i} className="h-4 rounded bg-[var(--prisma-border)] animate-pulse" />)}
        </div>
      ) : data ? (
        <>
          <ul className="space-y-2 text-sm text-[var(--prisma-text)]">
            <li className="flex items-start gap-2">
              <span className="text-[var(--prisma-muted)] min-w-[110px] text-xs">SNB Leitzins</span>
              <span className="font-medium">{data.leitzins.toFixed(2)}%</span>
            </li>
            <li className="flex items-start gap-2">
              <span className="text-[var(--prisma-muted)] min-w-[110px] text-xs">CHF/EUR</span>
              <span className="font-medium">{data.chf_eur.toFixed(3)}</span>
            </li>
            {data.inflation_ch != null && (
              <li className="flex items-start gap-2">
                <span className="text-[var(--prisma-muted)] min-w-[110px] text-xs">Inflation CH</span>
                <span className="font-medium">{data.inflation_ch.toFixed(1)}%</span>
              </li>
            )}
            <li className="flex items-start gap-2">
              <span className="text-[var(--prisma-muted)] min-w-[110px] text-xs">Klima</span>
              <span className={`font-medium ${climateColor[data.climate] ?? ''}`}>{data.climate}</span>
            </li>
          </ul>
          <p className="text-[10px] text-[var(--prisma-muted)] leading-relaxed pt-1">
            {data.narrative_de}
          </p>
          <p className="text-[10px] text-[var(--prisma-muted)]">
            Stand: {new Date(data.snapshot_date).toLocaleDateString('de-CH')}
          </p>
        </>
      ) : (
        <p className="text-xs text-[var(--prisma-muted)]">Makro-Daten nicht verfügbar.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CSV export (unchanged)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Persisted filter state
// ---------------------------------------------------------------------------

const LS_DECISION_KEY = 'prisma_decision_filters';

function loadStoredDecision() {
  try {
    const raw = localStorage.getItem(LS_DECISION_KEY);
    if (raw) {
      return JSON.parse(raw) as {
        signalFilter: SignalType | '';
        eligibleOnly: boolean;
        minConfidence: number;
        sortKey: 'weighted_score' | 'confidence' | 'quant_score' | 'ml_score' | 'ticker';
      };
    }
  } catch {
    // ignore
  }
  return null;
}

// ---------------------------------------------------------------------------
// DecisionClient — main export
// ---------------------------------------------------------------------------

export function DecisionClient() {
  const searchParams = useSearchParams();
  const { mode, toggle, isSimple, isPro } = usePrismaMode();

  // tickers param = Discovery-Flow
  const tickersParam = searchParams.get('tickers');
  const liveTickers = useMemo(
    () => (tickersParam ? tickersParam.split(',').filter(Boolean) : null),
    [tickersParam],
  );
  const isLiveMode = liveTickers !== null && liveTickers.length > 0;

  const [selectedUniverse, setSelectedUniverse] = useState<string>(
    () => searchParams.get('universe') ?? '',
  );
  const [signalFilter, setSignalFilter] = useState<SignalType | ''>('');
  const [eligibleOnly, setEligibleOnly] = useState(false);
  const [sortKey, setSortKey] = useState<'weighted_score' | 'confidence' | 'quant_score' | 'ml_score' | 'ticker'>('weighted_score');
  const [minConfidence, setMinConfidence] = useState(0);

  useEffect(() => {
    const s = loadStoredDecision();
    if (!s) return;
    if (s.signalFilter !== undefined) setSignalFilter(s.signalFilter);
    if (typeof s.eligibleOnly === 'boolean') setEligibleOnly(s.eligibleOnly);
    if (s.sortKey) setSortKey(s.sortKey);
    if (typeof s.minConfidence === 'number') setMinConfidence(s.minConfidence);
  }, []);

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

  // Always sort allSignals by weighted_score desc for hero card selection
  const sortedAllSignals = useMemo(
    () => [...allSignals].sort((a, b) => b.weighted_score - a.weighted_score),
    [allSignals],
  );

  const counts = useMemo(() => ({
    BUY:  allSignals.filter((s) => s.signal === 'BUY').length,
    HOLD: allSignals.filter((s) => s.signal === 'HOLD').length,
    SELL: allSignals.filter((s) => s.signal === 'SELL').length,
  }), [allSignals]);

  // Hero cards: top-scoring BUY, HOLD, SELL
  const heroSignals = useMemo(() => ({
    BUY:  sortedAllSignals.find((s) => s.signal === 'BUY'),
    HOLD: sortedAllSignals.find((s) => s.signal === 'HOLD'),
    SELL: sortedAllSignals.find((s) => s.signal === 'SELL'),
  }), [sortedAllSignals]);

  // Last-updated time derived from the most recent snapshot_date in the dataset
  const lastUpdated = useMemo(() => {
    if (allSignals.length === 0) return null;
    const dates = allSignals.map((s) => s.snapshot_date).filter(Boolean);
    if (dates.length === 0) return null;
    const latest = dates.reduce((a, b) => (a > b ? a : b));
    return new Date(latest).toLocaleTimeString('de-CH', { hour: '2-digit', minute: '2-digit' });
  }, [allSignals]);

  // ---------------------------------------------------------------------------
  // Shared loading / error / empty states
  // ---------------------------------------------------------------------------

  const emptyStateJsx = (
    <>
      {!isLiveMode && !selectedUniverse && !uLoading && universes.length === 0 && (
        <div className="rounded-xl border border-[var(--prisma-border)] p-8 text-center space-y-3">
          <p className="text-sm font-medium text-[var(--prisma-text)]">Kein Universum vorhanden</p>
          <p className="text-xs text-[var(--prisma-muted)]">
            Erstelle zuerst ein Universum unter{' '}
            <a href="/universes" className="text-[var(--prisma-blue)] hover:underline">Universen</a>.
          </p>
        </div>
      )}
      {!isLiveMode && !selectedUniverse && !uLoading && universes.length > 0 && (
        <p className="text-sm text-[var(--prisma-muted)] py-8 text-center">Bitte ein Universum wählen.</p>
      )}
      {isReady && isLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-lg bg-[var(--prisma-surface)]" />
          ))}
        </div>
      )}
      {isReady && isError && (
        <div className="space-y-3">
          <div className="rounded-md border border-[var(--prisma-red)]/50 bg-[var(--prisma-red)]/10 p-4 text-sm text-[var(--prisma-red)]">
            Signale konnten nicht geladen werden.
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Erneut versuchen
          </Button>
        </div>
      )}
      {isReady && !isLoading && !isError && sortedSignals.length === 0 && allSignals.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
          <BarChart2 className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm font-medium text-foreground">Noch keine Signale vorhanden</p>
          <p className="text-xs text-muted-foreground max-w-xs">
            Starte einen Rankings-Run um BUY, HOLD und SELL Signale zu generieren
          </p>
          <Link href="/rankings" className="text-xs text-blue-400 hover:text-blue-300">
            Zum Ranking →
          </Link>
        </div>
      )}
    </>
  );

  // ---------------------------------------------------------------------------
  // Mode toggle button (shared)
  // ---------------------------------------------------------------------------

  const modeToggleJsx = (
    <button
      onClick={toggle}
      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--prisma-border)] px-3 py-1.5 text-xs font-medium text-[var(--prisma-muted)] hover:bg-[var(--prisma-border)] hover:text-[var(--prisma-text)] transition-colors"
    >
      {isSimple ? 'Pro-Modus' : 'Einfacher Modus'}
    </button>
  );

  // ---------------------------------------------------------------------------
  // SIMPLE MODE
  // ---------------------------------------------------------------------------

  if (isSimple) {
    return (
      <div className="space-y-6">
        {/* Header row */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-[var(--prisma-text)] tracking-tight">Signale heute.</h1>
            {lastUpdated && (
              <p className="text-sm text-[var(--prisma-muted)] mt-1">Letzte Aktualisierung: {lastUpdated}</p>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {/* Simple universe selector */}
            {!isLiveMode && universes.length > 0 && (
              <select
                className="h-8 rounded-md border border-[var(--prisma-border)] bg-[var(--prisma-surface)] text-[var(--prisma-text)] px-2 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--prisma-blue)]"
                value={selectedUniverse}
                onChange={(e) => setSelectedUniverse(e.target.value)}
                disabled={uLoading}
              >
                <option value="">— Universum —</option>
                {universes.map((u) => (
                  <option key={u.id} value={u.id}>{u.name}</option>
                ))}
              </select>
            )}
            {modeToggleJsx}
          </div>
        </div>

        {/* Live-mode banner */}
        {isLiveMode && (
          <div className="flex items-center gap-2 text-xs text-[var(--prisma-muted)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#58a6ff]" />
            {liveTickers!.length} Titel live: {liveTickers!.join(', ')}
            <Link href="/discover" className="ml-auto text-[var(--prisma-blue)] hover:underline">Zurück →</Link>
          </div>
        )}

        {emptyStateJsx}

        {/* Hero cards */}
        {isReady && !isLoading && !isError && allSignals.length > 0 && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <HeroCard item={heroSignals.BUY}  signal="BUY"  />
              <HeroCard item={heroSignals.HOLD} signal="HOLD" />
              <HeroCard item={heroSignals.SELL} signal="SELL" />
            </div>

            {/* Expandable full signal list */}
            <AllSignalsTable signals={sortedAllSignals} />
          </>
        )}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // PRO MODE
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-bold text-[var(--prisma-text)] tracking-tight">Decision Intelligence.</h1>
        {modeToggleJsx}
      </div>

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
              <span className="text-[11px] text-[var(--prisma-muted)]">
                {liveTickers!.length} Titel · {liveTickers!.join(', ')}
              </span>
            </div>
            <Link href="/discover" className="text-xs text-[var(--prisma-blue)] hover:underline whitespace-nowrap">
              Zurück →
            </Link>
          </div>
        </>
      )}

      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        {!isLiveMode && (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-[var(--prisma-muted)] font-medium">Universum</label>
            <select
              className="h-9 rounded-md border border-[var(--prisma-border)] bg-[var(--prisma-surface)] text-[var(--prisma-text)] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--prisma-blue)] min-w-[180px]"
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
          <label className="text-xs text-[var(--prisma-muted)] font-medium">Signal</label>
          <select
            className="h-9 rounded-md border border-[var(--prisma-border)] bg-[var(--prisma-surface)] text-[var(--prisma-text)] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--prisma-blue)]"
            value={signalFilter}
            onChange={(e) => setSignalFilter(e.target.value as SignalType | '')}
          >
            <option value="">Alle</option>
            <option value="BUY">BUY</option>
            <option value="HOLD">HOLD</option>
            <option value="SELL">SELL</option>
          </select>
        </div>


        <div className="flex items-center gap-2 self-end h-9">
          <input
            type="checkbox"
            id="eligible-only"
            checked={eligibleOnly}
            onChange={(e) => setEligibleOnly(e.target.checked)}
            className="h-4 w-4 rounded border border-[var(--prisma-border)] accent-[#58a6ff]"
          />
          <label htmlFor="eligible-only" className="text-sm text-[var(--prisma-text)] select-none cursor-pointer">
            Nur 3a-eligible
          </label>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[var(--prisma-muted)] font-medium">Min. Konfidenz (%)</label>
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            value={minConfidence}
            onChange={(e) => setMinConfidence(Number(e.target.value))}
            className="h-9 w-24 rounded-md border border-[var(--prisma-border)] bg-[var(--prisma-surface)] text-[var(--prisma-text)] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--prisma-blue)]"
            data-testid="decision-min-confidence-input"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs text-[var(--prisma-muted)] font-medium">Sortierung</label>
          <select
            className="h-9 rounded-md border border-[var(--prisma-border)] bg-[var(--prisma-surface)] text-[var(--prisma-text)] px-3 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--prisma-blue)]"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as typeof sortKey)}
            data-testid="decision-sort-select"
          >
            <option value="weighted_score">PRISMA Score</option>
            <option value="confidence">Confidence</option>
            <option value="quant_score">Quant-Score</option>
            <option value="ml_score">ML-Score</option>
            <option value="ticker">Ticker A–Z</option>
          </select>
        </div>

        {hasActiveFilters && (
          <button
            onClick={resetFilters}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#f85149]/40 px-3 py-2 text-sm text-[var(--prisma-red)] hover:bg-[var(--prisma-red)]/10 transition-colors self-end"
            data-testid="decision-reset-filters-btn"
          >
            Filter zurücksetzen
          </button>
        )}
      </div>

      {/* Signal-Zusammenfassung chips */}
      {isReady && allSignals.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="signal-summary">
          {(['BUY', 'HOLD', 'SELL'] as const).map((sig) => {
            const cfg = FILTER_CHIP_CONFIG[sig];
            const active = signalFilter === sig;
            const tooltips: Record<string, string> = {
              BUY: 'BUY bedeutet: Der PRISMA-Score ist >= 70 von 100. Das Modell empfiehlt den Kauf.',
              HOLD: 'HOLD bedeutet: PRISMA-Score 40-69. Beobachten, aber (noch) nicht handeln.',
              SELL: 'SELL bedeutet: PRISMA-Score < 40. Die Fundamentaldaten sind schwach. Verkauf empfohlen.',
            };
            return (
              <span key={sig} className="inline-flex items-center gap-0.5">
                <button
                  onClick={() => setSignalFilter(active ? '' : sig)}
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    active
                      ? 'border-[#58a6ff] bg-[#58a6ff]/10 text-[var(--prisma-blue)]'
                      : 'border-[var(--prisma-border)] bg-[var(--prisma-surface)] text-[var(--prisma-muted)] hover:border-[#58a6ff]/40'
                  }`}
                  data-testid={`signal-chip-${sig}`}
                >
                  <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
                  {cfg.label}
                  <span className="tabular-nums">{counts[sig]}</span>
                </button>
                <InfoPopover ariaLabel={`Was bedeutet ${sig}?`}>
                  <p>{tooltips[sig]}</p>
                </InfoPopover>
              </span>
            );
          })}
        </div>
      )}

      {emptyStateJsx}

      {/* Additional filter-empty state */}
      {isReady && !isLoading && !isError && sortedSignals.length === 0 && allSignals.length > 0 && (
        <p className="text-sm text-[var(--prisma-muted)] py-8 text-center">
          Keine Signale gefunden (Filter zu eng).
        </p>
      )}

      {/* Pro table */}
      {sortedSignals.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <p className="text-xs text-[var(--prisma-muted)]" data-testid="decision-signals-count">
              {sortedSignals.length !== signals.length
                ? `${sortedSignals.length} von ${signals.length} Signalen`
                : `${sortedSignals.length} Signal${sortedSignals.length !== 1 ? 'e' : ''} gefunden`}
            </p>
            <button
              onClick={() => exportDecisionCsv(sortedSignals)}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--prisma-border)] px-2.5 py-1 text-xs font-medium text-[var(--prisma-muted)] hover:bg-[var(--prisma-border)] hover:text-[var(--prisma-text)] transition-colors"
              data-testid="decision-csv-export-btn"
            >
              <Download className="h-3 w-3" />
              CSV
            </button>
          </div>

          <ProTable signals={sortedSignals} />

          {/* Below-table panels */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <ProSignalBreakdownPanel counts={counts} />
            <ProMakroPanel />
          </div>

          {/* Audit Trail section */}
          <div className="space-y-2">
            <h2 className="text-xs font-bold uppercase tracking-widest text-[var(--prisma-muted)]">Audit Trail</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {sortedSignals.map((item) => (
                <SignalCard key={item.ticker} item={item} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
