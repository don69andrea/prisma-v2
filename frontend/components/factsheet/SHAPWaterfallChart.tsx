'use client';

import { useEffect, useRef, useState } from 'react';
import type { SHAPEntry } from '@/lib/api/ml';

interface Props {
  shapValues: SHAPEntry[];
  expectedValue: number;
  signal: 'OUTPERFORM' | 'NEUTRAL' | 'UNDERPERFORM';
}

export function SHAPWaterfallChart({ shapValues, expectedValue, signal }: Props) {
  const barsRef = useRef<(HTMLDivElement | null)[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const [maxBarWidth, setMaxBarWidth] = useState(180);

  // Responsive: containerWidth messen und maxBarWidth anpassen
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      // Bars dürfen maximal 60% der Container-Breite einnehmen (Rest für Label + Wert)
      setMaxBarWidth(Math.max(40, Math.min(180, Math.round(width * 0.45))));
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    barsRef.current.forEach((bar, i) => {
      if (!bar) return;
      bar.style.width = '0px';
      bar.style.transition = `width 600ms ease-out ${i * 60}ms`;
      requestAnimationFrame(() => {
        const target = bar.dataset.targetWidth ?? '0px';
        bar.style.width = target;
      });
    });
  }, [shapValues, maxBarWidth]);

  if (!shapValues.length) return null;

  const maxAbs = Math.max(...shapValues.map((e) => Math.abs(e.shap_value)), 0.01);

  const signalGradient =
    signal === 'OUTPERFORM'
      ? 'from-purple-900/40 to-emerald-950/40'
      : signal === 'UNDERPERFORM'
      ? 'from-purple-900/40 to-red-950/40'
      : 'from-purple-900/40 to-slate-900/40';

  return (
    <div
      ref={containerRef}
      className={`rounded-xl border border-purple-500/20 bg-gradient-to-br ${signalGradient} backdrop-blur-sm p-4 space-y-3`}
    >
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-semibold tracking-widest text-purple-300 uppercase">
          Why {signal}?
        </h4>
        <span className="text-[10px] text-muted-foreground">
          baseline {expectedValue >= 0 ? '+' : ''}{expectedValue.toFixed(3)}
        </span>
      </div>

      <div className="space-y-2">
        {shapValues.map((entry, i) => {
          const pct = Math.abs(entry.shap_value) / maxAbs;
          const barPx = Math.round(pct * maxBarWidth);
          const isPos = entry.shap_value >= 0;

          return (
            <div key={entry.feature} className="flex items-center gap-2">
              <span className="w-36 shrink-0 text-[11px] text-muted-foreground truncate text-right">
                {entry.label}
              </span>
              <div className="flex-1 flex items-center">
                {isPos ? (
                  <>
                    <div className="w-px h-4 bg-muted-foreground" />
                    <div
                      ref={(el) => { barsRef.current[i] = el; }}
                      data-target-width={`${barPx}px`}
                      className="h-3 rounded-r-full"
                      style={{
                        width: 0,
                        background: 'linear-gradient(90deg, #00ff8866, #00ff88)',
                        boxShadow: '0 0 8px #00ff8866',
                      }}
                    />
                  </>
                ) : (
                  <div className="flex items-center" style={{ width: `${barPx + 1}px` }}>
                    <div
                      ref={(el) => { barsRef.current[i] = el; }}
                      data-target-width={`${barPx}px`}
                      className="h-3 rounded-l-full"
                      style={{
                        width: 0,
                        background: 'linear-gradient(270deg, #ff446666, #ff4466)',
                        boxShadow: '0 0 8px #ff446666',
                      }}
                    />
                    <div className="w-px h-4 bg-muted-foreground" />
                  </div>
                )}
              </div>
              <span className={`w-14 shrink-0 text-[11px] tabular-nums font-medium ${isPos ? 'text-emerald-400' : 'text-red-400'}`}>
                {isPos ? '+' : ''}{entry.shap_value.toFixed(3)}
              </span>
            </div>
          );
        })}
      </div>

      <p className="text-[10px] text-muted-foreground pt-1 border-t border-border">
        SHAP — Shapley Additive Explanations
      </p>
    </div>
  );
}
