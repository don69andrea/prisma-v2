'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
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

  const runsQuery = useQuery({
    queryKey: ['runs', 'history'],
    queryFn: () => listRuns(10, 0),
  });

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
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium">Vergangene Runs</CardTitle>
        <Button
          size="sm"
          onClick={onCompare}
          disabled={selected.length !== 2}
          aria-label="Vergleichen"
        >
          Vergleichen
        </Button>
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

        {runsQuery.data && runsQuery.data.length > 0 && (
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
              {runsQuery.data.map((run: RunResponse) => {
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
