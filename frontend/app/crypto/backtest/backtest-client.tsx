'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Skeleton } from '@/components/ui/skeleton';
import { CryptoEquityChart } from '@/components/crypto/CryptoEquityChart';
import { getBacktest } from '@/lib/api/crypto-signals';

const COINS = ['BTC','ETH','SOL','BNB','XRP','ADA','AVAX','DOGE','LINK','DOT'];

export function BacktestClient() {
  const [coin, setCoin] = useState('BTC');
  const { data: report, isLoading } = useQuery({
    queryKey: ['backtest', coin],
    queryFn: () => getBacktest(coin),
    staleTime: 30 * 60_000,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={coin}
          onChange={e => setCoin(e.target.value)}
          className="w-36 rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {COINS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <span className="text-sm text-muted-foreground">Coin auswählen</span>
      </div>
      {isLoading && <Skeleton className="h-80 w-full" />}
      {report && <CryptoEquityChart report={report} title={`${coin} — Signal-Engine vs Baselines`} />}
    </div>
  );
}
