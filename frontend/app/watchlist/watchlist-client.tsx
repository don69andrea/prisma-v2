'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Plus, X, Bell, BellOff, Search, BookMarked } from 'lucide-react';
import { usePrismaMode } from '@/hooks/usePrismaMode';
import { liveDecisions, type DecisionSignal } from '@/lib/api/decisions';
import { listAlerts, type Alert } from '@/lib/api/alerts';
import { PrismaBar } from '@/components/ui/PrismaBar';

const WATCHLIST_KEY = 'prisma_watchlist';

const SMI_STOCKS = [
  { ticker: 'NOVN', name: 'Novartis AG' },
  { ticker: 'ROG', name: 'Roche Holding AG' },
  { ticker: 'NESN', name: 'Nestlé SA' },
  { ticker: 'UBSG', name: 'UBS Group AG' },
  { ticker: 'ABBN', name: 'ABB Ltd' },
  { ticker: 'SREN', name: 'Swiss Re AG' },
  { ticker: 'ZURN', name: 'Zurich Insurance Group AG' },
  { ticker: 'GIVN', name: 'Givaudan SA' },
  { ticker: 'LONN', name: 'Lonza Group AG' },
  { ticker: 'SLHN', name: 'Swiss Life Holding AG' },
  { ticker: 'SGKN', name: 'Sika AG' },
  { ticker: 'SCMN', name: 'Swisscom AG' },
  { ticker: 'KNIN', name: 'Kühne + Nagel International AG' },
  { ticker: 'BAER', name: 'Julius Baer Group AG' },
  { ticker: 'ADEN', name: 'Adecco Group AG' },
  { ticker: 'GEBN', name: 'Geberit AG' },
  { ticker: 'CFR', name: 'Compagnie Financière Richemont SA' },
  { ticker: 'HOLN', name: 'Holcim Ltd' },
  { ticker: 'PGHN', name: 'Partners Group Holding AG' },
  { ticker: 'ALC', name: 'Alcon Inc' },
];

const STOCK_NAME: Record<string, string> = Object.fromEntries(
  SMI_STOCKS.map((s) => [s.ticker, s.name]),
);

const SIGNAL_STYLE: Record<string, string> = {
  BUY:  'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  HOLD: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  SELL: 'bg-red-500/20 text-red-400 border border-red-500/30',
};

const SIGNAL_BAR_COLOR: Record<string, string> = {
  BUY:  'bg-emerald-500',
  HOLD: 'bg-amber-500',
  SELL: 'bg-red-500',
};

// ─── Simple Mode Row ────────────────────────────────────────────────────────

interface SimpleRowProps {
  ticker: string;
  signal?: DecisionSignal;
  hasAlert: boolean;
  onRemove: (ticker: string) => void;
}

