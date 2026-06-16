'use client';

import { Info } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface InfoTooltipProps {
  text: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  className?: string;
}

/**
 * Kleines Info-Icon mit Popover — zeigt statischen Erklärungstext.
 * Kein API-Call (im Gegensatz zu ExplainButton).
 */
export function InfoTooltip({ text, side = 'top', className }: InfoTooltipProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Info"
          className={
            className ??
            'inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:text-foreground hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring shrink-0'
          }
        >
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="max-w-xs text-sm leading-relaxed"
        side={side}
        sideOffset={6}
      >
        <p>{text}</p>
      </PopoverContent>
    </Popover>
  );
}
