'use client';

import { fearGreedColor, fearGreedLabel } from '@/lib/api/crypto';
import { cn } from '@/lib/utils';

interface FearGreedGaugeProps {
  value: number;
  label: string;
  className?: string;
}

export function FearGreedGauge({ value, label, className }: FearGreedGaugeProps) {
  const color = fearGreedColor(value);
  const germanLabel = fearGreedLabel(value);
  const pct = Math.min(100, Math.max(0, value));

  const rotation = pct * 1.8 - 90;

  return (
    <div className={cn('flex flex-col items-center gap-2', className)}>
      <div className="relative w-40 h-20 overflow-hidden">
        <div
          className="absolute inset-0 rounded-t-full"
          style={{
            background: 'conic-gradient(from 180deg at 50% 100%, #7ee787 0deg, #ffa657 90deg, #f85149 180deg)',
            opacity: 0.25,
          }}
        />
        <div
          className="absolute bottom-0 left-1/2 w-0.5 h-16 origin-bottom rounded-full transition-transform duration-700"
          style={{
            backgroundColor: color,
            transform: `translateX(-50%) rotate(${rotation}deg)`,
          }}
        />
        <div
          className="absolute bottom-0 left-1/2 w-3 h-3 rounded-full -translate-x-1/2 translate-y-1/2"
          style={{ backgroundColor: color }}
        />
      </div>
      <div className="text-center">
        <div className="text-2xl font-black tabular-nums" style={{ color }}>
          {value}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">{germanLabel}</div>
      </div>
    </div>
  );
}
