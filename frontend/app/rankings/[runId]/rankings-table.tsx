'use client';

import { useState, useMemo } from 'react';
import { ArrowUp, ArrowDown, ArrowUpDown, Download } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { RankingItem } from '@/lib/api/runs';

const MODEL_COLUMNS: Array<{ key: string; label: string }> = [
  { key: 'quality_classic', label: 'Quality' },
  { key: 'diversification', label: 'Diversification' },
  { key: 'trend_momentum', label: 'Trend' },
  { key: 'value_alpha_potential', label: 'Value' },
  { key: 'alpha', label: 'Alpha' },
];

type SortKey = 'total_rank' | 'weighted_avg' | string;
type SortDir = 'asc' | 'desc';

function getSortValue(item: RankingItem, key: SortKey): number {
  if (key === 'total_rank') return item.total_rank ?? Infinity;
  if (key === 'weighted_avg') return item.weighted_avg ?? Infinity;
  return item.per_model_ranks[key] ?? Infinity;
}

function formatNumber(value: number | null, digits = 0): string {
  if (value === null) return '—';
  return digits === 0 ? String(value) : value.toFixed(digits);
}

function exportToCsv(items: RankingItem[]): void {
  const modelKeys = MODEL_COLUMNS.map((c) => c.key);
  const headerRow = [
    'Ticker',
    'Total Rank',
    'Weighted Avg',
    'Sweet Spot',
    ...MODEL_COLUMNS.map((c) => c.label),
  ];
  const dataRows = items.map((item) => [
    item.ticker,
    item.total_rank ?? '',
    item.weighted_avg != null ? item.weighted_avg.toFixed(2) : '',
    item.is_sweet_spot ? 'true' : 'false',
    ...modelKeys.map((k) => item.per_model_ranks[k] ?? ''),
  ]);
  const csv = [headerRow, ...dataRows].map((row) => row.join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'rankings.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

interface SortableHeadProps {
  sortKey: SortKey;
  activeSortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
  children: React.ReactNode;
}

function SortableHead({ sortKey, activeSortKey, sortDir, onSort, children }: SortableHeadProps) {
  const isActive = activeSortKey === sortKey;
  const ariaSort = isActive ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none';
  const Icon = isActive ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;

  return (
    <TableHead
      className="cursor-pointer select-none"
      onClick={() => onSort(sortKey)}
      aria-sort={ariaSort}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        <Icon className={`h-3 w-3 ${isActive ? '' : 'opacity-30'}`} />
      </span>
    </TableHead>
  );
}

export function RankingsTable({ items }: { items: RankingItem[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('total_rank');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [filter, setFilter] = useState('');

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  const displayItems = useMemo(() => {
    const filtered = items.filter((item) =>
      item.ticker.toLowerCase().includes(filter.toLowerCase()),
    );
    return [...filtered].sort((a, b) => {
      const av = getSortValue(a, sortKey);
      const bv = getSortValue(b, sortKey);
      // Nulls (Infinity) always last, regardless of direction
      if (av === Infinity && bv === Infinity) return 0;
      if (av === Infinity) return 1;
      if (bv === Infinity) return -1;
      return sortDir === 'asc' ? av - bv : bv - av;
    });
  }, [items, filter, sortKey, sortDir]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Input
          placeholder="Ticker suchen…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="max-w-xs"
          aria-label="Ticker suchen"
        />
        <Button
          variant="outline"
          size="sm"
          onClick={() => exportToCsv(displayItems)}
          aria-label="CSV exportieren"
        >
          <Download className="mr-1 h-4 w-4" />
          CSV
        </Button>
      </div>

      {displayItems.length === 0 ? (
        <div className="py-12 text-center text-sm text-muted-foreground">Keine Ergebnisse</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <SortableHead
                sortKey="total_rank"
                activeSortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
              >
                #
              </SortableHead>
              <TableHead>Ticker</TableHead>
              <SortableHead
                sortKey="weighted_avg"
                activeSortKey={sortKey}
                sortDir={sortDir}
                onSort={handleSort}
              >
                Avg
              </SortableHead>
              <TableHead>Sweet-Spot</TableHead>
              {MODEL_COLUMNS.map((col) => (
                <SortableHead
                  key={col.key}
                  sortKey={col.key}
                  activeSortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                >
                  {col.label}
                </SortableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayItems.map((item) => (
              <TableRow key={item.ticker}>
                <TableCell>{formatNumber(item.total_rank)}</TableCell>
                <TableCell className="font-mono">{item.ticker}</TableCell>
                <TableCell>{formatNumber(item.weighted_avg, 2)}</TableCell>
                <TableCell>
                  {item.is_sweet_spot ? <Badge variant="default">★</Badge> : null}
                </TableCell>
                {MODEL_COLUMNS.map((col) => (
                  <TableCell key={col.key}>
                    {formatNumber(item.per_model_ranks[col.key] ?? null)}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
