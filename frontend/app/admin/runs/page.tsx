'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listRuns,
  createRun,
  getRankings,
  statusLabel,
  type RunResponse,
  type RankingItem,
} from '@/lib/api/runs';
import { listUniverses } from '@/lib/api/universes';

const STATUS_COLORS: Record<string, string> = {
  completed: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20',
  running: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  pending: 'bg-muted text-muted-foreground border-border',
  failed: 'bg-destructive/10 text-destructive border-destructive/20',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${STATUS_COLORS[status] ?? STATUS_COLORS.pending}`}>
      {statusLabel(status as 'pending' | 'running' | 'completed' | 'failed')}
    </span>
  );
}

function RankingsTable({ runId }: { runId: string }) {
  const { data, isLoading } = useQuery<RankingItem[]>({
    queryKey: ['rankings', runId],
    queryFn: () => getRankings(runId),
  });

  if (isLoading) return <p className="text-xs text-muted-foreground py-2">Lädt Rankings…</p>;
  if (!data?.length) return <p className="text-xs text-muted-foreground py-2">Keine Rankings gefunden.</p>;

  return (
    <table className="w-full text-xs mt-3">
      <thead>
        <tr className="border-b border-border text-muted-foreground text-left">
          <th className="pb-1 pr-3 font-medium">Rank</th>
          <th className="pb-1 pr-3 font-medium">Ticker</th>
          <th className="pb-1 pr-3 font-medium">Score</th>
          <th className="pb-1 font-medium">Sweet Spot</th>
        </tr>
      </thead>
      <tbody>
        {data.slice(0, 20).map((r, i) => (
          <tr key={i} className="border-b border-border/40 last:border-0">
            <td className="py-1 pr-3 font-mono">{r.total_rank ?? '—'}</td>
            <td className="py-1 pr-3 font-mono font-medium">{r.ticker}</td>
            <td className="py-1 pr-3">{r.weighted_avg != null ? r.weighted_avg.toFixed(2) : '—'}</td>
            <td className="py-1">{r.is_sweet_spot ? '✓' : ''}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function AdminRunsPage() {
  const qc = useQueryClient();
  const [selectedUniverse, setSelectedUniverse] = useState('');
  const [expandedRun, setExpandedRun] = useState<string | null>(null);

  const { data: runs, isLoading: runsLoading } = useQuery<RunResponse[]>({
    queryKey: ['admin-runs'],
    queryFn: () => listRuns(50),
  });

  const { data: universesData } = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
  });

  const triggerMutation = useMutation({
    mutationFn: () => createRun(selectedUniverse),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-runs'] });
      setSelectedUniverse('');
    },
  });

  const universes = universesData?.items ?? [];
  const completed = runs?.filter((r) => r.status === 'completed').length ?? 0;
  const failed = runs?.filter((r) => r.status === 'failed').length ?? 0;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Ranking-Runs</h1>

      {/* KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Total Runs</p>
          <p className="text-2xl font-bold mt-1">{runs?.length ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Abgeschlossen</p>
          <p className="text-2xl font-bold mt-1 text-emerald-500">{completed}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Fehlgeschlagen</p>
          <p className="text-2xl font-bold mt-1 text-destructive">{failed}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wide">Letzter Run</p>
          <p className="text-sm font-medium mt-1">
            {runs?.[0] ? new Date(runs[0].created_at).toLocaleDateString('de-CH') : '—'}
          </p>
        </div>
      </div>

      {/* Trigger New Run */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <h2 className="text-sm font-medium">Neuen Run starten</h2>
        <div className="flex gap-3 items-center">
          <select
            value={selectedUniverse}
            onChange={(e) => setSelectedUniverse(e.target.value)}
            className="text-sm px-3 py-2 rounded border border-border bg-background flex-1"
          >
            <option value="">Universum wählen…</option>
            {universes.map((u) => (
              <option key={u.id.toString()} value={u.id.toString()}>
                {u.name} ({u.tickers.length} Ticker)
              </option>
            ))}
          </select>
          <button
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending || !selectedUniverse}
            className="text-sm px-4 py-2 rounded bg-primary text-primary-foreground hover:opacity-90 disabled:opacity-50 whitespace-nowrap"
          >
            {triggerMutation.isPending ? 'Startet…' : 'Run starten'}
          </button>
        </div>
        {triggerMutation.isSuccess && (
          <p className="text-xs text-emerald-500">
            Run gestartet · ID: {triggerMutation.data?.id.slice(0, 8)}…
          </p>
        )}
        {triggerMutation.isError && (
          <p className="text-xs text-destructive">Fehler beim Starten des Runs.</p>
        )}
      </div>

      {/* Runs List */}
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <h2 className="text-sm font-medium">Run-Übersicht</h2>
        {runsLoading ? (
          <p className="text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="space-y-2">
            {runs?.map((run) => (
              <div key={run.id} className="border border-border/50 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{run.id.slice(0, 8)}…</span>
                      <StatusBadge status={run.status} />
                    </div>
                    <p className="text-sm">
                      {run.universe_name} ·{' '}
                      <span className="text-muted-foreground text-xs">
                        {new Date(run.created_at).toLocaleString('de-CH')}
                      </span>
                    </p>
                  </div>
                  {run.status === 'completed' && (
                    <button
                      onClick={() => setExpandedRun(expandedRun === run.id ? null : run.id)}
                      className="text-xs px-3 py-1 rounded border border-border hover:bg-muted"
                    >
                      {expandedRun === run.id ? 'Schliessen' : 'Rankings'}
                    </button>
                  )}
                </div>
                {expandedRun === run.id && <RankingsTable runId={run.id} />}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
