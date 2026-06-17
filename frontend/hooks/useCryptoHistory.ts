'use client';

import { useQuery } from '@tanstack/react-query';
import { getCryptoHistory, type CryptoHistoryPoint } from '@/lib/api/crypto';

export function useCryptoHistory(ticker: string, days: number): { data: CryptoHistoryPoint[]; loading: boolean } {
  const { data, isLoading } = useQuery<CryptoHistoryPoint[]>({
    queryKey: ['crypto-history', ticker, days],
    queryFn: () => getCryptoHistory(ticker, days),
    staleTime: 10 * 60 * 1000,
    enabled: Boolean(ticker),
  });
  return { data: data ?? [], loading: isLoading };
}
