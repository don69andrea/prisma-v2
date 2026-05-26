'use client';

import { Info } from 'lucide-react';
import type { ReactNode } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface Props {
  ariaLabel: string;
  children: ReactNode;
}

export function InfoPopover({ ariaLabel, children }: Props) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded text-muted-foreground opacity-60 hover:opacity-100 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Info className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="max-w-xs text-sm leading-relaxed" side="top">
        {children}
      </PopoverContent>
    </Popover>
  );
}
