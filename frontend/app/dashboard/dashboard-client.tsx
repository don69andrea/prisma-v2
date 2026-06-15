'use client';

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { TrendingUp, BarChart2, ArrowRight, Layers } from 'lucide-react';

import { listDecisions, type DecisionSignal } from '@/lib/api/decisions';
import { listUniverses } from '@/lib/api/universes';
import { getMacroContext } from '@/lib/api/macro';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { GuidedTourButton } from '@/components/GuidedTour';
import { DISCOVER_STORAGE_KEY } from '@/app/start/start-client';
import type { DiscoveryResponse } from '@/lib/api/discovery';
import { Skeleton } from '@/components/ui/skeleton';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Guten Morgen';
  if (h < 18) return 'Guten Tag';
  return 'Guten Abend';
}

function formatStand(): string {
  const now = new Date();
  return now.toLocaleString('de-CH', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function getDiscoverTickers(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(DISCOVER_STORAGE_KEY);
    if (!raw) return [];
    const cached = JSON.parse(raw) as DiscoveryResponse;
    return (cached.stocks ?? []).map((s) => s.ticker).slice(0, 12);
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Signal card styles
// ---------------------------------------------------------------------------

const SIGNAL_STYLE: Record<string, { badge: string; bg: string; border: string }> = {
  BUY:  { badge: 'bg-emerald-500/20 text-emerald-400', bg: 'bg-emerald-950/20', border: 'border-emerald-800/40' },
  HOLD: { badge: 'bg-amber-500/20 text-amber-400',    bg: 'bg-amber-950/20',   border: 'border-amber-800/40'   },
  SELL: { badge: 'bg-red-500/20 text-red-400',        bg: 'bg-red-950/20',     border: 'border-red-800/40'     },
};

// ---------------------------------------------------------------------------
// Simple Mode — signal hero card
// ---------------------------------------------------------------------------

function SimpleSignalCard({ signal }: { signal: DecisionSignal }) {
  const style = SIGNAL_STYLE[signal.signal] ?? SIGNAL_STYLE.HOLD;
  return (
    <Link
      href={`/stocks/${signal.ticker}`}
      className={`block rounded-xl p-4 border ${style.border} ${style.bg} hover:brightness-110 transition-all`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs font-bold uppercase px-2 py-0.5 rounded ${style.badge}`}>
          {signal.signal}
        </span>
        <span className="text-sm font-bold text-slate-200">
          {signal.weighted_score.toFixed(0)}/100
        </span>
      </div>
      <div className="font-semibold text-slate-200">{signal.ticker}</div>
      {signal.signal_reason && (
        <p className="mt-1 text-xs text-slate-400 leading-relaxed">
          &quot;{signal.signal_reason}&quot;
        </p>
      )}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode — compact signal row
// ---------------------------------------------------------------------------

function ProSignalRow({ signal }: { signal: DecisionSignal }) {
  const style = SIGNAL_STYLE[signal.signal] ?? SIGNAL_STYLE.HOLD;
  return (
    <Link
      href={`/stocks/${signal.ticker}`}
      className="flex items-start gap-3 rounded-lg px-3 py-3 hover:bg-slate-800/50 transition-colors group"
    >
      <span className={`mt-0.5 shrink-0 text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${style.badge}`}>
        {signal.signal}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-slate-200">{signal.ticker}</span>
          <span className="text-xs text-slate-500 tabular-nums">{signal.weighted_score.toFixed(0)}/100</span>
        </div>
        {signal.signal_reason && (
          <p className="mt-0.5 text-xs text-slate-500 leading-relaxed truncate">
            {signal.signal_reason}
          </p>
        )}
      </div>
      <ArrowRight className="h-3.5 w-3.5 text-slate-600 group-hover:text-slate-400 shrink-0 mt-1 transition-colors" />
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Signals hook — fetches BUY/HOLD/SELL for the user's universe
// ---------------------------------------------------------------------------

function useSignals() {
  const [signals, setSignals] = useState<DecisionSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [universeId, setUniverseId] = useState<string | null>(null);
  const [universeCount, setUniverseCount] = useState<number>(0);

  const { data: universesData } = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
  });

  useEffect(() => {
    const firstId = universesData?.items[0]?.id ?? null;
    setUniverseId(firstId);
    setUniverseCount(universesData?.items.length ?? 0);
  }, [universesData]);

  useEffect(() => {
    if (!universeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    listDecisions(universeId)
      .then((res) => setSignals(res.items))
      .catch(() => setSignals([]))
      .finally(() => setLoading(false));
  }, [universeId]);

  const buy  = signals.filter((s) => s.signal === 'BUY').sort((a, b) => b.weighted_score - a.weighted_score);
  const hold = signals.filter((s) => s.signal === 'HOLD').sort((a, b) => b.weighted_score - a.weighted_score);
  const sell = signals.filter((s) => s.signal === 'SELL').sort((a, b) => b.weighted_score - a.weighted_score);

  // Discover tickers count for the universe size display.
  // We read localStorage once on mount and re-read whenever the storage key
  // changes (e.g. after Discovery-Completion in another component/tab).
  const [discoverTickers, setDiscoverTickers] = useState<string[]>(() => getDiscoverTickers());

  useEffect(() => {
    // Re-read on storage events so the value stays fresh after discovery runs.
    const handleStorage = (e: StorageEvent) => {
      if (e.key === null || e.key === DISCOVER_STORAGE_KEY) {
        setDiscoverTickers(getDiscoverTickers());
      }
    };
    window.addEventListener('storage', handleStorage);
    // Also refresh immediately in case the value was written before this
    // component mounted (same-tab navigation back to dashboard).
    setDiscoverTickers(getDiscoverTickers());
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const universeSize = discoverTickers.length > 0 ? discoverTickers.length : signals.length;

  return { signals, buy, hold, sell, loading, universeId, universeCount, universeSize };
}

// ---------------------------------------------------------------------------
// Simple Mode layout
// ---------------------------------------------------------------------------

function SimpleDashboard() {
  const { buy, hold, sell, loading, universeSize } = useSignals();
  const stand = formatStand();

  // Top 1 of each type for the hero row
  const heroSignals: DecisionSignal[] = [
    ...(buy[0]  ? [buy[0]]  : []),
    ...(hold[0] ? [hold[0]] : []),
    ...(sell[0] ? [sell[0]] : []),
  ];

  return (
    <div className="space-y-8 max-w-2xl">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">{getGreeting()}.</h1>
        <p className="mt-1 text-xs text-slate-500">Stand: {stand}</p>
      </div>

      {/* Hero signals */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-slate-400 uppercase tracking-wider">
          Deine 3 stärksten Signale.
        </h2>

        {loading && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-24 w-full rounded-xl" />
            ))}
          </div>
        )}

        {!loading && heroSignals.length === 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-center">
            <p className="text-sm text-slate-500 mb-3">
              Noch keine Signale vorhanden.
            </p>
            <Link
              href="/rankings"
              className="inline-flex items-center gap-1.5 text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              Ersten Ranking-Run starten <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        )}

        {!loading && heroSignals.length > 0 && (
          <div className="space-y-3">
            {heroSignals.map((sig) => (
              <SimpleSignalCard key={sig.ticker} signal={sig} />
            ))}
          </div>
        )}
      </div>

      {/* Universe link */}
      {universeSize > 0 && (
        <Link
          href="/discover"
          className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowRight className="h-3.5 w-3.5" />
          Alle {universeSize} Aktien in deinem Universum
        </Link>
      )}

      {/* Guided tour */}
      <div className="pt-2">
        <GuidedTourButton />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pro Mode layout
// ---------------------------------------------------------------------------

function ProDashboard() {
  const { buy, hold, sell, loading, universeSize } = useSignals();
  const stand = formatStand();

  const macroQuery = useQuery({
    queryKey: ['macro-context'],
    queryFn: getMacroContext,
    staleTime: 5 * 60 * 1000,
  });

  const macro = macroQuery.data;

  const topBuySignals = buy.slice(0, 5);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard.</h1>
          <p className="mt-1 text-xs text-slate-500">Stand: {stand}</p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500 bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-1.5">
          <BarChart2 className="h-3.5 w-3.5" />
          Pro-Modus
        </div>
      </div>

      {/* Two-column overview */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Markt-Überblick */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Markt-Überblick.
          </h2>
          {macroQuery.isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-28" />
            </div>
          )}
          {macro && (
            <dl className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-slate-500 flex items-center gap-1.5">
                  <TrendingUp className="h-3.5 w-3.5" />
                  Makro-Klima
                </dt>
                <dd className="font-semibold text-slate-200">{macro.climate}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500">SNB Leitzins</dt>
                <dd className="font-semibold text-slate-200">{macro.leitzins.toFixed(2)}%</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500">CHF / EUR</dt>
                <dd className="font-semibold text-slate-200">{macro.chf_eur.toFixed(4)}</dd>
              </div>
              {macro.inflation_ch !== null && (
                <div className="flex items-center justify-between">
                  <dt className="text-slate-500">Inflation CH</dt>
                  <dd className="font-semibold text-slate-200">{macro.inflation_ch.toFixed(1)}%</dd>
                </div>
              )}
              {macro.pmi_ch !== null && (
                <div className="flex items-center justify-between">
                  <dt className="text-slate-500">PMI CH</dt>
                  <dd className="font-semibold text-slate-200">{macro.pmi_ch.toFixed(1)}</dd>
                </div>
              )}
            </dl>
          )}
          {!macroQuery.isLoading && !macro && (
            <p className="text-xs text-slate-600">Makro-Daten nicht verfügbar.</p>
          )}
        </div>

        {/* Dein Universum */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-3">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Dein Universum.
          </h2>
          {loading && (
            <div className="space-y-2">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-28" />
            </div>
          )}
          {!loading && (
            <dl className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-slate-500 flex items-center gap-1.5">
                  <Layers className="h-3.5 w-3.5" />
                  Aktien
                </dt>
                <dd className="font-semibold text-slate-200">{universeSize}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500 text-emerald-500/80">BUY</dt>
                <dd className="font-semibold text-emerald-400">{buy.length}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500 text-amber-500/80">HOLD</dt>
                <dd className="font-semibold text-amber-400">{hold.length}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-500 text-red-500/80">SELL</dt>
                <dd className="font-semibold text-red-400">{sell.length}</dd>
              </div>
            </dl>
          )}
          <Link
            href="/discover"
            className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Universum anpassen <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>

      {/* Top Signale */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            Top Signale heute.
          </h2>
          <Link
            href="/decision"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
          >
            Alle Signale <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {loading && (
          <div className="space-y-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-14 w-full rounded-lg" />
            ))}
          </div>
        )}

        {!loading && topBuySignals.length === 0 && (
          <div className="rounded-lg border border-slate-800 p-4 text-sm text-slate-500">
            Keine BUY-Signale vorhanden.{' '}
            <Link href="/rankings" className="text-blue-400 hover:text-blue-300 transition-colors">
              Ranking-Run starten →
            </Link>
          </div>
        )}

        {!loading && topBuySignals.length > 0 && (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 divide-y divide-slate-800/60">
            {topBuySignals.map((sig) => (
              <ProSignalRow key={sig.ticker} signal={sig} />
            ))}
          </div>
        )}
      </div>

      {/* News placeholder */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
            News heute.
          </h2>
          <Link
            href="/news"
            className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
          >
            3 neue Meldungen <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-500">
          <Link href="/news" className="hover:text-slate-300 transition-colors">
            Aktuelle Nachrichten zu Schweizer Aktien im Research-Bereich.
          </Link>
        </div>
      </div>

      {/* Guided tour */}
      <div className="pt-2">
        <GuidedTourButton />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PRISMA mode switcher (Simple ↔ Pro) — separate from the global Dark/Light
// ModeToggle in layout.tsx
// ---------------------------------------------------------------------------

function PrismaModeSwitcher() {
  const { mode, toggle } = usePrismaMode();
  return (
    <div className="mb-6 flex justify-end">
      <button
        onClick={toggle}
        className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/40 px-3 py-1.5 text-xs text-slate-400 hover:bg-slate-700 hover:text-slate-200 transition-colors"
        aria-label={mode === 'simple' ? 'Zu Pro-Modus wechseln' : 'Zu Einfach-Modus wechseln'}
      >
        {mode === 'simple' ? (
          <>
            <BarChart2 className="h-3.5 w-3.5" />
            Pro-Modus
          </>
        ) : (
          <>
            <Layers className="h-3.5 w-3.5" />
            Einfach-Modus
          </>
        )}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export function DashboardClient() {
  const { isSimple } = usePrismaMode();

  return (
    <div>
      <PrismaModeSwitcher />
      {isSimple ? <SimpleDashboard /> : <ProDashboard />}
    </div>
  );
}
