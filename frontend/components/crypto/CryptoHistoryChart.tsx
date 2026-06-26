'use client';

import { useState } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { useCryptoHistory } from '@/hooks/useCryptoHistory';
import { Skeleton } from '@/components/ui/skeleton';
import type { CryptoHistoryPoint } from '@/lib/api/crypto';

const DAYS_OPTIONS = [7, 30, 90] as const;
type Days = (typeof DAYS_OPTIONS)[number];

interface CryptoHistoryChartProps {
  ticker: string;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('de-CH', { day: '2-digit', month: 'short' });
}

interface TooltipPayloadEntry {
  name: string;
  value: number | null;
  color: string;
}

function ChartTooltip({
  active,
  payload,
  label,
  data,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  data: CryptoHistoryPoint[];
}) {
  if (!active || !payload?.length) return null;
  const point = data.find((d) => d.date === label);
  return (
    <div className="rounded border border-border bg-popover p-2 text-xs shadow">
      <div className="font-medium mb-1">{formatDate(label ?? null)}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value != null ? Number(p.value).toFixed(1) : '—'}
        </div>
      ))}
      {point?.detected_patterns.length ? (
        <div className="mt-1 text-[10px] text-amber-400">
          {point.detected_patterns.join(', ')}
        </div>
      ) : null}
    </div>
  );
}

export function CryptoHistoryChart({ ticker }: CryptoHistoryChartProps) {
  const [days, setDays] = useState<Days>(30);
  const { data, loading } = useCryptoHistory(ticker, days);

  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[100px] w-full" />
      </div>
    );
  }

  const hasEnoughData = data.length >= 2;
  const patternDots = data.filter((d) => d.detected_patterns.length > 0);

  return (
    <div className="space-y-3" data-testid="crypto-history-chart">
      {/* Zeitraum-Selector */}
      <div className="flex gap-1 justify-end">
        {DAYS_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            data-testid={`days-btn-${d}`}
            className={`rounded px-2 py-0.5 text-xs transition-colors ${
              days === d
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {d}T
          </button>
        ))}
      </div>

      {!hasEnoughData ? (
        <p
          className="text-sm text-muted-foreground py-8 text-center"
          data-testid="no-data-placeholder"
        >
          Noch keine ausreichende Historie für diesen Ticker.
        </p>
      ) : (
        <div className="space-y-1">
          {/* Preis + Score */}
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={data} margin={{ top: 4, right: 48, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="price"
                orientation="left"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) =>
                  v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0)
                }
                width={44}
              />
              <YAxis
                yAxisId="score"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip
                content={(props) => (
                  <ChartTooltip
                    active={props.active}
                    payload={props.payload as TooltipPayloadEntry[]}
                    label={props.label as string}
                    data={data}
                  />
                )}
              />
              <Area
                yAxisId="price"
                type="monotone"
                dataKey="price_chf"
                name="Preis CHF"
                stroke="#7ee787"
                fill="#7ee78718"
                strokeWidth={2}
                dot={false}
                connectNulls={false}
              />
              <Line
                yAxisId="score"
                type="monotone"
                dataKey="score"
                name="Score"
                stroke="#58a6ff"
                strokeWidth={1.5}
                strokeDasharray="4 2"
                dot={false}
              />
              {patternDots.map((d, i) => (
                <ReferenceDot
                  key={i}
                  yAxisId="price"
                  x={d.date ?? undefined}
                  y={d.price_chf ?? undefined}
                  r={4}
                  fill="#ffa657"
                  stroke="none"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>

          {/* RSI + Fear & Greed */}
          <ResponsiveContainer width="100%" height={100}>
            <ComposedChart data={data} margin={{ top: 4, right: 48, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" hide />
              <YAxis
                yAxisId="rsi"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <YAxis
                yAxisId="fg"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip
                content={(props) => (
                  <ChartTooltip
                    active={props.active}
                    payload={props.payload as TooltipPayloadEntry[]}
                    label={props.label as string}
                    data={data}
                  />
                )}
              />
              <ReferenceLine
                yAxisId="rsi"
                y={70}
                stroke="#f85149"
                strokeDasharray="3 3"
                strokeOpacity={0.6}
              />
              <ReferenceLine
                yAxisId="rsi"
                y={30}
                stroke="#7ee787"
                strokeDasharray="3 3"
                strokeOpacity={0.6}
              />
              <Line
                yAxisId="rsi"
                type="monotone"
                dataKey="rsi_14"
                name="RSI"
                stroke="#bc8cff"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
              <Line
                yAxisId="fg"
                type="monotone"
                dataKey="fear_greed_value"
                name="Fear & Greed"
                stroke="#ffa657"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
            </ComposedChart>
          </ResponsiveContainer>

          {/* Legende */}
          <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
            <span><span className="text-[#7ee787]">—</span> Preis CHF</span>
            <span><span className="text-[#58a6ff]">- -</span> Score</span>
            <span><span className="text-[#bc8cff]">—</span> RSI</span>
            <span><span className="text-[#ffa657]">—</span> Fear &amp; Greed</span>
            <span><span className="text-[#ffa657]">●</span> Pattern erkannt</span>
          </div>
        </div>
      )}
    </div>
  );
}
