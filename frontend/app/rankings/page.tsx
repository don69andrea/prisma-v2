import { Suspense } from 'react';
import type { Metadata } from 'next';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RankingsForm } from './rankings-form';
import { RunHistoryList } from './run-history-list';

export const metadata: Metadata = {
  title: 'Rankings',
};

export default function RankingsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ranking starten</h1>
        <p className="text-muted-foreground text-sm">
          Wähle ein Universum und starte einen Ranking-Run über alle 5 Modelle.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Neuer Run</CardTitle>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<div className="h-16 rounded-md bg-muted animate-pulse" />}>
            <RankingsForm />
          </Suspense>
        </CardContent>
      </Card>

      <RunHistoryList />
    </div>
  );
}
