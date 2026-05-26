'use client';

import { useRouter } from 'next/navigation';
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';

import { ROUTES } from '@/lib/routes';
import type { RankingItem } from '@/lib/api/runs';

interface Props {
  items: RankingItem[];
  runId: string;
}

interface ChartDatum {
  ticker: string;
  weighted_avg: number;
  weighted_avg_raw: number | null;
  is_sweet_spot: boolean;
}

const AMBER = '#f59e0b';
const PRIMARY = 'hsl(var(--primary))';

function TickLabel(props: {
  x?: number;
  y?: number;
  payload?: { value: string };
  data: ChartDatum[];
  onClick: (ticker: string) => void;
}) {
  const { x, y, payload, data, onClick } = props;
  if (!payload) return null;
  const ticker = payload.value;
  const datum = data.find((d) => d.ticker === ticker);
  const fill = datum?.is_sweet_spot ? AMBER : 'currentColor';
  return (
    <text
      x={x}
      y={y}
      dy={4}
      tabIndex={0}
      role="link"
      aria-label={`${ticker} Factsheet öffnen`}
      textAnchor="end"
      className="cursor-pointer font-mono text-xs focus:outline-none focus:underline"
      fill={fill}
      onClick={() => onClick(ticker)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick(ticker);
        }
      }}
    >
      {ticker}
    </text>
  );
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDatum }> }) {
  if (!active || !payload || payload.length === 0) return null;
  const { ticker, weighted_avg_raw, is_sweet_spot } = payload[0].payload;
  const avgDisplay = weighted_avg_raw !== null ? weighted_avg_raw.toFixed(2) : '—';
  return (
    <div className="rounded border bg-popover px-2 py-1 text-sm text-popover-foreground shadow-sm">
      <span className="font-mono">{ticker}</span>
      <span className="text-muted-foreground"> — Avg {avgDisplay}</span>
      {is_sweet_spot && <span className="text-amber-500"> • Sweet-Spot</span>}
    </div>
  );
}

export function TopTenBars({ items, runId }: Props) {
  const router = useRouter();
  const chartData: ChartDatum[] = items.map((item) => ({
    ticker: item.ticker,
    weighted_avg: item.weighted_avg ?? 0,
    weighted_avg_raw: item.weighted_avg,
    is_sweet_spot: item.is_sweet_spot,
  }));

  const handleNavigate = (ticker: string) => {
    router.push(ROUTES.factsheet(runId, ticker));
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 4, right: 32, bottom: 4, left: 4 }}
      >
        <XAxis type="number" hide reversed />
        <YAxis
          type="category"
          dataKey="ticker"
          width={64}
          tickLine={false}
          axisLine={false}
          tick={(tickProps) => (
            <TickLabel {...tickProps} data={chartData} onClick={handleNavigate} />
          )}
        />
        <Tooltip cursor={{ fill: 'hsl(var(--muted))', opacity: 0.3 }} content={<CustomTooltip />} />
        <Bar dataKey="weighted_avg" radius={[0, 4, 4, 0]} isAnimationActive={false}>
          {chartData.map((entry) => (
            <Cell key={entry.ticker} fill={entry.is_sweet_spot ? AMBER : PRIMARY} />
          ))}
          <LabelList
            dataKey="weighted_avg"
            position="right"
            formatter={(value: unknown) => (typeof value === 'number' ? value.toFixed(2) : '—')}
            className="fill-foreground text-xs"
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
