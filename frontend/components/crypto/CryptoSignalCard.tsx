'use client';

import { type CryptoSignal, signalColor, signalLabel } from '@/lib/api/crypto';
import { cn } from '@/lib/utils';

interface CryptoSignalCardProps {
  signal: CryptoSignal;
}

export function CryptoSignalCard({ signal }: CryptoSignalCardProps) {
  const color = signalColor(signal.signal);
  const label = signalLabel(signal.signal);
  const pct = Math.round(signal.score);

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-bold text-base">{signal.name}</div>
          <div className="text-xs text-muted-foreground">{signal.ticker}</div>
        </div>
        <div className="flex flex-col items-center shrink-0">
          <div
            className="text-xl font-black tabular-nums"
            style={{ color }}
          >
            {pct}
          </div>
          <div className="text-[10px] text-muted-foreground">/100</div>
        </div>
      </div>

      <div className="h-1.5 w-full rounded-full bg-[#21262d] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>

      <div className="flex items-center gap-2">
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full border"
          style={{
            color,
            borderColor: color + '50',
            backgroundColor: color + '20',
          }}
        >
          {label}
        </span>
        {signal.has_six_etp && (
          <span className="text-[10px] text-[#8b949e] border border-[#30363d] rounded px-1.5 py-0.5">
            SIX ETP
          </span>
        )}
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed">
        {signal.signal_reason_de}
      </p>
    </div>
  );
}
