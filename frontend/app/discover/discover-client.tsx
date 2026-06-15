'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Bell, Compass } from 'lucide-react';

import { completeDiscovery, type DiscoveredStock, type DiscoveryResponse } from '@/lib/api/discovery';
import { DISCOVER_STORAGE_KEY } from '@/app/start/start-client';
import { InfoPopover } from '@/components/InfoPopover';

const SECTOR_LABELS: Record<string, string> = {
  consumer:   'Konsum',
  pharma:     'Pharma',
  finance:    'Finanzen',
  industrial: 'Industrie',
  tech:       'Tech',
  luxury:     'Lifestyle',
};

const SECTOR_COLOR: Record<string, string> = {
  consumer:   '#7ee787',
  pharma:     '#58a6ff',
  finance:    '#bc8cff',
  industrial: '#ffa657',
  tech:       '#58a6ff',
  luxury:     '#f85149',
};

const SIGNAL_STYLE: Record<string, string> = {
  BUY:  'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  HOLD: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  SELL: 'bg-red-500/20 text-red-400 border border-red-500/30',
};

function ThreeABadge() {
  return (
    <span className="inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 border border-violet-500/30">
      3a
      <InfoPopover ariaLabel="Info: Säule 3a">
        Diese Aktie kann für die Säule 3a (Altersvorsorge) verwendet werden
      </InfoPopover>
    </span>
  );
}

