import { ArrowDown, ArrowUp, Minus } from 'lucide-react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { CompareRow } from '@/lib/compare';

interface Props {
  rows: CompareRow[];
}

function formatDeltaRank(delta: number): {
  text: string;
  className: string;
  icon: React.ReactNode;
} {
  if (delta > 0) {
    return {
      text: `+${delta}`,
      className: 'text-green-600 dark:text-green-400',
      icon: <ArrowUp className="inline h-3 w-3" />,
    };
  }
  if (delta < 0) {
    return {
      text: `${delta}`,
      className: 'text-red-600 dark:text-red-400',
      icon: <ArrowDown className="inline h-3 w-3" />,
    };
  }
  return {
    text: '0',
    className: 'text-muted-foreground',
    icon: <Minus className="inline h-3 w-3" />,
  };
}

function formatDeltaScore(delta: number): { text: string; className: string } {
  const sign = delta > 0 ? '+' : '';
  const formatted = `${sign}${delta.toFixed(2)}`;
  if (delta > 0) return { text: formatted, className: 'text-green-600 dark:text-green-400' };
  if (delta < 0) return { text: formatted, className: 'text-red-600 dark:text-red-400' };
  return { text: '0.00', className: 'text-muted-foreground' };
}

export function CompareTable({ rows }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Rank A</TableHead>
          <TableHead className="text-right">Rank B</TableHead>
          <TableHead className="text-right">Δ Rank</TableHead>
          <TableHead className="text-right">Δ Score</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const dr = formatDeltaRank(r.deltaRank);
          const ds = formatDeltaScore(r.deltaScore);
          return (
            <TableRow key={r.ticker}>
              <TableCell className="font-medium">{r.ticker}</TableCell>
              <TableCell className="text-right tabular-nums">{r.rankA}</TableCell>
              <TableCell className="text-right tabular-nums">{r.rankB}</TableCell>
              <TableCell
                data-testid="delta-rank-cell"
                className={`text-right tabular-nums ${dr.className}`}
              >
                <span className="inline-flex items-center gap-1">
                  {dr.icon}
                  {dr.text}
                </span>
              </TableCell>
              <TableCell
                data-testid="delta-score-cell"
                className={`text-right tabular-nums ${ds.className}`}
              >
                {ds.text}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
