'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

export interface AuditTrailProps {
  quantScore: number;
  mlScore: number;
  macroScore: number;
  signal: 'BUY' | 'HOLD' | 'SELL';
  snapshotDate?: string;
  className?: string;
}

const ROWS = [
  { key: 'quant',  label: 'Quant-Score',   weight: 0.45, color: 'bg-[#58a6ff]',  glow: 'rgba(88,166,255,0.35)' },
  { key: 'ml',     label: 'ML-Prediction', weight: 0.35, color: 'bg-[#bc8cff]',  glow: 'rgba(188,140,255,0.35)' },
  { key: 'macro',  label: 'Makro-Kontext', weight: 0.20, color: 'bg-[#7ee787]',  glow: 'rgba(126,231,135,0.35)' },
] as const;

const SIGNAL_RANGE: Record<string, string> = {
  BUY:  '≥ 65',
  HOLD: '40–64',
  SELL: '< 40',
};

export function AuditTrail({
  quantScore,
  mlScore,
  macroScore,
  signal,
  snapshotDate,
  className,
}: AuditTrailProps) {
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 30);
    return () => clearTimeout(t);
  }, []);

  const scores: Record<typeof ROWS[number]['key'], number> = {
    quant: quantScore,
    ml: mlScore,
    macro: macroScore,
  };

  const total = ROWS.reduce((sum, r) => sum + scores[r.key] * r.weight, 0);

  return (
    <div
      className={cn('space-y-2 text-[11px]', className)}
      data-testid="audit-trail"
    >
      <p className="text-[10px] text-[#8b949e] font-semibold uppercase tracking-[0.1em]">
        Signal-Herleitung
      </p>

      {ROWS.map((row, i) => {
        const score = scores[row.key];
        const contribution = score * row.weight;
        const barPct = Math.min(Math.max(score, 0), 100);

        return (
          <div key={row.key} className="flex items-center gap-2" style={{ animationDelay: `${i * 60}ms` }}>
            <span className="text-[#8b949e] w-28 shrink-0">{row.label}</span>

            {/* animated bar */}
            <div
              className="flex-1 h-1.5 rounded-full bg-[#21262d] overflow-hidden"
              role="progressbar"
              aria-valuenow={score}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className={cn('h-full rounded-full transition-all duration-700 ease-out', row.color)}
                style={{
                  width: animated ? `${barPct}%` : '0%',
                  boxShadow: animated ? `0 0 6px ${row.glow}` : 'none',
                }}
              />
            </div>

            <span className="text-[#e6edf3] w-7 text-right tabular-nums">{score.toFixed(0)}</span>
            <span className="text-[#8b949e] w-8 text-center">×{row.weight.toFixed(2)}</span>
            <span className="text-[#bc8cff] w-7 text-right tabular-nums font-medium">
              {contribution.toFixed(1)}
            </span>
          </div>
        );
      })}

      {/* Gesamt-Score */}
      <div className="flex items-center justify-between pt-2 border-t border-[#21262d] font-semibold">
        <span className="text-[#8b949e]">Gesamt</span>
        <span className="text-[#e6edf3] tabular-nums">
          {total.toFixed(1)}
          <span className="text-[#8b949e] font-normal ml-1.5">
            → {signal} ({SIGNAL_RANGE[signal] ?? '—'})
          </span>
        </span>
      </div>

      {/* Metadata */}
      <div className="flex justify-between text-[10px] text-[#8b949e] pt-0.5" data-testid="audit-metadata">
        <span>Modell v1 · Quant×0.45 + ML×0.35 + Makro×0.20</span>
        {snapshotDate && (
          <span>
            {new Date(snapshotDate).toLocaleDateString('de-CH', { dateStyle: 'short' })}
          </span>
        )}
      </div>
    </div>
  );
}
