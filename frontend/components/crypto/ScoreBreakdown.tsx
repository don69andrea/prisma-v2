'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { type CryptoSignal } from '@/lib/api/crypto';

const COMPONENT_LABELS: Record<string, { label: string; max: number; color: string }> = {
  momentum: { label: 'Momentum',  max: 30, color: '#58a6ff' },
  trend:    { label: 'Trend',     max: 25, color: '#3fb950' },
  sentiment:{ label: 'Sentiment', max: 20, color: '#ffa657' },
  markt:    { label: 'Markt',     max: 15, color: '#bc8cff' },
  risiko:   { label: 'Risiko',    max: 10, color: '#79c0ff' },
};

interface ScoreBreakdownProps {
  signal: CryptoSignal;
}

export function ScoreBreakdown({ signal }: ScoreBreakdownProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded border border-border/40 overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-muted-foreground hover:bg-muted/30 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span>Score-Aufschlüsselung</span>
        {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
      </button>
      {open && (
        <div className="px-3 pb-3 pt-1 flex flex-col gap-2">
          {Object.entries(COMPONENT_LABELS).map(([key, { label, max, color }]) => {
            const val = signal.score_components[key as keyof typeof signal.score_components] ?? 0;
            const pct = Math.round((val / max) * 100);
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="text-[10px] text-muted-foreground w-16 shrink-0">{label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-[#21262d] overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                  />
                </div>
                <span className="text-[10px] tabular-nums text-muted-foreground w-10 text-right">
                  {val}/{max}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
