'use client';

import { useCallback, useState } from 'react';
import { cn } from '@/lib/utils';

// Standard weights in percent
const DEFAULT_QUANT = 45;
const DEFAULT_ML = 35;
const DEFAULT_MACRO = 20;
const MAX_SINGLE = 80; // max % for any one slider

function computeScore(
  quant: number,
  ml: number,
  macro: number,
  wQuant: number,
  wMl: number,
  wMacro: number,
): number {
  return quant * (wQuant / 100) + ml * (wMl / 100) + macro * (wMacro / 100);
}

function scoreToSignal(score: number): 'BUY' | 'HOLD' | 'WATCH' {
  if (score >= 70) return 'BUY';
  if (score >= 40) return 'HOLD';
  return 'WATCH';
}

const SIGNAL_COLORS = {
  BUY: '#7ee787',
  HOLD: '#ffa657',
  WATCH: '#8b949e',
};

interface SliderRowProps {
  label: string;
  color: string;
  value: number;
  onChange: (v: number) => void;
}

function SliderRow({ label, color, value, onChange }: SliderRowProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-medium" style={{ color }}>
          {label}
        </span>
        <span className="tabular-nums text-[#e6edf3] font-semibold">{value}%</span>
      </div>
      <input
        type="range"
        min={0}
        max={MAX_SINGLE}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={
          {
            accentColor: color,
            background: `linear-gradient(to right, ${color} 0%, ${color} ${(value / MAX_SINGLE) * 100}%, #21262d ${(value / MAX_SINGLE) * 100}%, #21262d 100%)`,
          } as React.CSSProperties
        }
        aria-label={`${label} Gewichtung`}
      />
    </div>
  );
}

export interface WeightSensitivityProps {
  quantScore: number;
  mlScore: number;
  macroScore: number;
  /** The standard-weighted score returned by the API */
  standardScore: number;
  standardSignal: 'BUY' | 'HOLD' | 'WATCH';
  className?: string;
}