function SimpleRow({ ticker, signal, hasAlert, onRemove }: SimpleRowProps) {
  const name = STOCK_NAME[ticker] ?? ticker;
  const signalLabel = signal?.signal ?? null;
  const score = signal ? Math.round(signal.weighted_score) : null;
  const barColor = signalLabel ? (SIGNAL_BAR_COLOR[signalLabel] ?? 'bg-[var(--prisma-muted)]') : 'bg-[var(--prisma-muted)]';

  return (
    <div
      className="flex items-center gap-3 px-4 py-3 rounded-xl transition-colors"
      style={{ background: 'var(--prisma-surface)', border: '1px solid var(--prisma-border)' }}
    >
      {/* Ticker + Name */}
      <Link
        href={`/stocks/${ticker}`}
        className="flex-1 min-w-0 hover:opacity-80 transition-opacity"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="font-semibold text-[var(--prisma-text)] text-sm shrink-0">{name}</span>
          <span className="text-xs text-[var(--prisma-muted)] shrink-0">{ticker}</span>
          {/* Score bar */}
          {score !== null && signalLabel ? (
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <div className="h-1 flex-1 rounded-full bg-[var(--prisma-border)] overflow-hidden max-w-[80px]">
                <div
                  className={`h-full rounded-full ${barColor}`}
                  style={{ width: `${Math.min(score, 100)}%` }}
                />
              </div>
            </div>
          ) : (
            <span className="text-[var(--prisma-muted)] text-xs opacity-40">─</span>
          )}
        </div>
      </Link>

      {/* Signal badge */}
      <div className="shrink-0 flex items-center gap-2">
        {signalLabel ? (
          <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${SIGNAL_STYLE[signalLabel] ?? ''}`}>
            {signalLabel}
            {score !== null && ` ${score}`}
          </span>
        ) : (
          <span className="text-xs text-[var(--prisma-muted)] tabular-nums">—</span>
        )}

        {/* Alert status */}
        <Link
          href={`/alerts?ticker=${ticker}`}
          className="flex items-center gap-1 text-xs shrink-0 transition-colors"
          title={hasAlert ? 'Alert aktiv' : 'Alert setzen'}
        >
          {hasAlert ? (
            <span className="flex items-center gap-1 text-emerald-400">
              <Bell className="h-3.5 w-3.5" />
              <span className="hidden sm:inline text-[10px] font-medium">aktiv</span>
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[var(--prisma-muted)] hover:text-[var(--prisma-blue)]">
              <BellOff className="h-3.5 w-3.5" />
              <span className="hidden sm:inline text-[10px]">setzen</span>
            </span>
          )}
        </Link>

        {/* Remove */}
        <button
          onClick={() => onRemove(ticker)}
          className="text-[var(--prisma-muted)] hover:text-[var(--prisma-red)] transition-colors p-0.5 rounded"
          aria-label={`${ticker} entfernen`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─── Pro Mode Table ──────────────────────────────────────────────────────────

interface ProTableProps {
  tickers: string[];
  signals: Record<string, DecisionSignal>;
  alertTickers: Set<string>;
  onRemove: (ticker: string) => void;
}

function ProTable({ tickers, signals, alertTickers, onRemove }: ProTableProps) {
  return (
    <div className="overflow-x-auto rounded-xl" style={{ border: '1px solid var(--prisma-border)' }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ background: 'var(--prisma-bg)', borderBottom: '1px solid var(--prisma-border)' }}>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-[var(--prisma-muted)] uppercase tracking-wide">Ticker</th>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-[var(--prisma-muted)] uppercase tracking-wide">Name</th>
            <th className="text-left px-4 py-2.5 text-xs font-semibold text-[var(--prisma-muted)] uppercase tracking-wide">Signal</th>
            <th className="text-right px-4 py-2.5 text-xs font-semibold text-[var(--prisma-muted)] uppercase tracking-wide">Score</th>
            <th className="text-center px-4 py-2.5 text-xs font-semibold text-[var(--prisma-muted)] uppercase tracking-wide">Alert</th>
            <th className="px-4 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker, i) => {
            const d = signals[ticker];
            const signalLabel = d?.signal ?? null;
            const score = d ? Math.round(d.weighted_score) : null;
            const hasAlert = alertTickers.has(ticker);
            const isLast = i === tickers.length - 1;

            return (
              <tr
                key={ticker}
                style={{
                  background: i % 2 === 0 ? 'var(--prisma-surface)' : 'var(--prisma-bg)',
                  borderBottom: isLast ? undefined : '1px solid var(--prisma-border)',
                }}
                className="hover:opacity-90 transition-opacity"
              >
                <td className="px-4 py-3">
                  <Link href={`/stocks/${ticker}`} className="font-mono text-xs text-[var(--prisma-blue)] hover:underline">
                    {ticker}
                  </Link>
                </td>
                <td className="px-4 py-3 text-[var(--prisma-text)] text-xs">
                  {STOCK_NAME[ticker] ?? ticker}
                </td>
                <td className="px-4 py-3">
                  {signalLabel ? (
                    <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${SIGNAL_STYLE[signalLabel] ?? ''}`}>
                      {signalLabel}
                    </span>
                  ) : (
                    <span className="text-xs text-[var(--prisma-muted)]">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {score !== null ? (
                    <span className="text-xs text-[var(--prisma-text)] tabular-nums font-medium">{score}</span>
                  ) : (
                    <span className="text-xs text-[var(--prisma-muted)]">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center">
                  <Link
                    href={`/alerts?ticker=${ticker}`}
                    className="inline-flex items-center justify-center"
                    title={hasAlert ? 'Alert aktiv' : 'Alert setzen'}
                  >
                    {hasAlert ? (
                      <Bell className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <BellOff className="h-3.5 w-3.5 text-[var(--prisma-muted)] hover:text-[var(--prisma-blue)] transition-colors" />
                    )}
                  </Link>
                </td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => onRemove(ticker)}
                    className="text-[var(--prisma-muted)] hover:text-[var(--prisma-red)] transition-colors p-0.5 rounded"
                    aria-label={`${ticker} entfernen`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Tax Placeholder (Pro only) ──────────────────────────────────────────────

function TaxOverview() {
  return (
    <div
      className="rounded-xl p-4 space-y-3"
      style={{ background: 'var(--prisma-surface)', border: '1px solid var(--prisma-border)' }}
    >
      <h2 className="text-sm font-semibold text-[var(--prisma-text)]">Steuer-Überblick</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div
          className="rounded-lg p-3 space-y-1"
          style={{ background: 'var(--prisma-bg)', border: '1px solid var(--prisma-border)' }}
        >
          <div className="text-[10px] text-[var(--prisma-muted)] uppercase tracking-wide font-medium">Nächste Dividenden</div>
          <div className="text-xs text-[var(--prisma-muted)] italic">Wird ergänzt</div>
        </div>
        <div
          className="rounded-lg p-3 space-y-1"
          style={{ background: 'var(--prisma-bg)', border: '1px solid var(--prisma-border)' }}
        >
          <div className="text-[10px] text-[var(--prisma-muted)] uppercase tracking-wide font-medium">Verrechnungssteuer rückforderbar</div>
          <div className="text-xs text-[var(--prisma-muted)] italic">Wird berechnet</div>
        </div>
      </div>
    </div>
  );
}

// ─── Search / Add ────────────────────────────────────────────────────────────

interface AddStockPanelProps {
  query: string;
  onQueryChange: (q: string) => void;
  results: typeof SMI_STOCKS;
  onAdd: (ticker: string) => void;
  onClose: () => void;
}

function AddStockPanel({ query, onQueryChange, results, onAdd, onClose }: AddStockPanelProps) {
  return (
    <div
      className="rounded-xl p-4 space-y-3"
      style={{ background: 'var(--prisma-surface)', border: '1px solid var(--prisma-border)' }}
    >
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--prisma-muted)]" />
          <input
            autoFocus
            type="text"
            placeholder="Firma oder Ticker eingeben..."
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            className="w-full pl-8 pr-3 py-2 text-sm rounded-lg bg-[var(--prisma-bg)] text-[var(--prisma-text)] placeholder-[var(--prisma-muted)] outline-none focus:ring-1 focus:ring-[var(--prisma-blue)]/50"
            style={{ border: '1px solid var(--prisma-border)' }}
          />
        </div>
        <button
          onClick={onClose}
          className="text-[var(--prisma-muted)] hover:text-[var(--prisma-text)] transition-colors p-1.5 rounded"
          aria-label="Suche schliessen"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {results.length > 0 && (
        <ul className="space-y-1 max-h-52 overflow-y-auto">
          {results.map((s) => (
            <li key={s.ticker}>
              <button
                onClick={() => onAdd(s.ticker)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-colors hover:bg-[var(--prisma-surface)]"
              >
                <span className="text-sm text-[var(--prisma-text)]">{s.name}</span>
                <span className="text-xs text-[var(--prisma-muted)] font-mono ml-2 shrink-0">{s.ticker}.SW</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {query.length >= 1 && results.length === 0 && (
        <p className="text-xs text-[var(--prisma-muted)] px-1">Keine Treffer für &ldquo;{query}&rdquo;</p>
      )}
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────────

interface EmptyStateProps {
  onAdd: () => void;
}

function EmptyState({ onAdd }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center gap-4">
      <BookMarked className="h-12 w-12 text-[var(--prisma-muted)]/40" />
      <div className="space-y-1 max-w-xs">
        <p className="text-sm font-medium text-[var(--prisma-text)]">
          Füge Aktien hinzu die dich interessieren —
        </p>
        <p className="text-xs text-[var(--prisma-muted)]">
          PRISMA zeigt dir live wie sich die Signale entwickeln.
        </p>
      </div>
      <button
        onClick={onAdd}
        className="mt-2 flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-[#0d1117] transition-all hover:opacity-90"
        style={{ background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)' }}
      >
        <Plus className="h-4 w-4" />
        Erste Aktie hinzufügen
      </button>
    </div>
  );
}

// ─── Main Client ─────────────────────────────────────────────────────────────

export function WatchlistClient() {
  const { isSimple, isPro } = usePrismaMode();

  const [tickers, setTickers] = useState<string[]>([]);
  const [signals, setSignals] = useState<Record<string, DecisionSignal>>({});
  const [alertTickers, setAlertTickers] = useState<Set<string>>(new Set());
  const [loadingSignals, setLoadingSignals] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);

  // Load watchlist from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(WATCHLIST_KEY);
      if (stored) {
        const parsed = JSON.parse(stored) as string[];
        if (Array.isArray(parsed)) setTickers(parsed);
      }
    } catch {
      // ignore malformed data
    }
  }, []);

  // Fetch signals whenever tickers change
  useEffect(() => {
    if (tickers.length === 0) {
      setSignals({});
      return;
    }

    setLoadingSignals(true);
    // liveDecisions supports up to 12 tickers
    const batch = tickers.slice(0, 12);
    liveDecisions(batch)
      .then((res) => {
        const map: Record<string, DecisionSignal> = {};
        for (const item of res.items) {
          map[item.ticker] = item;
        }
        setSignals(map);
      })
      .catch(() => {
        // API unavailable — show dashes, not an error
        setSignals({});
      })
      .finally(() => setLoadingSignals(false));
  }, [tickers]);

  // Fetch active alerts to show "Alert aktiv" state
  useEffect(() => {
    if (tickers.length === 0) {
      setAlertTickers(new Set());
      return;
    }
    listAlerts()
      .then((res) => {
        const active = new Set(
          res.alerts
            .filter((a: Alert) => a.is_active && tickers.includes(a.ticker))
            .map((a: Alert) => a.ticker),
        );
        setAlertTickers(active);
      })
      .catch(() => {
        setAlertTickers(new Set());
      });
  }, [tickers]);

  function saveTickers(next: string[]) {
    setTickers(next);
    try {
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(next));
    } catch {
      // ignore quota errors
    }
  }

  function addTicker(ticker: string) {
    if (tickers.includes(ticker)) return;
    saveTickers([...tickers, ticker]);
    setSearchQuery('');
    setShowSearch(false);
  }

  function removeTicker(ticker: string) {
    saveTickers(tickers.filter((t) => t !== ticker));
  }

  const searchResults =
    searchQuery.length >= 1
      ? SMI_STOCKS.filter(
          (s) =>
            s.ticker.toLowerCase().includes(searchQuery.toLowerCase()) ||
            s.name.toLowerCase().includes(searchQuery.toLowerCase()),
        ).filter((s) => !tickers.includes(s.ticker))
      : [];

  const isEmpty = tickers.length === 0;
  const title = isSimple ? 'Meine Watchlist.' : 'Watchlist.';
  const subtitle = isSimple
    ? 'Aktien die du beobachtest.'
    : `${tickers.length} Titel in deiner Watchlist`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--prisma-text)]">{title}</h1>
          <p className="text-sm text-[var(--prisma-muted)] mt-1">{subtitle}</p>
        </div>

        {!isEmpty && (
          <button
            onClick={() => setShowSearch((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors text-[var(--prisma-muted)] hover:text-[var(--prisma-text)] hover:bg-[var(--prisma-surface)]"
            style={{ border: '1px solid var(--prisma-border)' }}
          >
            <Plus className="h-4 w-4" />
            Aktie hinzufügen
          </button>
        )}
      </div>

      {/* Search Panel */}
      {showSearch && (
        <AddStockPanel
          query={searchQuery}
          onQueryChange={setSearchQuery}
          results={searchResults}
          onAdd={addTicker}
          onClose={() => {
            setShowSearch(false);
            setSearchQuery('');
          }}
        />
      )}

      {/* Content */}
      {isEmpty ? (
        <EmptyState onAdd={() => setShowSearch(true)} />
      ) : (
        <>
          {/* Signals loading indicator */}
          {loadingSignals && (
            <div className="space-y-1">
              <PrismaBar />
              <p className="text-xs text-muted-foreground">Signale werden geladen…</p>
            </div>
          )}

          {/* Simple Mode: rows */}
          {isSimple && (
            <div className="space-y-2">
              {tickers.map((ticker) => (
                <SimpleRow
                  key={ticker}
                  ticker={ticker}
                  signal={signals[ticker]}
                  hasAlert={alertTickers.has(ticker)}
                  onRemove={removeTicker}
                />
              ))}
            </div>
          )}

          {/* Pro Mode: table */}
          {isPro && (
            <ProTable
              tickers={tickers}
              signals={signals}
              alertTickers={alertTickers}
              onRemove={removeTicker}
            />
          )}

          {/* Pro Mode: Tax overview placeholder */}
          {isPro && <TaxOverview />}
        </>
      )}
    </div>
  );
}
