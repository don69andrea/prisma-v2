'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { FundamentalsRead } from '@/lib/api/fundamentals';

function fmt(value: number | null, digits = 2, suffix = ''): string {
  if (value === null) return '—';
  return `${value.toFixed(digits)}${suffix}`;
}

const ROWS: Array<{ label: string; key: keyof FundamentalsRead; format: (v: number | null) => string }> = [
  { label: 'KGV (P/E)', key: 'pe_ratio', format: (v) => fmt(v, 1, '×') },
  { label: 'KBV (P/B)', key: 'pb_ratio', format: (v) => fmt(v, 1, '×') },
  { label: 'FCF-Rendite', key: 'fcf_yield', format: (v) => fmt(v !== null ? v * 100 : null, 1, '%') },
  { label: 'Operating Margin', key: 'operating_margin', format: (v) => fmt(v !== null ? v * 100 : null, 1, '%') },
  { label: 'Dividendenrendite', key: 'dividend_yield', format: (v) => fmt(v !== null ? v * 100 : null, 2, '%') },
];

interface FundamentalsCardProps {
  data: FundamentalsRead;
}

export function FundamentalsCard({ data }: FundamentalsCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">Fundamentaldaten</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          {ROWS.map(({ label, key, format }) => (
            <>
              <dt key={`dt-${key}`} className="text-muted-foreground">
                {label}
              </dt>
              <dd key={`dd-${key}`} className="font-mono font-medium tabular-nums">
                {format(data[key] as number | null)}
              </dd>
            </>
          ))}
        </dl>
        <p className="text-xs text-muted-foreground border-t pt-2">{data.disclaimer}</p>
      </CardContent>
    </Card>
  );
}
