'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Search } from 'lucide-react';

import { listStocks, type StockRead } from '@/lib/api/stocks';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { SwissBadge } from '@/components/ui/swiss-badge';
import { cn } from '@/lib/utils';

const MARKET_CAP_3A_THRESHOLD = 100_000_000; // 100M CHF

function is3aEligible(stock: StockRead): boolean {
  if (stock.exchange !== 'XSWX') return false;
  if (!stock.market_cap_chf) return false;
  return parseFloat(stock.market_cap_chf) >= MARKET_CAP_3A_THRESHOLD;
}

function formatMarketCap(value: string | null): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (n >= 1e12) return `${(n / 1e12).toFixed(1)} Bio.`;
  if (n >= 1e9)  return `${(n / 1e9).toFixed(1)} Mrd.`;
  if (n >= 1e6)  return `${(n / 1e6).toFixed(0)} Mio.`;
  return `CHF ${n.toFixed(0)}`;
}

const EXCHANGE_OPTIONS = [
  { value: '',     label: 'Alle Börsen' },
  { value: 'XSWX', label: 'SIX (Schweiz)' },
];

export function StocksListClient() {
  const [search, setSearch] = useState('');
  const [exchange, setExchange] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['stocks-list', exchange],
    queryFn: () => listStocks(200, 0, exchange || undefined),
    staleTime: 5 * 60 * 1000,
  });

  const sectors = useMemo(() => {
    if (!data) return [];
    const s = new Set(data.items.map((s) => s.sector).filter(Boolean) as string[]);
    return Array.from(s).sort();
  }, [data]);

  const [sector, setSector] = useState('');

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    return data.items.filter((s) => {
      if (q && !s.ticker.toLowerCase().includes(q) && !s.name.toLowerCase().includes(q)) return false;
      if (sector && s.sector !== sector) return false;
      return true;
    });
  }, [data, search, sector]);

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Ticker oder Name suchen…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            data-testid="stocks-search"
          />
        </div>
        <select
          value={exchange}
          onChange={(e) => setExchange(e.target.value)}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          data-testid="stocks-exchange-filter"
        >
          {EXCHANGE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          disabled={sectors.length === 0}
          className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          data-testid="stocks-sector-filter"
        >
          <option value="">Alle Sektoren</option>
          {sectors.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      )}

      {!isLoading && (
        <>
          <p className="text-xs text-muted-foreground">
            {filtered.length} von {data?.items.length ?? 0} Aktien
          </p>
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Ticker</th>
                  <th className="px-4 py-2 text-left font-medium">Name</th>
                  <th className="px-4 py-2 text-left font-medium hidden sm:table-cell">Sektor</th>
                  <th className="px-4 py-2 text-right font-medium hidden md:table-cell">Marktkap. (CHF)</th>
                  <th className="px-4 py-2 text-center font-medium hidden sm:table-cell">3a</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filtered.map((stock) => (
                  <tr
                    key={stock.id}
                    className={cn(
                      'hover:bg-muted/30 transition-colors cursor-pointer',
                    )}
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/stocks/${stock.ticker}`}
                        className="flex items-center gap-2 font-mono font-medium hover:underline"
                        data-testid={`stock-row-${stock.ticker}`}
                      >
                        {stock.ticker}
                        {stock.exchange && <SwissBadge exchange={stock.exchange} />}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground max-w-[200px] truncate">
                      {stock.name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground hidden sm:table-cell">
                      {stock.sector ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums hidden md:table-cell">
                      {formatMarketCap(stock.market_cap_chf)}
                    </td>
                    <td className="px-4 py-3 text-center hidden sm:table-cell">
                      {is3aEligible(stock) && (
                        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">3a</Badge>
                      )}
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted-foreground text-sm">
                      Keine Aktien gefunden.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
