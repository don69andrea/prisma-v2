import { TrendingUp, Minus, Eye } from 'lucide-react';

import { cn } from '@/lib/utils';

export type SignalType = 'BUY' | 'HOLD' | 'WATCH' | 'SELL';

interface SignalBadgeProps {
  signal: SignalType;
  confidence?: number;
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
  className?: string;
}

const SIGNAL_CONFIG = {
  BUY: {
    bg:     'bg-[#0d2d1a]',
    text:   'text-[#7ee787]',
    border: 'border-[#7ee787]/30',
    label:  'BUY',
    Icon:   TrendingUp,
    rotate: '',
  },
  HOLD: {
    bg:     'bg-[#2d1a0d]',
    text:   'text-[#ffa657]',
    border: 'border-[#ffa657]/30',
    label:  'HOLD',
    Icon:   Minus,
    rotate: '',
  },
  WATCH: {
    bg:     'bg-[#0d1f3c]',
    text:   'text-[#58a6ff]',
    border: 'border-[#58a6ff]/30',
    label:  'BEOBACHTEN',
    Icon:   Eye,
    rotate: '',
  },
  SELL: {
    bg:     'bg-[#2d0d0d]',
    text:   'text-[#f85149]',
    border: 'border-[#f85149]/30',
    label:  'SELL',
    Icon:   TrendingUp,
    rotate: 'rotate-180',
  },
} satisfies Record<
  SignalType,
  {
    bg: string;
    text: string;
    border: string;
    label: string;
    Icon: React.ComponentType<{ className?: string }>;
    rotate: string;
  }
>;

const SIZE_CONFIG = {
  sm: { wrap: 'px-2 py-0.5 text-[10px] gap-1',  icon: 'h-2.5 w-2.5' },
  md: { wrap: 'px-3 py-1   text-xs     gap-1.5', icon: 'h-3   w-3'   },
  lg: { wrap: 'px-4 py-1.5 text-sm     gap-2',   icon: 'h-3.5 w-3.5' },
};

export function SignalBadge({
  signal,
  confidence,
  size = 'md',
  animated = false,
  className,
}: SignalBadgeProps) {
  const cfg   = SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.WATCH;
  const szcfg = SIZE_CONFIG[size];

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border font-semibold tracking-wide',
        cfg.bg, cfg.text, cfg.border,
        szcfg.wrap,
        animated && signal === 'BUY' && '[animation:pulse-glow_2s_ease-in-out_infinite]',
        className,
      )}
    >
      <cfg.Icon className={cn(szcfg.icon, cfg.rotate)} aria-hidden />
      <span>{cfg.label}</span>
      {confidence !== undefined && (
        <span className="opacity-60 font-normal">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}
