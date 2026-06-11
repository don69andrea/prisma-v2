import { cn } from '@/lib/utils';

interface PrismaScoreProps {
  label: string;
  score: number;
  color?: 'green' | 'blue' | 'purple' | 'orange';
  showExplain?: boolean;
  onExplain?: () => void;
  className?: string;
}

const COLOR_GRADIENT: Record<NonNullable<PrismaScoreProps['color']>, string> = {
  green:  'from-[#f85149] via-[#ffa657] to-[#7ee787]',
  blue:   'from-[#f85149] via-[#ffa657] to-[#58a6ff]',
  purple: 'from-[#f85149] via-[#ffa657] to-[#bc8cff]',
  orange: 'from-[#f85149] via-[#ffa657] to-[#ffa657]',
};

function scoreTextColor(score: number): string {
  if (score >= 70) return 'text-[#7ee787]';
  if (score >= 40) return 'text-[#ffa657]';
  return 'text-[#f85149]';
}

export function PrismaScore({
  label,
  score,
  color = 'green',
  showExplain = false,
  onExplain,
  className,
}: PrismaScoreProps) {
  const pct = Math.max(0, Math.min(100, Math.round(score)));

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span className="text-xs text-[#8b949e] w-24 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-[#21262d] overflow-hidden">
        <div
          className={cn('h-full rounded-full bg-gradient-to-r', COLOR_GRADIENT[color])}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${pct}`}
        />
      </div>
      <span className={cn('text-xs font-mono font-semibold w-7 text-right', scoreTextColor(pct))}>
        {pct}
      </span>
      {showExplain && (
        <button
          type="button"
          onClick={onExplain}
          aria-label={`${label} erklären`}
          className="text-[10px] text-[#8b949e] hover:text-[#58a6ff] transition-colors w-4 shrink-0"
        >
          ?
        </button>
      )}
    </div>
  );
}