export function WeightSensitivity({
  quantScore,
  mlScore,
  macroScore,
  standardScore,
  standardSignal,
  className,
}: WeightSensitivityProps) {
  const [open, setOpen] = useState(false);
  const [wQuant, setWQuant] = useState(DEFAULT_QUANT);
  const [wMl, setWMl] = useState(DEFAULT_ML);
  const [wMacro, setWMacro] = useState(DEFAULT_MACRO);

  // Proportional redistribution: when one slider changes, redistribute
  // the remainder to the other two proportionally.
  const handleQuantChange = useCallback(
    (v: number) => {
      const remaining = 100 - v;
      const oldRest = wMl + wMacro;
      if (oldRest === 0) {
        setWQuant(v);
        setWMl(Math.round(remaining / 2));
        setWMacro(remaining - Math.round(remaining / 2));
      } else {
        const newMl = Math.round((wMl / oldRest) * remaining);
        const newMacro = remaining - newMl;
        setWQuant(v);
        setWMl(Math.max(0, newMl));
        setWMacro(Math.max(0, newMacro));
      }
    },
    [wMl, wMacro],
  );

  const handleMlChange = useCallback(
    (v: number) => {
      const remaining = 100 - v;
      const oldRest = wQuant + wMacro;
      if (oldRest === 0) {
        setWMl(v);
        setWQuant(Math.round(remaining / 2));
        setWMacro(remaining - Math.round(remaining / 2));
      } else {
        const newQuant = Math.round((wQuant / oldRest) * remaining);
        const newMacro = remaining - newQuant;
        setWMl(v);
        setWQuant(Math.max(0, newQuant));
        setWMacro(Math.max(0, newMacro));
      }
    },
    [wQuant, wMacro],
  );

  const handleMacroChange = useCallback(
    (v: number) => {
      const remaining = 100 - v;
      const oldRest = wQuant + wMl;
      if (oldRest === 0) {
        setWMacro(v);
        setWQuant(Math.round(remaining / 2));
        setWMl(remaining - Math.round(remaining / 2));
      } else {
        const newQuant = Math.round((wQuant / oldRest) * remaining);
        const newMl = remaining - newQuant;
        setWMacro(v);
        setWQuant(Math.max(0, newQuant));
        setWMl(Math.max(0, newMl));
      }
    },
    [wQuant, wMl],
  );

  function reset() {
    setWQuant(DEFAULT_QUANT);
    setWMl(DEFAULT_ML);
    setWMacro(DEFAULT_MACRO);
  }

  const isDefault =
    wQuant === DEFAULT_QUANT && wMl === DEFAULT_ML && wMacro === DEFAULT_MACRO;
  const sumOk = wQuant + wMl + wMacro === 100;

  const customScore = computeScore(quantScore, mlScore, macroScore, wQuant, wMl, wMacro);
  const customSignal = scoreToSignal(customScore);
  const signalChanged = customSignal !== standardSignal;

  const customColor = SIGNAL_COLORS[customSignal];
  const standardColor = SIGNAL_COLORS[standardSignal];

  const scoreDelta = customScore - standardScore;

  return (
    <div className={cn('rounded-xl border border-[#21262d]', className)}>
      {/* Accordion header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-[#21262d]/40 transition-colors rounded-xl"
        aria-expanded={open}
      >
        <div className="flex items-center gap-2">
          <svg
            width="13"
            height="13"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#8b949e"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
            <path d="M15.54 8.46a5 5 0 0 1 0 7.07M8.46 8.46a5 5 0 0 0 0 7.07" />
          </svg>
          <span className="text-[11px] font-semibold text-[#8b949e] uppercase tracking-[0.08em]">
            Gewichtung anpassen
          </span>
        </div>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#8b949e"
          strokeWidth="2"
          strokeLinecap="round"
          className={cn('transition-transform duration-200', open && 'rotate-180')}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {/* Accordion body */}
      {open && (
        <div className="px-4 pb-4 space-y-4 border-t border-[#21262d]">
          <p className="text-[10px] text-[#8b949e] pt-3 leading-relaxed">
            Verschiebe die Regler, um zu sehen wie das Signal reagiert.
            Die drei Gewichte müssen zusammen 100% ergeben.
          </p>

          {/* Sliders */}
          <div className="space-y-3">
            <SliderRow
              label={`Quant (${DEFAULT_QUANT}% Standard)`}
              color="#58a6ff"
              value={wQuant}
              onChange={handleQuantChange}
            />
            <SliderRow
              label={`ML (${DEFAULT_ML}% Standard)`}
              color="#bc8cff"
              value={wMl}
              onChange={handleMlChange}
            />
            <SliderRow
              label={`Makro (${DEFAULT_MACRO}% Standard)`}
              color="#7ee787"
              value={wMacro}
              onChange={handleMacroChange}
            />
          </div>

          {/* Sum indicator */}
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-[#8b949e]">Summe</span>
            <span
              className={cn(
                'font-semibold tabular-nums',
                sumOk ? 'text-[#7ee787]' : 'text-[#f85149]',
              )}
            >
              {wQuant + wMl + wMacro}% {sumOk ? '✓' : '≠ 100%'}
            </span>
          </div>

          {/* Result */}
          {sumOk && (
            <div
              className="rounded-xl p-3 space-y-2"
              style={{
                background: `${customColor}0a`,
                border: `1px solid ${customColor}30`,
              }}
            >
              {/* Custom score line */}
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-[#8b949e]">Bei dieser Gewichtung</span>
                <div className="flex items-center gap-2">
                  <span className="text-[12px] font-bold tabular-nums text-[#e6edf3]">
                    Score {customScore.toFixed(1)}
                  </span>
                  <span
                    className="text-[11px] font-bold px-2 py-0.5 rounded-full"
                    style={{
                      color: customColor,
                      background: `${customColor}18`,
                      border: `1px solid ${customColor}40`,
                    }}
                  >
                    {customSignal}
                  </span>
                </div>
              </div>

              {/* Separator */}
              <div className="border-t border-[#21262d]" />

              {/* Standard comparison */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[#8b949e]">
                  Standard ({DEFAULT_QUANT}/{DEFAULT_ML}/{DEFAULT_MACRO})
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] tabular-nums text-[#8b949e]">
                    {standardScore.toFixed(1)}
                  </span>
                  <span
                    className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full"
                    style={{
                      color: standardColor,
                      background: `${standardColor}10`,
                      border: `1px solid ${standardColor}30`,
                    }}
                  >
                    {standardSignal}
                  </span>
                </div>
              </div>

              {/* Delta */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-[#8b949e]">Score-Differenz</span>
                <span
                  className={cn(
                    'text-[11px] font-semibold tabular-nums',
                    scoreDelta > 0
                      ? 'text-[#7ee787]'
                      : scoreDelta < 0
                      ? 'text-[#f85149]'
                      : 'text-[#8b949e]',
                  )}
                >
                  {scoreDelta > 0 ? '+' : ''}
                  {scoreDelta.toFixed(1)} Pkt
                </span>
              </div>

              {/* Signal change callout */}
              {signalChanged && (
                <div
                  className="rounded-lg px-3 py-2 text-[11px] font-medium leading-snug"
                  style={{
                    background: `${customColor}15`,
                    border: `1px solid ${customColor}40`,
                    color: customColor,
                  }}
                >
                  Deine Gewichtung aendert das Signal von{' '}
                  <span style={{ color: standardColor }}>{standardSignal}</span> zu{' '}
                  <span style={{ color: customColor }}>{customSignal}</span>!
                </div>
              )}

              {!signalChanged && !isDefault && (
                <p className="text-[10px] text-[#8b949e]">
                  Signal bleibt {customSignal} — auch mit dieser Gewichtung.
                </p>
              )}
            </div>
          )}

          {/* Reset */}
          {!isDefault && (
            <button
              onClick={reset}
              className="inline-flex items-center gap-1.5 rounded-md border border-[#21262d] px-3 py-1.5 text-[11px] font-medium text-[#8b949e] hover:bg-[#21262d] hover:text-[#e6edf3] transition-colors"
            >
              <svg
                width="11"
                height="11"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                <path d="M3 3v5h5" />
              </svg>
              Zurücksetzen (45/35/20)
            </button>
          )}
        </div>
      )}
    </div>
  );
}
