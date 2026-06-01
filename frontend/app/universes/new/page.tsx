'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';
import { createUniverse } from '@/lib/api/universes';

export default function NewUniversePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [tickersRaw, setTickersRaw] = useState('');
  const [createdUniverse, setCreatedUniverse] = useState<{ id: string; name: string } | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createUniverse({
        name: name.trim(),
        region: region.trim(),
        tickers: tickersRaw
          .split(',')
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['universes'] });
      setCreatedUniverse({ id: data.id, name: data.name });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Neues Universum</h1>
        <p className="text-muted-foreground text-sm">
          Definiere einen Aktien-Pool für Ranking-Runs.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Universum-Details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="z.B. SMI"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="region" className="text-sm font-medium">
                Region
              </label>
              <Input
                id="region"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="z.B. CH, US, EU"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="tickers" className="text-sm font-medium">
                Ticker (kommagetrennt)
              </label>
              <textarea
                id="tickers"
                value={tickersRaw}
                onChange={(e) => setTickersRaw(e.target.value)}
                placeholder="z.B. NESN, NOVN, ROG"
                required
                rows={3}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
              />
              <p className="text-xs text-muted-foreground">
                Ticker werden automatisch in Grossbuchstaben umgewandelt.
              </p>
            </div>

            {mutation.isError && (
              <div className="flex items-center gap-2 text-destructive text-sm">
                <XCircle className="h-4 w-4 shrink-0" />
                <span>
                  {mutation.error instanceof Error
                    ? mutation.error.message
                    : 'Fehler beim Speichern'}
                </span>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? 'Speichern...' : 'Universum anlegen'}
              </Button>
              <Button variant="outline" asChild>
                <Link href="/universes">Abbrechen</Link>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <StartRankingDialog
        universe={createdUniverse}
        onClose={() => {
          setCreatedUniverse(null);
          router.push('/universes');
        }}
      />
    </div>
  );
}
