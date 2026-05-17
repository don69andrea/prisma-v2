import { Badge } from '@/components/ui/badge';
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

function formatNumber(value: number | null, digits = 0): string {
  if (value === null) return '—';
  return digits === 0 ? String(value) : value.toFixed(digits);
}

export function RankingsTable({ items }: { items: RankingItem[] }) {
  if (items.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">Keine Ergebnisse</div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>#</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead>Avg</TableHead>
          <TableHead>Sweet-Spot</TableHead>
          {MODEL_COLUMNS.map((col) => (
            <TableHead key={col.key}>{col.label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.ticker}>
            <TableCell>{formatNumber(item.total_rank)}</TableCell>
            <TableCell className="font-mono">{item.ticker}</TableCell>
            <TableCell>{formatNumber(item.weighted_avg, 2)}</TableCell>
            <TableCell>
              {item.is_sweet_spot ? <Badge variant="default">★</Badge> : null}
            </TableCell>
            {MODEL_COLUMNS.map((col) => (
              <TableCell key={col.key}>{formatNumber(item.per_model_ranks[col.key] ?? null)}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
