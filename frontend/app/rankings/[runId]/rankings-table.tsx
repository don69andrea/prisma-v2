'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { ArrowUp, ArrowDown, ArrowUpDown, Download } from 'lucide-react';

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
import { ROUTES } from '@/lib/routes';
import type { RankingItem } from '@/lib/api/runs';
import { InfoPopover } from '@/components/InfoPopover';
import { ModelInfoIcon } from '@/components/ModelInfoIcon';
import { MODEL_INFO, SWEET_SPOT_DEFINITION, getSweetSpotModels, type ModelKey } from '@/lib/model-info';
import { MemoSheet } from '@/components/factsheet/MemoSheet';
import { SwissBadge } from '@/components/ui/swiss-badge';

const MODEL_COLUMNS: Array<{ key: ModelKey; label: string }> = [
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
  infoIcon?: React.ReactNode;
  children: React.ReactNode;
}

function SortableHead({ sortKey, activeSortKey, sortDir, onSort, infoIcon, children }: SortableHeadProps) {
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
        {infoIcon}
        <Icon className={`h-3 w-3 ${isActive ? '' : 'opacity-30'}`} />
      </span>
    </TableHead>
  );
}

function SweetSpotBadge({
  ticker,
  perModelRanks,
  totalStocks,
}: {
  ticker: string;
  perModelRanks: Record<string, number | null>;
  totalStocks: number;
}) {
  const sweetSpotKeys = getSweetSpotModels(perModelRanks, totalStocks);
  const labels = sweetSpotKeys.map((k) => MODEL_INFO[k].label).join(', ');
  const count = sweetSpotKeys.length;

  return (
    <InfoPopover ariaLabel={`Sweet-Spot-Begründung für ${ticker}`}>
      <p>
        <strong>{ticker}</strong> ist Top-25 % in {labels} ({count}/5 Modellen).
      </p>
    </InfoPopover>
  );
}

interface RankingsTableProps {
  items: RankingItem[];
  runId: string;
  swissTickers?: Set<string>;  // optional — no filter shown if undefined
}

export function RankingsTable({ items, runId, swissTickers }: RankingsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('total_rank');
  const [sortDir, setSortDir] = useState<SortDir>('asc');
  const [filter, setFilter] = useState('');
  const [exchangeFilter, setExchangeFilter] = useState<'all' | 'xswx'>('all');
  const [selectedStock, setSelectedStock] = useState<{ stockId: string; ticker: string } | null>(null);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  const displayItems = useMemo(() => {
    let result = items;
    if (exchangeFilter === 'xswx' && swissTickers) {
      result = result.filter((item) => swissTickers.has(item.ticker));
    }
    const filtered = result.filter((item) =>
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
  }, [items, filter, sortKey, sortDir, exchangeFilter, swissTickers]);

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
        {swissTickers !== undefined && (
          <div className="flex gap-1 ml-auto">
            <Button
              variant={exchangeFilter === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setExchangeFilter('all')}
            >
              Alle
            </Button>
            <Button
              variant={exchangeFilter === 'xswx' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setExchangeFilter('xswx')}
            >
              🇨🇭 XSWX
            </Button>
          </div>
        )}
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
              <TableHead>
                <span className="inline-flex items-center gap-1">
                  Sweet-Spot
                  <InfoPopover ariaLabel="Sweet-Spot-Definition">
                    <p>{SWEET_SPOT_DEFINITION}</p>
                  </InfoPopover>
                </span>
              </TableHead>
              {MODEL_COLUMNS.map((col) => (
                <SortableHead
                  key={col.key}
                  sortKey={col.key}
                  activeSortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                  infoIcon={<ModelInfoIcon modelKey={col.key} />}
                >
                  {col.label}
                </SortableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayItems.map((item) => (
              <TableRow
                key={item.ticker}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => {
                  if (item.stock_id) {
                    setSelectedStock({ stockId: item.stock_id, ticker: item.ticker });
                  }
                }}
              >
                <TableCell>
                  <Link
                    href={ROUTES.factsheet(runId, item.ticker)}
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1.5"
                  >
                    {item.total_rank === 1 && (
                      <span className="text-[10px] font-bold text-amber-500" data-testid="rank-medal-1">🥇</span>
                    )}
                    {item.total_rank === 2 && (
                      <span className="text-[10px] font-bold text-slate-400" data-testid="rank-medal-2">🥈</span>
                    )}
                    {item.total_rank === 3 && (
                      <span className="text-[10px] font-bold text-orange-400" data-testid="rank-medal-3">🥉</span>
                    )}
                    <span className={
                      item.total_rank === 1 ? 'text-amber-600 font-bold dark:text-amber-400' :
                      item.total_rank === 2 ? 'text-slate-500 font-semibold dark:text-slate-300' :
                      item.total_rank === 3 ? 'text-orange-500 font-semibold dark:text-orange-400' : ''
                    }>
                      {formatNumber(item.total_rank)}
                    </span>
                  </Link>
                </TableCell>
                <TableCell className="font-mono">
                  <div className="flex items-center gap-1.5">
                    <Link href={ROUTES.factsheet(runId, item.ticker)} onClick={(e) => e.stopPropagation()} className="hover:underline">
                      {item.ticker}
                    </Link>
                    {swissTickers?.has(item.ticker) && <SwissBadge exchange="XSWX" />}
                  </div>
                </TableCell>
                <TableCell>{formatNumber(item.weighted_avg, 2)}</TableCell>
                <TableCell>
                  {item.is_sweet_spot ? (
                    <span onClick={(e) => e.stopPropagation()}>
                      <SweetSpotBadge ticker={item.ticker} perModelRanks={item.per_model_ranks} totalStocks={items.length} />
                    </span>
                  ) : null}
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

      <MemoSheet
        stockId={selectedStock?.stockId ?? null}
        runId={runId}
        ticker={selectedStock?.ticker ?? ''}
        open={selectedStock !== null}
        onOpenChange={(o) => {
          if (!o) setSelectedStock(null);
        }}
      />
    </div>
  );
}
