'use client';

import { type CryptoSignal, signalColor, signalLabel } from '@/lib/api/crypto';

interface CryptoProRowProps {
  signal: CryptoSignal;
}

function fmt(n: number | null, decimals = 2): string {
  if (n == null) return '—';
  return n.toLocaleString('de-CH', { maximumFractionDigits: decimals, minimumFractionDigits: decimals });
}

function fmtPct(n: number | null): string {
  if (n == null) return '—';
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(1)}%`;
}

function pctColor(n: number | null): string {
  if (n == null) return '';
  return n > 0 ? 'text-[#7ee787]' : n < 0 ? 'text-[#f85149]' : 'text-muted-foreground';
}

export function CryptoProRow({ signal }: CryptoProRowProps) {
  const color = signalColor(signal.signal);
  const label = signalLabel(signal.signal);

  return (
    <tr className="border-b border-border/30 hover:bg-muted/20 transition-colors text-sm">
      <td className="py-2 px-3">
        <div className="font-mono font-bold">{signal.ticker}</div>
        <div className="text-[10px] text-muted-foreground">{signal.name}</div>
      </td>
      <td className="py-2 px-3">
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full border whitespace-nowrap"
          style={{ color, borderColor: color + '50', backgroundColor: color + '20' }}
        >
          {label}
        </span>
      </td>
      <td className="py-2 px-3 tabular-nums">
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-12 rounded-full bg-[#21262d] overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${Math.round(signal.score)}%`, backgroundColor: color }}
            />
          </div>
          <span className="text-xs">{signal.score}</span>
        </div>
      </td>
      <td className="py-2 px-3 tabular-nums text-right">
        {signal.price_chf != null ? `CHF ${fmt(signal.price_chf, 0)}` : '—'}
      </td>
      <td className={`py-2 px-3 tabular-nums text-right ${pctColor(signal.price_change_24h_pct)}`}>
        {fmtPct(signal.price_change_24h_pct)}
      </td>
      <td className={`py-2 px-3 tabular-nums text-right ${pctColor(signal.price_change_7d_pct)}`}>
        {fmtPct(signal.price_change_7d_pct)}
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.rsi_14.toFixed(1)}
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.volatility_30d_pct.toFixed(1)}%
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.correlation_smi_1y.toFixed(2)}
      </td>
    </tr>
  );
}
