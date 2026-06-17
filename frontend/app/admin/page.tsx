'use client';

import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '@/lib/api/client';

interface CostSummary {
  total_usd: number;
  by_model: Record<string, number>;
  by_feature: Record<string, number>;
  recent_calls: Array<{
    model: string;
    feature: string;
    cost_usd: number;
    created_at: string;
  }>;
}

export default function AdminPage() {
  const { data, isLoading } = useQuery<CostSummary>({
    queryKey: ['admin-costs'],
    queryFn: () => apiFetch<CostSummary>('/api/v1/admin/costs'),
  });

  if (isLoading) return <p className="text-muted-foreground">Lädt …</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Admin — Übersicht</h1>

      <div className="rounded-lg border border-border p-6 space-y-1">
        <p className="text-sm text-muted-foreground">LLM-Kosten (aktueller Monat)</p>
        <p className="text-3xl font-bold">${data.total_usd.toFixed(4)}</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-border p-4 space-y-2">
          <h2 className="text-sm font-medium">Nach Modell</h2>
          {Object.entries(data.by_model).map(([model, cost]) => (
            <div key={model} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{model}</span>
              <span>${cost.toFixed(4)}</span>
            </div>
          ))}
        </div>

        <div className="rounded-lg border border-border p-4 space-y-2">
          <h2 className="text-sm font-medium">Nach Feature</h2>
          {Object.entries(data.by_feature).map(([feature, cost]) => (
            <div key={feature} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{feature}</span>
              <span>${cost.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-border p-4 space-y-3">
        <h2 className="text-sm font-medium">Letzte API-Calls</h2>
        <div className="space-y-1">
          {data.recent_calls.map((call, i) => (
            <div key={i} className="flex justify-between text-sm">
              <span className="text-muted-foreground">
                {call.feature} · {call.model}
              </span>
              <span>${call.cost_usd.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
