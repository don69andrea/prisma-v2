'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listAlerts, deleteAlert, type Alert } from '@/lib/api/alerts';

export default function AdminAlertsPage() {
  const qc = useQueryClient();
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-alerts'],
    queryFn: listAlerts,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteAlert(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-alerts'] });
      setConfirmDelete(null);
    },
  });

  const alerts: Alert[] = data?.alerts ?? [];
  const filtered = alerts.filter((a) => {
    if (activeFilter === 'active') return a.is_active;
    if (activeFilter === 'inactive') return !a.is_active;
    return true;
  });

  const activeCount = alerts.filter((a) => a.is_active).length;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Alerts</h1>

      {/* KPI */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Alerts</p>
          <p className="text-2xl font-bold mt-1">{alerts.length}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Aktiv</p>
          <p className="text-2xl font-bold mt-1 text-emerald-500">{activeCount}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Inaktiv</p>
          <p className="text-2xl font-bold mt-1 text-muted-foreground">{alerts.length - activeCount}</p>
        </div>
      </div>

      {/* Filter + Table */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium">Alert-Liste</h2>
          <div className="flex gap-1">
            {(['all', 'active', 'inactive'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`text-xs px-3 py-1 rounded border transition-colors ${
                  activeFilter === f
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'border-border hover:bg-muted'
                }`}
              >
                {f === 'all' ? 'Alle' : f === 'active' ? 'Aktiv' : 'Inaktiv'}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Lädt…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground">Keine Alerts gefunden.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">Ticker</th>
                  <th className="pb-2 pr-3 font-medium">Typ</th>
                  <th className="pb-2 pr-3 font-medium">Schwelle</th>
                  <th className="pb-2 pr-3 font-medium">Kanal</th>
                  <th className="pb-2 pr-3 font-medium">Ziel</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 pr-3 font-medium">Erstellt</th>
                  <th className="pb-2 pr-3 font-medium">Ausgelöst</th>
                  <th className="pb-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((a) => (
                  <tr key={a.id} className="border-b border-border/50 last:border-0">
                    <td className="py-2 pr-3 font-mono font-medium">{a.ticker}</td>
                    <td className="py-2 pr-3 text-muted-foreground text-xs">{a.trigger_type}</td>
                    <td className="py-2 pr-3 font-mono">{a.threshold}%</td>
                    <td className="py-2 pr-3 text-muted-foreground text-xs">{a.channel}</td>
                    <td className="py-2 pr-3 text-muted-foreground text-xs truncate max-w-[120px]">{a.target}</td>
                    <td className="py-2 pr-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full border ${
                          a.is_active
                            ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                            : 'bg-muted text-muted-foreground border-border'
                        }`}
                      >
                        {a.is_active ? 'Aktiv' : 'Inaktiv'}
                      </span>
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">
                      {new Date(a.created_at).toLocaleDateString('de-CH')}
                    </td>
                    <td className="py-2 pr-3 text-xs text-muted-foreground">
                      {a.last_triggered_at
                        ? new Date(a.last_triggered_at).toLocaleDateString('de-CH')
                        : '—'}
                    </td>
                    <td className="py-2">
                      {confirmDelete === a.id ? (
                        <div className="flex gap-1">
                          <button
                            onClick={() => deleteMutation.mutate(a.id)}
                            disabled={deleteMutation.isPending}
                            className="text-xs px-2 py-0.5 rounded bg-destructive text-destructive-foreground"
                          >
                            Ja
                          </button>
                          <button
                            onClick={() => setConfirmDelete(null)}
                            className="text-xs px-2 py-0.5 rounded border border-border"
                          >
                            Nein
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDelete(a.id)}
                          className="text-xs px-2 py-0.5 rounded border border-border hover:bg-destructive/10 hover:text-destructive hover:border-destructive/20 transition-colors"
                        >
                          Löschen
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
