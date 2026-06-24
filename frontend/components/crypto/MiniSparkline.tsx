'use client';

import { LineChart, Line, ResponsiveContainer } from 'recharts';

interface Props {
  data: { date: string; close: number }[];
  positive?: boolean;
}

export function MiniSparkline({ data, positive }: Props) {
  if (data.length === 0) return <div className="h-8 w-20 bg-muted/30 rounded" />;
  const color = positive === false ? '#ef4444' : '#22c55e';
  return (
    <ResponsiveContainer width={80} height={32}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="close"
          stroke={color}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
