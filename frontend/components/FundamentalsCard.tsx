'use client';

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { FundamentalsData } from '@/lib/api/fundamentals';

function fmt(value: number | null, digits = 2, suffix = ''): string {
  if (value === null) return '—';
  return `${value.toFixed(digits)}${suffix}`;
}

const ROWS: Array<{ label: string; key: keyof FundamentalsData; format: (v: number | null) => string }> = [
  { label: 'KGV (P/E)', key: 'pe_ratio', format: (v) => fmt(v, 1, '×') },
  { label: 'KBV (P/B)', key: 'pb_ratio', format: (v) => fmt(v, 1, '×') },
  { label: 'Gewinn je Aktie (CHF)', key: 'eps_chf', format: (v) => fmt(v, 2, ' CHF') },
  { label: 'Dividendenrendite', key: 'dividend_yield_pct', format: (v) => fmt(v, 2, '%') },
];

interface FundamentalsCardProps {
  data: FundamentalsData;
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
            <React.Fragment key={key}>
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-mono font-medium tabular-nums">
                {format(data[key] as number | null)}
              </dd>
            </React.Fragment>
          ))}
        </dl>
        <p className="text-xs text-muted-foreground border-t pt-2">{data.disclaimer}</p>
      </CardContent>
    </Card>
  );
}
