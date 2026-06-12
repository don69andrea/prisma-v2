'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { getPersonalizedStocks, type DiscoveredStock, type DiscoveryResponse } from '@/lib/api/discovery';
import { DISCOVER_STORAGE_KEY } from '@/app/start/start-client';

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

function StockCard({ stock }: { stock: DiscoveredStock }) {
  const color = SECTOR_COLOR[stock.sector ?? ''] ?? '#8b949e';
  const label = SECTOR_LABELS[stock.sector ?? ''] ?? stock.sector ?? '—';

  return (
    <Link
      href={`/stocks/${stock.ticker}`}
      className="glass-card p-4 flex flex-col gap-3 hover:border-[#58a6ff]/40 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-[#e6edf3] text-sm leading-none">{stock.name}</div>
          <div className="text-xs text-[#8b949e] mt-1">{stock.ticker}.SW</div>
        </div>
        <span
          className="text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0"
          style={{ backgroundColor: `${color}22`, color }}
        >
          {label}
        </span>
      </div>

      <div className="flex items-center justify-between text-xs text-[#8b949e]">
        <span>{stock.exchange}</span>
        {stock.market_cap_chf && (
          <span>
            CHF {(Number(stock.market_cap_chf) / 1e9).toFixed(1)} Mrd.
          </span>
        )}
      </div>

      <div className="text-[11px] text-[#58a6ff] flex items-center gap-1">
        Durchleuchten →
      </div>
    </Link>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-16 space-y-4">
      <div
        className="w-12 h-12 rotate-45 rounded-sm mx-auto"
        style={{
          background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)',
          opacity: 0.4,
        }}
      />
      <p className="text-[#8b949e] text-sm max-w-xs mx-auto">
        Noch keine Titel ausgewählt. Starte den geführten Einstieg um dein persönliches Universe zu erstellen.
      </p>
      <Link
        href="/start"
        className="inline-block rounded-lg px-5 py-2.5 text-sm font-semibold text-[#0d1117] transition-all hover:opacity-90"
        style={{ background: 'linear-gradient(135deg, #58a6ff 0%, #7ee787 100%)' }}
      >
        Jetzt starten →
      </Link>
    </div>
  );
}

export function DiscoverClient() {
  const [stocks, setStocks]     = useState<DiscoveredStock[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading]   = useState(true);

  useEffect(() => {
    const raw = localStorage.getItem(DISCOVER_STORAGE_KEY);
    if (!raw) {
      setLoading(false);
      return;
    }

    const cached = JSON.parse(raw) as DiscoveryResponse;
    setSessionId(cached.session_id);

    if (cached.stocks.length > 0) {
      setStocks(cached.stocks);
      setLoading(false);
      return;
    }

    // Cached stocks empty — try live fetch
    getPersonalizedStocks(cached.session_id)
      .then((data) => {
        setStocks(data.stocks);
        localStorage.setItem(DISCOVER_STORAGE_KEY, JSON.stringify(data));
      })
      .catch(() => {/* backend not available yet */})
      .finally(() => setLoading(false));
  }, []);

  const hasStocks = stocks.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#e6edf3]">Mein Universe</h1>
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

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-28 rounded-xl animate-pulse"
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

      {/* CTA to decision */}
      {hasStocks && (
        <div
          className="rounded-xl p-4 flex items-center justify-between gap-4"
          style={{ background: 'rgba(88,166,255,0.07)', border: '1px solid rgba(88,166,255,0.15)' }}
        >
          <div>
            <div className="text-sm font-medium text-[#e6edf3]">Bereit für die Signale?</div>
            <div className="text-xs text-[#8b949e]">
              BUY / HOLD / WATCH mit vollständigem Audit-Trail
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
