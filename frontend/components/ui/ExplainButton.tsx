'use client';

import { useRef, useState } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { streamChat } from '@/lib/api/chat';

const CONTEXT_PROMPTS: Record<string, string> = {
  quality_score:
    'Was bedeutet der Quality-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  trend_score:
    'Was bedeutet der Trend-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  value_score:
    'Was bedeutet der Value-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  macro_score:
    'Was bedeutet der Makro-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  diversification:
    'Was bedeutet Diversification-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  ml_prediction:
    'Was bedeutet die ML-Prediction bei PRISMA? Erkläre in max. 3 Sätzen auf Deutsch.',
  confidence:
    'Was bedeutet der Konfidenz-Wert bei PRISMA-Signalen? Erkläre in max. 3 Sätzen auf Deutsch.',
  signal:
    'Was bedeutet BUY/HOLD/WATCH bei PRISMA? Erkläre in max. 3 Sätzen auf Deutsch.',
};

interface ExplainButtonProps {
  context: string;
  ticker?: string;
  label?: string;
  className?: string;
}

export function ExplainButton({
  context,
  ticker,
  label = '?',
  className,
}: ExplainButtonProps) {
  const [open, setOpen]       = useState(false);
  const [text, setText]       = useState('');
  const [loading, setLoading] = useState(false);
  const cancelRef             = useRef<(() => void) | null>(null);

  function handleOpen(isOpen: boolean) {
    setOpen(isOpen);
    if (!isOpen) {
      cancelRef.current?.();
      return;
    }
    if (text) return;

    const prompt =
      CONTEXT_PROMPTS[context] ??
      `Was bedeutet "${context}"${ticker ? ` für ${ticker}` : ''}? Erkläre in max. 3 Sätzen auf Deutsch.`;

    setText('');
    setLoading(true);

    const cancel = streamChat(
      prompt,
      [],
      (event) => {
        if (event.type === 'token' && event.content) {
          setText((prev) => prev + event.content);
        }
      },
      () => setLoading(false),
      () => setLoading(false),
    );
    cancelRef.current = cancel;
  }

  return (
    <Popover open={open} onOpenChange={handleOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`${context} erklären`}
          className={
            className ??
            'inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold text-[#8b949e] hover:text-[#58a6ff] hover:bg-[#21262d] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#58a6ff]'
          }
        >
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="max-w-xs text-sm leading-relaxed bg-[#161b22] border-[#21262d] text-[#e6edf3]"
        side="top"
      >
        {loading && !text && (
          <p className="text-[#8b949e] text-xs">PRISMA erklärt…</p>
        )}
        {text && (
          <p className="whitespace-pre-wrap">
            {text}
            {loading && (
              <span
                className="inline-block w-[1px] h-[1em] bg-[#58a6ff] ml-0.5 align-middle [animation:blink-cursor_1s_step-end_infinite]"
                aria-hidden
              />
            )}
          </p>
        )}
        {!loading && !text && (
          <p className="text-[#f85149] text-xs">Erklärung nicht verfügbar.</p>
        )}
        <p className="mt-2 text-[10px] text-[#8b949e] border-t border-[#21262d] pt-1.5">
          Erklärt von Claude Haiku
        </p>
      </PopoverContent>
    </Popover>
  );
}
