'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api/client';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface ModelBreakdown {
  model: string;
  calls: number;
  cost_usd: number;
}

interface FeatureBreakdown {
  feature: string;
  calls: number;
  cost_usd: number;
}

interface CallEntry {
  created_at: string;
  model: string;
  feature: string;
  cost_usd: number;
}

interface CostSummary {
  month: string;
  cap_usd: number;
  current_usd: number;
  remaining_usd: number;
  by_model: ModelBreakdown[];
  by_feature: FeatureBreakdown[];
  last_calls: CallEntry[];
}

const CHART_COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'];

export default function AdminPage() {
  const { data, isLoading } = useQuery<CostSummary>({
    queryKey: ['admin-costs'],
    queryFn: () => apiFetch<CostSummary>('/api/v1/admin/costs?last=50'),
  });

  if (isLoading) return <p className="text-muted-foreground">Lädt …</p>;
  if (!data) return null;

  const usedPct = data.cap_usd > 0 ? (data.current_usd / data.cap_usd) * 100 : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Admin — Übersicht</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Monat</p>
          <p className="text-2xl font-bold">{data.month}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Verbrauch</p>
          <p className="text-2xl font-bold">${data.current_usd.toFixed(2)}</p>
          <p className="text-xs text-muted-foreground">von ${data.cap_usd.toFixed(2)} Budget</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Verbleibend</p>
          <p className="text-2xl font-bold text-emerald-500">${data.remaining_usd.toFixed(2)}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Budget-Auslastung</p>
          <p className="text-2xl font-bold">{usedPct.toFixed(1)}%</p>
          <div className="w-full bg-muted rounded-full h-1.5 mt-1">
            <div
              className="h-1.5 rounded-full bg-indigo-500"
              style={{ width: `${Math.min(usedPct, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-sm font-medium">Kosten nach Modell</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={data.by_model} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
              <XAxis dataKey="model" tick={{ fontSize: 11 }} tickFormatter={(v) => v.split('-').slice(-1)[0]} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} width={50} />
              <Tooltip formatter={(v: number) => [`$${v.toFixed(4)}`, 'Kosten']} />
              <Bar dataKey="cost_usd" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-border bg-card p-4 space-y-3">
          <h2 className="text-sm font-medium">Kosten nach Feature</h2>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={data.by_feature}
                dataKey="cost_usd"
                nameKey="feature"
                cx="50%"
                cy="50%"
                outerRadius={70}
                label={({ feature, percent }) => `${feature} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {data.by_feature.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => [`$${v.toFixed(4)}`, 'Kosten']} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Calls Table */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <h2 className="text-sm font-medium">Letzte LLM-Calls</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="pb-2 pr-4 font-medium">Zeitpunkt</th>
                <th className="pb-2 pr-4 font-medium">Modell</th>
                <th className="pb-2 pr-4 font-medium">Feature</th>
                <th className="pb-2 font-medium text-right">Kosten</th>
              </tr>
            </thead>
            <tbody>
              {data.last_calls.map((call, i) => (
                <tr key={i} className="border-b border-border/50 last:border-0">
                  <td className="py-2 pr-4 text-muted-foreground">
                    {new Date(call.created_at).toLocaleString('de-CH')}
                  </td>
                  <td className="py-2 pr-4">{call.model}</td>
                  <td className="py-2 pr-4">{call.feature}</td>
                  <td className="py-2 text-right font-mono">${call.cost_usd.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
