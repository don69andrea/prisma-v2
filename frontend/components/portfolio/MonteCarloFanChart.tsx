'use client';

import { useEffect, useRef } from 'react';

interface Props {
  p5: number[];
  p50: number[];
  p95: number[];
  contributionLine: number[];
  years: number;
  correlationDegraded?: boolean;
}

const W = 600;
const H = 320;
const PAD = { top: 20, right: 20, bottom: 40, left: 70 };
const INNER_W = W - PAD.left - PAD.right;
const INNER_H = H - PAD.top - PAD.bottom;

function scaleX(i: number, total: number) {
  return PAD.left + (i / (total - 1)) * INNER_W;
}

function scaleY(v: number, minV: number, maxV: number) {
  return PAD.top + INNER_H - ((v - minV) / (maxV - minV)) * INNER_H;
}

function toPath(values: number[], minV: number, maxV: number) {
  return values
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${scaleX(i, values.length).toFixed(1)},${scaleY(v, minV, maxV).toFixed(1)}`)
    .join(' ');
}

function toArea(top: number[], bottom: number[], minV: number, maxV: number) {
  const forward = top.map(
    (v, i) => `${i === 0 ? 'M' : 'L'}${scaleX(i, top.length).toFixed(1)},${scaleY(v, minV, maxV).toFixed(1)}`
  );
  const backward = [...bottom]
    .reverse()
    .map(
      (v, i) => `L${scaleX(bottom.length - 1 - i, bottom.length).toFixed(1)},${scaleY(v, minV, maxV).toFixed(1)}`
    );
  return [...forward, ...backward, 'Z'].join(' ');
}

function formatCHF(v: number) {
  if (v >= 1_000_000) return `CHF ${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `CHF ${(v / 1_000).toFixed(0)}k`;
  return `CHF ${v.toFixed(0)}`;
}

export function MonteCarloFanChart({ p5, p50, p95, contributionLine, years, correlationDegraded }: Props) {
  const pathRef = useRef<SVGPathElement>(null);

  useEffect(() => {
    if (!pathRef.current) return;
    const len = pathRef.current.getTotalLength();
    pathRef.current.style.strokeDasharray = `${len}`;
    pathRef.current.style.strokeDashoffset = `${len}`;
    pathRef.current.style.transition = 'stroke-dashoffset 1.8s ease-in-out';
    requestAnimationFrame(() => {
      if (pathRef.current) pathRef.current.style.strokeDashoffset = '0';
    });
  }, [p50]);

  const allValues = [...p5, ...p95, ...contributionLine];
  const minV = Math.min(...allValues, 0);
  const maxV = Math.max(...allValues) * 1.05;

  const n = p50.length;
  const yTicks = 5;
  const xLabelStep = Math.max(1, Math.floor(years / 5));

  return (
    <div className="space-y-2">
      {correlationDegraded && (
        <div className="rounded-lg px-3 py-2 text-xs flex items-start gap-2" style={{ background: 'rgba(234,179,8,0.1)', border: '1px solid rgba(234,179,8,0.3)', color: '#ca8a04' }}>
          <span className="mt-0.5 shrink-0">⚠</span>
          <span>Korrelationsdaten unvollständig — Simulation ohne Titelkorrelationen berechnet. Diversifikationseffekte können über- oder unterschätzt sein.</span>
        </div>
      )}
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id="fanGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.1" />
        </linearGradient>
        <filter id="glow">
          <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* Y grid lines */}
      {Array.from({ length: yTicks }).map((_, i) => {
        const v = minV + ((maxV - minV) * i) / (yTicks - 1);
        const y = scaleY(v, minV, maxV);
        return (
          <g key={i}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y} y2={y} stroke="#1e293b" strokeWidth="1" />
            <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize="10" fill="#475569">
              {formatCHF(v)}
            </text>
          </g>
        );
      })}

      {/* X axis labels */}
      {Array.from({ length: Math.ceil(years / xLabelStep) + 1 }).map((_, i) => {
        const yr = i * xLabelStep;
        if (yr > years) return null;
        const monthIdx = Math.min(yr * 12, n - 1);
        const x = scaleX(monthIdx, n);
        return (
          <text key={i} x={x} y={H - PAD.bottom + 16} textAnchor="middle" fontSize="10" fill="#475569">
            {yr}J
          </text>
        );
      })}

      {/* Fan area P5–P95 */}
      <path d={toArea(p95, p5, minV, maxV)} fill="url(#fanGrad)" />

      {/* P5 line */}
      <path d={toPath(p5, minV, maxV)} fill="none" stroke="#4f46e5" strokeWidth="1" strokeOpacity="0.6" strokeDasharray="4 3" />

      {/* P95 line */}
      <path d={toPath(p95, minV, maxV)} fill="none" stroke="#7c3aed" strokeWidth="1" strokeOpacity="0.6" strokeDasharray="4 3" />

      {/* Contribution baseline */}
      <path
        d={toPath(contributionLine, minV, maxV)}
        fill="none"
        stroke="#475569"
        strokeWidth="1.5"
        strokeDasharray="6 4"
      />

      {/* P50 median — animated draw-on */}
      <path
        ref={pathRef}
        d={toPath(p50, minV, maxV)}
        fill="none"
        stroke="white"
        strokeWidth="2.5"
        filter="url(#glow)"
      />

      {/* Legend */}
      <g transform={`translate(${PAD.left + 8}, ${PAD.top + 8})`}>
        <line x1="0" x2="20" y1="6" y2="6" stroke="white" strokeWidth="2.5" />
        <text x="24" y="10" fontSize="9" fill="#cbd5e1">Median (P50)</text>
        <rect x="0" y="18" width="20" height="8" fill="url(#fanGrad)" rx="2" />
        <text x="24" y="27" fontSize="9" fill="#94a3b8">P5–P95 Band</text>
        <line x1="0" x2="20" y1="40" y2="40" stroke="#475569" strokeWidth="1.5" strokeDasharray="6 4" />
        <text x="24" y="44" fontSize="9" fill="#64748b">Einzahlungen</text>
      </g>
    </svg>
    </div>
  );
}
