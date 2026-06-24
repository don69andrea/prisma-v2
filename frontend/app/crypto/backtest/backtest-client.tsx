'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
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
        <Select value={coin} onValueChange={setCoin}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {COINS.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">Coin auswählen</span>
      </div>
      {isLoading && <Skeleton className="h-80 w-full" />}
      {report && <CryptoEquityChart report={report} title={`${coin} — Signal-Engine vs Baselines`} />}
    </div>
  );
}
