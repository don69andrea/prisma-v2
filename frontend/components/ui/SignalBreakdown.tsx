'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

export interface SignalBreakdownProps {
  quantScore?: number;   // 0-100
  mlScore?: number;      // 0-100
  macroScore?: number;   // 0-100
  finalScore?: number;   // weighted_score 0-100
  signal: 'BUY' | 'HOLD' | 'WATCH';
  className?: string;
}

const COMPONENTS = [
  {
    label: 'Quant',
    weight: 45,
    scoreKey: 'quantScore' as const,
    color: '#58a6ff',
    barClass: 'bg-[#58a6ff]',
    glow: 'rgba(88,166,255,0.4)',
  },
  {
    label: 'ML',
    weight: 35,
    scoreKey: 'mlScore' as const,
    color: '#bc8cff',
    barClass: 'bg-[#bc8cff]',
    glow: 'rgba(188,140,255,0.4)',
  },
  {
    label: 'Makro',
    weight: 20,
    scoreKey: 'macroScore' as const,
    color: '#7ee787',
    barClass: 'bg-[#7ee787]',
    glow: 'rgba(126,231,135,0.4)',
  },
] as const;

const SIGNAL_CONFIG = {
  BUY:   { color: '#7ee787', label: 'BUY',   threshold: '≥ 70' },
  HOLD:  { color: '#ffa657', label: 'HOLD',  threshold: '40–69' },
  WATCH: { color: '#8b949e', label: 'WATCH', threshold: '< 40' },
} as const;

export function SignalBreakdown({
  quantScore,
  mlScore,
  macroScore,
  finalScore,
  signal,
  className,
}: SignalBreakdownProps) {
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 40);
    return () => clearTimeout(t);
  }, []);

  const scores = { quantScore, mlScore, macroScore } as const;
  const cfg = SIGNAL_CONFIG[signal];

  return (
    <div
      className={cn(
        'rounded-xl border border-[#21262d] bg-[#0d1117]/60 p-3 space-y-2.5',
        className,
      )}
      data-testid="signal-breakdown"
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#8b949e]">
          Signal-Zusammensetzung
        </p>
        <span
          className="text-[11px] font-bold tabular-nums rounded-full px-2 py-0.5"
          style={{
            color: cfg.color,
            background: `${cfg.color}18`,
            border: `1px solid ${cfg.color}40`,
          }}
        >
          {cfg.label}
        </span>
      </div>

      {/* Component bars */}
      {COMPONENTS.map(({ label, weight, scoreKey, barClass, glow }, i) => {
        const score = scores[scoreKey];
        const barPct = score != null ? Math.min(Math.max(score, 0), 100) : 0;

        return (
          <div key={label} className="space-y-1">
            <div className="flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-1.5">
                <span className="font-medium text-[#e6edf3]">{label}</span>
                <span className="text-[#8b949e]">{weight}%</span>
              </div>
              <span className="tabular-nums text-[#8b949e]">
                {score != null ? `${score.toFixed(1)} Pkt` : '—'}
              </span>
            </div>
            <div
              className="h-1.5 w-full rounded-full bg-[#21262d] overflow-hidden"
              role="progressbar"
              aria-valuenow={score ?? 0}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`${label}-Score`}
              style={{ animationDelay: `${i * 60}ms` }}
            >
              <div
                className={cn('h-full rounded-full transition-all duration-700 ease-out', barClass)}
                style={{
                  width: animated ? `${barPct}%` : '0%',
                  boxShadow: animated && score != null ? `0 0 5px ${glow}` : 'none',
                }}
              />
            </div>
          </div>
        );
      })}

      {/* Weighted total */}
      {finalScore != null && (
        <div className="flex items-center justify-between pt-2 border-t border-[#21262d] text-[11px]">
          <span className="text-[#8b949e]">Gesamt-Score</span>
          <span className="font-semibold text-[#e6edf3] tabular-nums">
            {finalScore.toFixed(1)}
            <span className="text-[#8b949e] font-normal ml-1">/ 100</span>
          </span>
        </div>
      )}

      {/* Threshold legend */}
      <p className="text-[9px] text-[#8b949e]/60 leading-tight">
        BUY ≥ 70 · HOLD 40–69 · WATCH &lt; 40 · Quant×0.45 + ML×0.35 + Makro×0.20
      </p>
    </div>
  );
}
