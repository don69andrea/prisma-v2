'use client';

import { type CryptoHistoryPoint } from '@/lib/api/crypto';
import { signalColor } from '@/lib/api/crypto';

interface SignalSparklineProps {
  data: CryptoHistoryPoint[];
  width?: number;
  height?: number;
}

export function SignalSparkline({ data, width = 90, height = 28 }: SignalSparklineProps) {
  if (!data || data.length < 2) {
    return <span className="text-[10px] text-muted-foreground">Noch keine Historie</span>;
  }

  const scores = data.map((d) => d.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1;

  const points = data
    .map((d, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((d.score - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(' ');

  const last = data[data.length - 1];
  const first = data[0];
  const trendUp = last.score >= first.score;
  const color = signalColor(last.signal as Parameters<typeof signalColor>[0]) ?? '#94a3b8';

  return (
    <div className="flex items-center gap-1.5">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
        <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-[10px] tabular-nums" style={{ color }}>
        {trendUp ? '↑' : '↓'} {last.score.toFixed(0)}
      </span>
    </div>
  );
}
