'use client';

import { useQuery } from '@tanstack/react-query';
import { getMacroContext, type MacroClimate } from '@/lib/api/macro';
import { Skeleton } from '@/components/ui/skeleton';
import { InfoPopover } from '@/components/InfoPopover';
import { cn } from '@/lib/utils';

const CLIMATE_CONFIG: Record<
  MacroClimate,
  { label: string; dot: string; bg: string; text: string }
> = {
  EXPANSIV:    { label: 'Expansiv',    dot: 'bg-emerald-500', bg: 'bg-emerald-50 dark:bg-emerald-950/30', text: 'text-emerald-700 dark:text-emerald-400' },
  NEUTRAL:     { label: 'Neutral',     dot: 'bg-amber-500',   bg: 'bg-amber-50 dark:bg-amber-950/30',    text: 'text-amber-700 dark:text-amber-400'   },
  RESTRIKTIV:  { label: 'Restriktiv',  dot: 'bg-rose-500',    bg: 'bg-rose-50 dark:bg-rose-950/30',      text: 'text-rose-700 dark:text-rose-400'     },
};

export function MacroWidget() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['macro-context'],
    queryFn: getMacroContext,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border p-4 space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-3 w-full" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-lg border p-4 text-sm text-muted-foreground">
        Makro-Daten nicht verfügbar.
      </div>
    );
  }

  const cfg = CLIMATE_CONFIG[data.climate] ?? CLIMATE_CONFIG.NEUTRAL;
  const snbLow = data.leitzins <= 0.5;

  return (
    <div className={cn('rounded-lg border p-4 space-y-3', cfg.bg)}>
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Makro-Klima Schweiz
        </p>
        <div className={cn('flex items-center gap-1.5 text-sm font-semibold', cfg.text)}>
          <span className={cn('h-2 w-2 rounded-full', cfg.dot)} />
          {cfg.label}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="flex items-center gap-1">
            <p className="text-[11px] text-muted-foreground">SNB-Leitzins</p>
            <InfoPopover ariaLabel="Info: SNB-Leitzins">
              Der Leitzins der Schweizerischen Nationalbank. Beeinflusst die Attraktivität von Aktien vs. Obligationen.
            </InfoPopover>
          </div>
          <p className="font-semibold">{data.leitzins.toFixed(2)}%</p>
          <p className={cn('text-[10px] mt-0.5', snbLow ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400')}>
            {snbLow
              ? 'Tiefzinsumfeld begünstigt Aktienanlagen'
              : 'Zinsen gestiegen — Obligationen werden attraktiver'}
          </p>
        </div>
        <div>
          <p className="text-[11px] text-muted-foreground">CHF / EUR</p>
          <p className="font-semibold">{data.chf_eur.toFixed(4)}</p>
        </div>
        {data.inflation_ch !== null && (
          <div>
            <p className="text-[11px] text-muted-foreground">Inflation CH</p>
            <p className="font-semibold">{data.inflation_ch.toFixed(1)}%</p>
          </div>
        )}
        {data.pmi_ch !== null && (
          <div>
            <p className="text-[11px] text-muted-foreground">PMI CH</p>
            <p className="font-semibold">{data.pmi_ch.toFixed(1)}</p>
          </div>
        )}
      </div>

      <p className="text-xs text-muted-foreground leading-relaxed border-t pt-2">
        {data.narrative_de}
      </p>
    </div>
  );
}
