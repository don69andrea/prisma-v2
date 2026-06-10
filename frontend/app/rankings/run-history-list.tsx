'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { listRuns, statusLabel, type RankingRunStatus, type RunResponse } from '@/lib/api/runs';

const DATE_FMT = new Intl.DateTimeFormat('de-CH', {
  dateStyle: 'medium',
  timeStyle: 'short',
});


function statusBadgeVariant(status: RankingRunStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed': return 'default';
    case 'running':
    case 'pending':   return 'secondary';
    case 'failed':    return 'destructive';
  }
}

export function RunHistoryList() {
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([]);
  const [universeFilter, setUniverseFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const runsQuery = useQuery({
    queryKey: ['runs', 'history'],
    queryFn: () => listRuns(50, 0),
  });

  const universeNames = useMemo(() => {
    const names = new Set((runsQuery.data ?? []).map((r) => r.universe_name).filter(Boolean));
    return Array.from(names).sort();
  }, [runsQuery.data]);

  const visibleRuns = useMemo(() => {
    let all = runsQuery.data ?? [];
    if (universeFilter) all = all.filter((r) => r.universe_name === universeFilter);
    if (statusFilter) all = all.filter((r) => r.status === statusFilter);
    return all;
  }, [runsQuery.data, universeFilter, statusFilter]);

  function toggle(runId: string) {
    setSelected((prev) => {
      if (prev.includes(runId)) return prev.filter((id) => id !== runId);
      if (prev.length < 2) return [...prev, runId];
      return [prev[1], runId];
    });
  }

  function onCompare() {
    if (selected.length !== 2) return;
    router.push(`/rankings/compare?a=${selected[0]}&b=${selected[1]}`);
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-base font-medium">Vergangene Runs</CardTitle>
          <div className="flex items-center gap-2">
            {universeNames.length > 0 && (
              <select
                value={universeFilter}
                onChange={(e) => setUniverseFilter(e.target.value)}
                className="h-8 rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
                data-testid="run-history-universe-filter"
              >
                <option value="">Alle Universen</option>
                {universeNames.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            )}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-8 rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              data-testid="run-history-status-filter"
            >
              <option value="">Alle Status</option>
              <option value="completed">Abgeschlossen</option>
              <option value="running">Läuft</option>
              <option value="failed">Fehler</option>
            </select>
            <Button
              size="sm"
              onClick={onCompare}
              disabled={selected.length !== 2}
              aria-label="Vergleichen"
            >
              Vergleichen
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {runsQuery.isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        )}

        {runsQuery.data && runsQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground py-4">
            Noch keine Runs — starte deinen ersten oben.
          </p>
        )}

        {runsQuery.data && runsQuery.data.length > 0 && visibleRuns.length === 0 && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            Keine Runs für «{universeFilter}».
          </p>
        )}

        {visibleRuns.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>Datum</TableHead>
                <TableHead>Universe</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20 text-right">Aktion</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleRuns.map((run: RunResponse) => {
                const disabled = run.status !== 'completed';
                return (
                  <TableRow key={run.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={`Run ${run.id} auswählen`}
                        disabled={disabled}
                        checked={selected.includes(run.id)}
                        onChange={() => toggle(run.id)}
                        className="h-4 w-4 cursor-pointer disabled:cursor-not-allowed"
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {DATE_FMT.format(new Date(run.created_at))}
                    </TableCell>
                    <TableCell className="text-sm font-medium">{run.universe_name}</TableCell>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(run.status)}>
                        {statusLabel(run.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/rankings/${run.id}`}
                        className="text-sm text-primary hover:underline"
                      >
                        Öffnen
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
