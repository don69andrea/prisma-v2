'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { Download, Search, ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';

import { listStocks, type StockRead } from '@/lib/api/stocks';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { SwissBadge } from '@/components/ui/swiss-badge';
import { cn } from '@/lib/utils';

const MARKET_CAP_3A_THRESHOLD = 100_000_000; // 100M CHF

export function is3aEligible(stock: StockRead): boolean {
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
  { value: '',      label: 'Alle Börsen' },
  { value: 'XSWX', label: 'SIX (Schweiz)' },
];

type SortKey = 'ticker' | 'market_cap' | 'sector';
type SortDir = 'asc' | 'desc';

export function sortStocks(
  items: StockRead[],
  key: SortKey | null,
  dir: SortDir,
): StockRead[] {
  if (!key) return items;
  return [...items].sort((a, b) => {
    let cmp = 0;
    if (key === 'ticker') {
      cmp = a.ticker.localeCompare(b.ticker);
    } else if (key === 'market_cap') {
      const aVal = a.market_cap_chf ? parseFloat(a.market_cap_chf) : 0;
      const bVal = b.market_cap_chf ? parseFloat(b.market_cap_chf) : 0;
      cmp = aVal - bVal;
    } else if (key === 'sector') {
      const aSec = a.sector ?? '';
      const bSec = b.sector ?? '';
      cmp = aSec.localeCompare(bSec);
    }
    return dir === 'asc' ? cmp : -cmp;
  });
}

interface SortableThProps {
  label: string;
  sortKey: SortKey;
  activeSortKey: SortKey | null;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
  className?: string;
  testid?: string;
}

function SortableTh({
  label,
  sortKey,
  activeSortKey,
  sortDir,
  onSort,
  className,
  testid,
}: SortableThProps) {
  const isActive = activeSortKey === sortKey;
  const Icon = isActive ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;
  return (
    <th
      className={cn('px-4 py-2 font-medium select-none', className)}
      data-testid={testid}
    >
      <button
        type="button"
        onClick={() => onSort(sortKey)}
        className="inline-flex items-center gap-1 hover:text-foreground text-left"
        aria-sort={isActive ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
      >
        {label}
        <Icon className={cn('h-3 w-3', isActive ? 'text-foreground' : 'text-muted-foreground')} />
      </button>
    </th>
  );
}

export function StocksListClient() {
  const [search, setSearch] = useState('');
  const [exchange, setExchange] = useState('');
  const [sector, setSector] = useState('');
  const [only3a, setOnly3a] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('asc');

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

  const filteredAndSorted = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    const filtered = data.items.filter((s) => {
      if (q && !s.ticker.toLowerCase().includes(q) && !s.name.toLowerCase().includes(q)) return false;
      if (sector && s.sector !== sector) return false;
      if (only3a && !is3aEligible(s)) return false;
      return true;
    });
    return sortStocks(filtered, sortKey, sortDir);
  }, [data, search, sector, only3a, sortKey, sortDir]);

  function exportCsv() {
    const rows = [
      ['Ticker', 'Name', 'Sektor', 'Marktkap. (CHF)', 'Börse', '3a-geeignet'],
      ...filteredAndSorted.map((s) => [
        s.ticker,
        s.name ?? '',
        s.sector ?? '',
        s.market_cap_chf ? formatMarketCap(s.market_cap_chf) : '',
        s.exchange ?? '',
        is3aEligible(s) ? 'ja' : 'nein',
      ]),
    ];
    const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aktien-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative flex-1 min-w-[200px]">
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
        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input
            type="checkbox"
            checked={only3a}
            onChange={(e) => setOnly3a(e.target.checked)}
            className="rounded"
            data-testid="stocks-3a-filter"
          />
          Nur 3a-geeignet
        </label>
        <button
          onClick={exportCsv}
          disabled={filteredAndSorted.length === 0}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
          data-testid="stocks-csv-export-btn"
        >
          <Download className="h-4 w-4" />
          CSV
        </button>
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
            {filteredAndSorted.length} von {data?.items.length ?? 0} Aktien
          </p>
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <SortableTh
                    label="Ticker"
                    sortKey="ticker"
                    activeSortKey={sortKey}
                    sortDir={sortDir}
                    onSort={handleSort}
                    className="text-left"
                    testid="stocks-sort-ticker"
                  />
                  <th className="px-4 py-2 text-left font-medium">Name</th>
                  <SortableTh
                    label="Sektor"
                    sortKey="sector"
                    activeSortKey={sortKey}
                    sortDir={sortDir}
                    onSort={handleSort}
                    className="text-left hidden sm:table-cell"
                    testid="stocks-sort-sector"
                  />
                  <SortableTh
                    label="Marktkap. (CHF)"
                    sortKey="market_cap"
                    activeSortKey={sortKey}
                    sortDir={sortDir}
                    onSort={handleSort}
                    className="text-right hidden md:table-cell"
                    testid="stocks-sort-marketcap"
                  />
                  <th className="px-4 py-2 text-center font-medium hidden sm:table-cell">3a</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredAndSorted.map((stock) => (
                  <tr
                    key={stock.id}
                    className={cn('hover:bg-muted/30 transition-colors cursor-pointer')}
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
                {filteredAndSorted.length === 0 && (
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
