'use client';

import type { SHAPEntry, MLSignal } from '@/lib/api/ml';

interface Props {
  shapValues: SHAPEntry[];
  signal: MLSignal;
  topN?: number;
}

function toDecisionSignal(signal: MLSignal): string {
  const map: Record<MLSignal, string> = {
    OUTPERFORM: 'OUTPERFORM',
    NEUTRAL: 'NEUTRAL',
    UNDERPERFORM: 'UNDERPERFORM',
  };
  return map[signal];
}

export function SHAPMiniBreakdown({ shapValues, signal, topN = 3 }: Props) {
  if (!shapValues.length) return null;

  const sorted = [...shapValues].sort(
    (a, b) => Math.abs(b.shap_value) - Math.abs(a.shap_value),
  );
  const top = sorted.slice(0, topN);
  const maxAbs = Math.max(...top.map((e) => Math.abs(e.shap_value)), 0.01);

  const headerColor =
    signal === 'OUTPERFORM'
      ? '#a855f7'
      : signal === 'UNDERPERFORM'
      ? '#f85149'
      : '#8b949e';

  return (
    <div className="rounded-lg border border-purple-500/15 bg-[#0d1117]/50 px-3 py-2.5 space-y-2">
      <p
        className="text-[10px] font-semibold uppercase tracking-[0.1em]"
        style={{ color: headerColor }}
      >
        ML-Treiber · {toDecisionSignal(signal)}
      </p>

      <div className="space-y-1.5">
        {top.map((entry) => {
          const isPos = entry.shap_value >= 0;
          const barPct = (Math.abs(entry.shap_value) / maxAbs) * 100;

          return (
            <div key={entry.feature} className="flex items-center gap-2">
              <span className="w-28 shrink-0 text-[10px] text-[#8b949e] truncate text-right leading-tight">
                {entry.label}
              </span>
              <div className="flex-1 h-2 rounded-full bg-[#21262d] overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${barPct}%`,
                    background: isPos
                      ? 'linear-gradient(90deg, #00cc6688, #00ff88)'
                      : 'linear-gradient(90deg, #ff446688, #ff4466)',
                  }}
                />
              </div>
              <span
                className="w-12 shrink-0 text-[10px] tabular-nums font-medium text-right"
                style={{ color: isPos ? '#7ee787' : '#f85149' }}
              >
                {isPos ? '+' : ''}
                {entry.shap_value.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
