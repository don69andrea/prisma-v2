'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { ArrowUp, ArrowDown, ArrowUpDown } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import type { StockRead } from '@/lib/api/stocks';

// ---- Types ------------------------------------------------------------------

type SortKey = 'ticker' | 'sector' | null;
type SortDir = 'asc' | 'desc';

interface SortState {
  key: SortKey;
  dir: SortDir;
}

// ---- Helpers ----------------------------------------------------------------

function nextSort(current: SortState, clicked: Exclude<SortKey, null>): SortState {
  if (current.key !== clicked) return { key: clicked, dir: 'asc' };
  if (current.dir === 'asc') return { key: clicked, dir: 'desc' };
  return { key: null, dir: 'asc' };
}

function ariaSortAttr(sort: SortState, key: Exclude<SortKey, null>): 'ascending' | 'descending' | 'none' {
  if (sort.key !== key) return 'none';
  return sort.dir === 'asc' ? 'ascending' : 'descending';
}

function SortIcon({ sort, col }: { sort: SortState; col: Exclude<SortKey, null> }) {
  if (sort.key !== col) return <ArrowUpDown className="ml-1 inline h-3 w-3 opacity-40" />;
  if (sort.dir === 'asc') return <ArrowUp className="ml-1 inline h-3 w-3" />;
  return <ArrowDown className="ml-1 inline h-3 w-3" />;
}

// ---- Component --------------------------------------------------------------

interface StocksListClientProps {
  stocks: StockRead[];
}

export function StocksListClient({ stocks }: StocksListClientProps) {
  const [query, setQuery] = useState('');
  const [only3a, setOnly3a] = useState(false);
  const [sort, setSort] = useState<SortState>({ key: null, dir: 'asc' });

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    let result = stocks.filter((s) => {
      const matchesQuery =
        !q ||
        s.ticker.toLowerCase().includes(q) ||
        s.name.toLowerCase().includes(q);
      const matches3a = !only3a || s.country === 'CH';
      return matchesQuery && matches3a;
    });

    if (sort.key) {
      const key = sort.key;
      result = [...result].sort((a, b) => {
        const av = (a[key] ?? '').toLowerCase();
        const bv = (b[key] ?? '').toLowerCase();
        const cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return sort.dir === 'asc' ? cmp : -cmp;
      });
    }

    return result;
  }, [stocks, query, only3a, sort]);

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <Input
          aria-label="Suche nach Ticker oder Name"
          placeholder="Suche…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="max-w-xs"
        />
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input"
            checked={only3a}
            onChange={(e) => setOnly3a(e.target.checked)}
            aria-label="Nur 3a-geeignete Aktien anzeigen"
          />
          Nur 3a-geeignet
        </label>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead
              aria-sort={ariaSortAttr(sort, 'ticker')}
              className="cursor-pointer select-none"
              onClick={() => setSort(nextSort(sort, 'ticker'))}
            >
              Ticker <SortIcon sort={sort} col="ticker" />
            </TableHead>
            <TableHead>Name</TableHead>
            <TableHead
              aria-sort={ariaSortAttr(sort, 'sector')}
              className="cursor-pointer select-none"
              onClick={() => setSort(nextSort(sort, 'sector'))}
            >
              Sektor <SortIcon sort={sort} col="sector" />
            </TableHead>
            <TableHead>Land</TableHead>
            <TableHead>Währung</TableHead>
            <TableHead>3a</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="py-8 text-center text-muted-foreground">
                Keine Aktien gefunden.
              </TableCell>
            </TableRow>
          ) : (
            filtered.map((stock) => (
              <TableRow key={stock.id}>
                <TableCell className="font-mono font-medium">
                  <Link href={`/stocks/${stock.ticker}`} className="hover:underline">
                    {stock.ticker}
                  </Link>
                </TableCell>
                <TableCell>{stock.name}</TableCell>
                <TableCell>{stock.sector ?? '—'}</TableCell>
                <TableCell>{stock.country ?? '—'}</TableCell>
                <TableCell>{stock.currency}</TableCell>
                <TableCell>
                  {stock.country === 'CH' && (
                    <Badge variant="secondary" className="text-xs">
                      3a
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