function StockCard({ stock }: { stock: DiscoveredStock & { signal?: string; score?: number; is_3a_eligible?: boolean } }) {
  const color = SECTOR_COLOR[stock.sector ?? ''] ?? '#8b949e';
  const label = SECTOR_LABELS[stock.sector ?? ''] ?? stock.sector ?? null;
  const score = stock.score ?? null;
  const signal = stock.signal ?? null;
  const is3a = stock.is_3a_eligible === true;

  return (
    <div className="glass-card p-4 flex flex-col gap-3 hover:border-[#58a6ff]/40 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-[#e6edf3] text-sm leading-none">{stock.name}</div>
          <div className="text-xs text-[#8b949e] mt-1">{stock.ticker}.SW</div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {label && (
            <span
              className="text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0"
              style={{ backgroundColor: `${color}22`, color }}
            >
              {label}
            </span>
          )}
          {signal && (
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${SIGNAL_STYLE[signal] ?? ''}`}>
              {signal}
            </span>
          )}
        </div>
      </div>

      {score !== null && (
        <div className="space-y-0.5">
          <div className="flex items-center gap-1">
            <div className="h-1 flex-1 rounded-full bg-green-500/20 overflow-hidden">
              <div style={{ width: `${score}%` }} className="h-full bg-green-500 rounded-full" />
            </div>
            <span className="text-[10px] text-[#8b949e] tabular-nums w-6 text-right">{score}</span>
            <InfoPopover ariaLabel="Info: PRISMA-Score">
              PRISMA-Score: Bewertung von 0–100 basierend auf technischer Analyse, KI-Prognose und Makroökonomie
            </InfoPopover>
          </div>
        </div>
      )}

      {stock.signal_reason && (
        <p className="text-[11px] text-[#8b949e] italic leading-relaxed">
          &quot;{stock.signal_reason}&quot;
        </p>
      )}

      <div className="flex items-center justify-between text-xs text-[#8b949e]">
        <div className="flex items-center gap-2">
          <span>{stock.exchange}</span>
          {is3a && <ThreeABadge />}
        </div>
        {stock.market_cap_chf && (
          <span>
            CHF {(Number(stock.market_cap_chf) / 1e9).toFixed(1)} Mrd.
          </span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <Link href={`/stocks/${stock.ticker}`} className="text-[11px] text-[#58a6ff] flex items-center gap-1">
          Durchleuchten →
        </Link>
        <Link
          href={`/alerts?ticker=${stock.ticker}`}
          className="text-[11px] text-[#8b949e] hover:text-[#58a6ff] transition-colors flex items-center gap-1"
          onClick={(e) => e.stopPropagation()}
        >
          <Bell className="h-3 w-3" />
          Alert
        </Link>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <Compass className="h-10 w-10 text-muted-foreground/40" />
      <p className="text-sm font-medium">Dein persönliches Aktien-Universum</p>
      <p className="text-xs text-muted-foreground max-w-sm">
        Beantworte 7 kurze Fragen und wir empfehlen dir Schweizer Aktien die zu deinem Profil passen
      </p>
      <Link
        href="/start"
        className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-md transition-colors"
      >
        Profil erstellen
      </Link>
    </div>
  );
}

export function DiscoverClient() {
  const [stocks, setStocks]       = useState<DiscoveredStock[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);

  function load() {
    setError(null);
    setLoading(true);

    const raw = localStorage.getItem(DISCOVER_STORAGE_KEY);
    if (!raw) {
      setLoading(false);
      return;
    }

    let cached: DiscoveryResponse;
    try {
      cached = JSON.parse(raw) as DiscoveryResponse;
    } catch {
      setError('Gespeichertes Profil konnte nicht gelesen werden. Bitte neu starten.');
      setLoading(false);
      return;
    }

    setSessionId(cached.session_id);

    if (cached.stocks.length > 0) {
      setStocks(cached.stocks);
      setLoading(false);
      return;
    }

    // Cached stocks empty — re-complete the session via turn-by-turn API
    completeDiscovery(cached.session_id)
      .then((data) => {
        const updated: DiscoveryResponse = {
          session_id: cached.session_id,
          total: data.recommended_stocks.length,
          stocks: data.recommended_stocks,
        };
        setStocks(updated.stocks);
        localStorage.setItem(DISCOVER_STORAGE_KEY, JSON.stringify(updated));
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Unbekannter Fehler';
        setError(`Titel konnten nicht geladen werden: ${msg}`);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const hasStocks = stocks.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-1">
            <h1 className="text-2xl font-bold text-[#e6edf3]">Mein Universum.</h1>
            <InfoPopover ariaLabel="Info: Mein Universum">
              Hier siehst du Schweizer Aktien die zu deinem persönlichen Profil passen. PRISMA wählt sie basierend auf deinem Risikotyp, Anlageziel und deinen Präferenzen aus.
            </InfoPopover>
          </div>
          <p className="text-sm text-[#8b949e] mt-1">
            {hasStocks
              ? `${stocks.length} Titel — ausgewählt für dein Profil`
              : 'Personalisierte Schweizer Titel'}
          </p>
        </div>
        {sessionId && (
          <Link
            href="/start"
            className="text-xs text-[#8b949e] hover:text-[#58a6ff] transition-colors"
          >
            Profil neu erstellen →
          </Link>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div
          className="rounded-xl p-4 flex items-center justify-between gap-4"
          style={{ background: 'rgba(248,81,73,0.08)', border: '1px solid rgba(248,81,73,0.25)' }}
        >
          <div className="text-sm text-[#f85149]">{error}</div>
          <button
            onClick={load}
            className="shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold text-[#f85149] border border-[#f85149]/40 hover:bg-[#f85149]/10 transition-colors"
          >
            Erneut versuchen
          </button>
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-36 rounded-xl animate-pulse"
              style={{ background: '#161b22', border: '1px solid #21262d' }}
            />
          ))}
        </div>
      ) : hasStocks ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {stocks.map((s) => (
            <StockCard key={s.ticker} stock={s} />
          ))}
        </div>
      ) : (
        <EmptyState />
      )}

      {hasStocks && (
        <div className="text-center pt-2">
          <span className="text-xs text-[#8b949e]">
            Basierend auf: deinem Risikotyp · Anlageziel · Sektoren
          </span>
          {' · '}
          <Link href="/start" className="text-xs text-[#58a6ff] hover:underline">
            Profil anpassen →
          </Link>
        </div>
      )}

      {/* CTA to decision */}
      {hasStocks && (
        <div
          className="rounded-xl p-4 flex items-center justify-between gap-4"
          style={{ background: 'rgba(88,166,255,0.07)', border: '1px solid rgba(88,166,255,0.15)' }}
        >
          <div>
            <div className="text-sm font-medium text-[#e6edf3]">Bereit für die Signale?</div>
            <div className="text-xs text-[#8b949e]">
              BUY / HOLD / SELL mit vollständigem Audit-Trail
            </div>
          </div>
          <Link
            href={`/decision?tickers=${stocks.slice(0, 12).map((s) => s.ticker).join(',')}`}
            className="shrink-0 rounded-lg px-4 py-2 text-sm font-semibold text-[#0d1117] whitespace-nowrap transition-all hover:opacity-90"
            style={{ background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)' }}
          >
            Zu den Signalen →
          </Link>
        </div>
      )}
    </div>
  );
}
