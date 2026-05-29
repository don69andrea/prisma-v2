'use client';

import Link from 'next/link';
import { Plus, Sparkles, XCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { listUniverses } from '@/lib/api/universes';
import { UniverseList } from './universe-list';

function UniverseSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-12 rounded-md bg-muted animate-pulse" />
      ))}
    </div>
  );
}

export default function UniversesPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
    staleTime: 30 * 1000,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Universen</h1>
          <p className="text-muted-foreground text-sm">
            Aktien-Universen verwalten — Basis für jeden Ranking-Run.
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline">
            <Link href="/universes/wizard">
              <Sparkles className="mr-2 h-4 w-4" />
              Mit KI generieren
            </Link>
          </Button>
          <Button asChild>
            <Link href="/universes/new">
              <Plus className="mr-2 h-4 w-4" />
              Neues Universum
            </Link>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Vorhandene Universen</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <UniverseSkeleton />}

          {isError && (
            <div className="flex items-center gap-2 text-destructive text-sm py-4">
              <XCircle className="h-4 w-4 shrink-0" />
              <span>
                Universen konnten nicht geladen werden:{' '}
                {error instanceof Error ? error.message : 'Unbekannter Fehler'}
              </span>
            </div>
          )}

          {!isLoading && !isError && data && <UniverseList universes={data.items} />}
        </CardContent>
      </Card>
    </div>
  );
}
