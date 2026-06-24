'use client';

import { useState } from 'react';
import {
  ComposedChart, Bar, Line, CartesianGrid, XAxis, YAxis,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { OHLCVBar } from '@/lib/api/ohlcv';

type Indicator = 'MA20' | 'MA50' | 'Bollinger';

interface Props {
  bars: OHLCVBar[];
  coin: string;
}

function computeMA(bars: OHLCVBar[], period: number): (number | null)[] {
  return bars.map((_, i) => {
    if (i < period - 1) return null;
    const slice = bars.slice(i - period + 1, i + 1);
    return slice.reduce((s, b) => s + b.close, 0) / period;
  });
}

function computeBollingerBands(
  bars: OHLCVBar[],
  period = 20,
): { upper: number | null; lower: number | null }[] {
  return bars.map((_, i) => {
    if (i < period - 1) return { upper: null, lower: null };
    const slice = bars.slice(i - period + 1, i + 1);
    const mean = slice.reduce((s, b) => s + b.close, 0) / period;
    const variance = slice.reduce((s, b) => s + (b.close - mean) ** 2, 0) / period;
    const std = Math.sqrt(variance);
    return { upper: mean + 2 * std, lower: mean - 2 * std };
  });
}

interface CustomBarShapeProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: {
    bullish: boolean;
  };
}

function CandleBodyShape(props: CustomBarShapeProps) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props;
  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={Math.max(1, height)}
      fill={payload?.bullish ? '#22c55e' : '#ef4444'}
    />
  );
}

export function CandlestickChart({ bars, coin }: Props) {
  const [indicators, setIndicators] = useState<Set<Indicator>>(new Set(['MA20', 'MA50']));

  const ma20 = computeMA(bars, 20);
  const ma50 = computeMA(bars, 50);
  const bb = computeBollingerBands(bars);

  // Build chart data — OHLCV as high-low bar range
  const data = bars.map((b, i) => ({
    date: b.date,
    low: b.low,
    high: b.high,
    open: b.open,
    close: b.close,
    // Candlestick approximation: range bar = [low, high], body bar = [min(open,close), max(open,close)]
    range: [b.low, b.high] as [number, number],
    body: [Math.min(b.open, b.close), Math.max(b.open, b.close)] as [number, number],
    bullish: b.close >= b.open,
    ma20: ma20[i],
    ma50: ma50[i],
    bbUpper: bb[i].upper,
    bbLower: bb[i].lower,
  }));

  const toggleIndicator = (ind: Indicator) => {
    setIndicators(prev => {
      const next = new Set(prev);
      if (next.has(ind)) next.delete(ind);
      else next.add(ind);
      return next;
    });
  };

  const indicatorList: Indicator[] = ['MA20', 'MA50', 'Bollinger'];

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{coin} — Preis &amp; Indikatoren</CardTitle>
        <div className="flex flex-wrap gap-2 mt-1">
          {indicatorList.map(ind => (
            <button
              key={ind}
              onClick={() => toggleIndicator(ind)}
              className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                indicators.has(ind)
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-muted-foreground/30 text-muted-foreground'
              }`}
            >
              {ind}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 9 }}
              tickLine={false}
              tickFormatter={(v: string) => v.slice(5)}
            />
            <YAxis
              tick={{ fontSize: 9 }}
              tickLine={false}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) =>
                v > 999 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0)
              }
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-background border rounded p-2 text-xs shadow">
                    <div className="font-semibold">{d.date}</div>
                    <div>O: {(d.open as number)?.toFixed(2)} H: {(d.high as number)?.toFixed(2)}</div>
                    <div>L: {(d.low as number)?.toFixed(2)} C: {(d.close as number)?.toFixed(2)}</div>
                  </div>
                );
              }}
            />
            {/* High-Low wick */}
            <Bar dataKey="range" fill="transparent" stroke="#94a3b8" barSize={1} />
            {/* Open-Close body — bullish=green, bearish=red */}
            <Bar
              dataKey="body"
              fill="#94a3b8"
              stroke="none"
              barSize={6}
              shape={<CandleBodyShape />}
            />
            {indicators.has('MA20') && (
              <Line
                type="monotone"
                dataKey="ma20"
                name="MA20"
                stroke="#3b82f6"
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            )}
            {indicators.has('MA50') && (
              <Line
                type="monotone"
                dataKey="ma50"
                name="MA50"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            )}
            {indicators.has('Bollinger') && (
              <>
                <Line
                  type="monotone"
                  dataKey="bbUpper"
                  name="BB Upper"
                  stroke="#a78bfa"
                  strokeWidth={1}
                  dot={false}
                  strokeDasharray="3 2"
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="bbLower"
                  name="BB Lower"
                  stroke="#a78bfa"
                  strokeWidth={1}
                  dot={false}
                  strokeDasharray="3 2"
                  connectNulls
                />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
