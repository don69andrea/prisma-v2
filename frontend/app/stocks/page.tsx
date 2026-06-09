import type { Metadata } from 'next';
import { StocksListClient } from './stocks-list-client';

export const metadata: Metadata = { title: 'Aktien' };

export default function StocksPage() {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">Aktienuniversum</h1>
      <p className="text-sm text-muted-foreground">
        Alle Aktien im PRISMA-Universum — klicke für das Factsheet
      </p>
      <div className="pt-4">
        <StocksListClient />
      </div>
    </div>
  );
}
