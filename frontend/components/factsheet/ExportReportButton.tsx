'use client';

import { useState } from 'react';
import { Download, CheckCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  ticker: string;
}

const STEPS = [
  'Quant Scores',
  'ML Prediction',
  'Swiss-Daten',
  'Rendering PDF',
];

export function ExportReportButton({ ticker }: Props) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
  const [step, setStep] = useState(0);

  const handleExport = async () => {
    setState('loading');
    setStep(0);

    for (let i = 0; i < STEPS.length - 1; i++) {
      await new Promise<void>((r) => setTimeout(r, 350));
      setStep(i + 1);
    }

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const res = await fetch(`${API_BASE}/api/v1/stocks/${ticker}/report.pdf`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');
      a.href = url;
      a.download = `PRISMA_${ticker}_${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      setState('done');
      setTimeout(() => setState('idle'), 3000);
    } catch {
      setState('error');
      setTimeout(() => setState('idle'), 2000);
    }
  };

  return (
    <div className="flex flex-col items-end gap-1.5">
      <button
        onClick={handleExport}
        disabled={state === 'loading'}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
          'border backdrop-blur-sm',
          state === 'idle' && 'bg-muted-foreground/60 border-border text-muted-foreground hover:border-purple-500/60 hover:text-white',
          state === 'loading' && 'bg-muted-foreground/60 border-purple-500/40 text-purple-300 cursor-not-allowed',
          state === 'done' && 'bg-emerald-950/60 border-emerald-500/40 text-emerald-400',
          state === 'error' && 'bg-red-950/60 border-red-500/40 text-red-400',
        )}
      >
        {state === 'loading' && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {state === 'done' && <CheckCircle className="h-3.5 w-3.5" />}
        {(state === 'idle' || state === 'error') && <Download className="h-3.5 w-3.5" />}
        {state === 'idle' && 'Export Report'}
        {state === 'loading' && 'Generating...'}
        {state === 'done' && 'Downloaded!'}
        {state === 'error' && 'Error — retry'}
      </button>

      {state === 'loading' && (
        <div className="flex items-center gap-2">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-1">
              {i > 0 && <span className="text-muted-foreground text-[10px]">&#8594;</span>}
              <span
                className={cn(
                  'text-[10px] transition-colors duration-300',
                  i < step ? 'text-emerald-500' : i === step ? 'text-purple-400' : 'text-muted-foreground',
                )}
              >
                {i < step ? '✓' : ''} {s}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
