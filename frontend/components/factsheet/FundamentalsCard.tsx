'use client';

import { BarChart2 } from 'lucide-react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { FundamentalsData } from '@/lib/api/fundamentals';

function fmt(value: number | null, digits = 2): string {
  return value != null ? value.toFixed(digits) : '—';
}

interface Props {
  data: FundamentalsData;
}

export function FundamentalsCard({ data }: Props) {
  const { pe_ratio, pb_ratio, eps_chf, dividend_yield_pct, disclaimer } = data;

  const rows: Array<{ label: string; value: string; testid: string }> = [
    { label: 'KGV (P/E)',         value: fmt(pe_ratio),            testid: 'fund-pe' },
    { label: 'KBV (P/B)',         value: fmt(pb_ratio),            testid: 'fund-pb' },
    { label: 'EPS (CHF)',         value: fmt(eps_chf, 4),          testid: 'fund-eps' },
    { label: 'Dividendenrendite', value: dividend_yield_pct != null ? `${dividend_yield_pct.toFixed(1)} %` : '—', testid: 'fund-yield' },
  ];

  return (
    <Card data-testid="fundamentals-card">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Bewertungskennzahlen</CardTitle>
        </div>
        <CardDescription className="text-xs">Yahoo Finance — Trailing 12 Months</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          {rows.map(({ label, value, testid }) => (
            <>
              <dt key={`${testid}-dt`} className="text-muted-foreground">{label}</dt>
              <dd key={`${testid}-dd`} className="font-medium tabular-nums" data-testid={testid}>{value}</dd>
            </>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">{disclaimer}</p>
      </CardContent>
    </Card>
  );
}
