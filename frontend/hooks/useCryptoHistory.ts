'use client';

import { useState, useEffect } from 'react';
import { getCryptoHistory } from '@/lib/api/crypto';
import type { CryptoHistoryPoint } from '@/lib/api/crypto';

export function useCryptoHistory(ticker: string, days: number): { data: CryptoHistoryPoint[]; loading: boolean } {
  const [data, setData] = useState<CryptoHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCryptoHistory(ticker, days)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setData([]);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [ticker, days]);

  return { data, loading };
}
