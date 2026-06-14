'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { PrismaBar } from '@/components/ui/PrismaBar';
import { InfoPopover } from '@/components/InfoPopover';
import { listUniverses } from '@/lib/api/universes';
import { createRun } from '@/lib/api/runs';

export function RankingsForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [universeId, setUniverseId] = useState<string>(
    searchParams.get('universeId') ?? '',
  );

  const universesQuery = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
    staleTime: 30 * 1000,
  });

  const mutation = useMutation({
    mutationFn: () => createRun(universeId),
    onSuccess: (run) => router.push(`/rankings/${run.id}`),
  });

  const isPending = mutation.isPending;
  const disabled = !universeId || isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled) mutation.mutate();
      }}
    >
      <div className="space-y-1">
        <div className="inline-flex items-center gap-1">
          <label htmlFor="universe" className="text-sm font-medium">Universe</label>
          <InfoPopover ariaLabel="Mehr Informationen">
            <p>Ein Universum ist eine definierte Auswahl von Aktien die analysiert werden sollen. z.B. alle SMI-Titel</p>
          </InfoPopover>
        </div>
        <select
          id="universe"
          value={universeId}
          onChange={(e) => setUniverseId(e.target.value)}
          disabled={isPending || universesQuery.isLoading}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">— wählen —</option>
          {universesQuery.data?.items.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
      </div>

      {universesQuery.isError && (
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            Universen konnten nicht geladen werden:{' '}
            {universesQuery.error instanceof Error
              ? universesQuery.error.message
              : 'Unbekannter Fehler'}
          </span>
        </div>
      )}

      {mutation.isError && (
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            {mutation.error instanceof Error
              ? mutation.error.message
              : 'Run konnte nicht gestartet werden'}
          </span>
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button type="submit" disabled={disabled} aria-busy={isPending}>
          {isPending ? 'Run wird gestartet…' : 'Run starten'}
        </Button>
        <InfoPopover ariaLabel="Ranking-Run erklären">
          <p>Ein Run ist eine Berechnung die alle Aktien im Universum bewertet und einen Score vergibt</p>
        </InfoPopover>
      </div>
      {isPending && <PrismaBar />}
    </form>
  );
}
