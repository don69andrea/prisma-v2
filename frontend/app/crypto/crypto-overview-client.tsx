'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { InfoPopover } from '@/components/InfoPopover';
import { CryptoSignalBadge } from '@/components/crypto/CryptoSignalBadge';
import { MiniSparkline } from '@/components/crypto/MiniSparkline';
import { listSignals } from '@/lib/api/crypto-signals';
import { getOHLCV } from '@/lib/api/ohlcv';
import type { SignalVector } from '@/lib/api/crypto-signals';
import Link from 'next/link';

type SortKey = 'coin' | 'action' | 'confidence' | 'size_factor';

export function CryptoOverviewClient() {
  const [sortKey, setSortKey] = useState<SortKey>('confidence');
  const [sortDesc, setSortDesc] = useState(true);

  const { data: signals, isLoading, error } = useQuery({
    queryKey: ['v4-signals'],
    queryFn: listSignals,
    staleTime: 5 * 60_000,
  });

  const sorted = [...(signals ?? [])].sort((a, b) => {
    const av = a[sortKey] as string | number;
    const bv = b[sortKey] as string | number;
    if (typeof av === 'number' && typeof bv === 'number') {
      return sortDesc ? bv - av : av - bv;
    }
    return sortDesc
      ? String(bv).localeCompare(String(av))
      : String(av).localeCompare(String(bv));
  });

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDesc(!sortDesc);
    else { setSortKey(key); setSortDesc(true); }
  };

  const SortBtn = ({ label, k }: { label: string; k: SortKey }) => (
    <button
      onClick={() => toggleSort(k)}
      className="flex items-center gap-1 text-left hover:text-foreground transition-colors"
    >
      {label}
      <ArrowUpDown size={12} className={sortKey === k ? 'opacity-100' : 'opacity-30'} />
    </button>
  );

  return (
    <div className="space-y-4">
      <div className="rounded border border-amber-200 bg-amber-50/60 dark:border-amber-800/40 dark:bg-amber-950/10 px-4 py-2 text-xs text-amber-700 dark:text-amber-400">
        Entscheidungsunterstützung, kein Anlagerat. SELL = raus/cash (kein Shorting). Konfidenz-Quelle: deterministische Signal-Engine.
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            Krypto-Signale
            <InfoPopover ariaLabel="Info: Krypto-Signale">
              Signale basieren auf der V4-1 Signal-Engine (Trend-Following + Vol-Targeting).
              Alle Zahlen sind Out-of-Sample Walk-Forward Backtests, netto 0.1% Kosten.
              Kein Versprechen zukünftiger Renditen.
            </InfoPopover>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}
          {error && (
            <p className="text-destructive text-sm">Fehler beim Laden der Signale. Backend verfügbar?</p>
          )}
          {signals && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs">
                    <th className="pb-2 text-left"><SortBtn label="Coin" k="coin" /></th>
                    <th className="pb-2 text-left"><SortBtn label="Signal" k="action" /></th>
                    <th className="pb-2 text-right"><SortBtn label="Größe" k="size_factor" /></th>
                    <th className="pb-2 text-right"><SortBtn label="Konfidenz" k="confidence" /></th>
                    <th className="pb-2 text-center">Konsens</th>
                    <th className="pb-2 text-right hidden sm:table-cell">Trend (7T)</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((sig) => (
                    <CoinRow key={sig.coin} signal={sig} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function CoinRow({ signal }: { signal: SignalVector }) {
  const { data: ohlcv } = useQuery({
    queryKey: ['ohlcv', signal.coin, 7],
    queryFn: () => getOHLCV(signal.coin, 7),
    staleTime: 10 * 60_000,
  });

  const sparkData = ohlcv?.bars.map(b => ({ date: b.date, close: b.close })) ?? [];
  const isPositive = sparkData.length >= 2
    ? sparkData[sparkData.length - 1].close >= sparkData[0].close
    : undefined;

  const shortCoin = signal.coin.replace(/-USD$/, '');

  return (
    <tr className="border-b last:border-0 hover:bg-muted/20 transition-colors">
      <td className="py-2.5 pr-3">
        <Link
          href={`/crypto/${shortCoin.toLowerCase()}`}
          className="font-semibold hover:underline"
        >
          {shortCoin}
        </Link>
        <div className="text-[10px] text-muted-foreground">{signal.asof}</div>
      </td>
      <td className="py-2.5 pr-3">
        <CryptoSignalBadge action={signal.action} confidence={signal.confidence} />
      </td>
      <td className="py-2.5 text-right font-mono text-sm">
        {signal.size_factor.toFixed(2)}×
      </td>
      <td className="py-2.5 text-right">
        {Math.round(signal.confidence * 100)}%
      </td>
      <td className="py-2.5 text-center text-sm">{signal.consensus}</td>
      <td className="py-2.5 text-right hidden sm:table-cell">
        <MiniSparkline data={sparkData} positive={isPositive} />
      </td>
    </tr>
  );
}
