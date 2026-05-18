'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { PricePoint } from '@/lib/api/stocks';

interface Props {
  ticker: string;
  prices: PricePoint[];
}

function formatDateShort(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('de-CH', { month: 'short', year: '2-digit' });
}

function formatPrice(value: number): string {
  return value.toFixed(2);
}

function buildTickFormatter(prices: PricePoint[]) {
  const step = Math.max(1, Math.floor(prices.length / 6));
  const tickSet = new Set(prices.filter((_, i) => i % step === 0).map((p) => p.date));
  return (date: string) => (tickSet.has(date) ? formatDateShort(date) : '');
}

export function PriceChart({ ticker, prices }: Props) {
  if (prices.length === 0) return null;

  const tickFormatter = buildTickFormatter(prices);
  const minClose = Math.min(...prices.map((p) => p.close));
  const maxClose = Math.max(...prices.map((p) => p.close));
  const padding = (maxClose - minClose) * 0.05;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">
          Kursentwicklung — {ticker} (1 Jahr)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={prices} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tickFormatter={tickFormatter}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={[minClose - padding, maxClose + padding]}
              tickFormatter={formatPrice}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              formatter={(value: number) => [formatPrice(value), 'Kurs']}
              labelFormatter={(label: string) =>
                new Date(label).toLocaleDateString('de-CH', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })
              }
            />
            <Line
              type="monotone"
              dataKey="close"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
