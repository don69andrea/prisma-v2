'use client';

import { Badge } from '@/components/ui/badge';
import type { CryptoAction } from '@/lib/api/crypto-signals';

interface Props {
  action: CryptoAction;
  confidence: number;
  size?: 'sm' | 'md' | 'lg';
}

const BADGE_STYLES: Record<CryptoAction, string> = {
  BUY:  'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 border-emerald-300',
  HOLD: 'bg-zinc-100 text-zinc-700 dark:bg-zinc-800/40 dark:text-zinc-300 border-zinc-300',
  SELL: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300 border-red-300',
};

export function CryptoSignalBadge({ action, confidence }: Props) {
  const pct = Math.round(confidence * 100);
  return (
    <div className="flex flex-col gap-1">
      <Badge className={`${BADGE_STYLES[action]} font-semibold border`}>
        {action}
      </Badge>
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full rounded-full bg-primary/60 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span>{pct}%</span>
      </div>
    </div>
  );
}
