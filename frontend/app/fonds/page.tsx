import type { Metadata } from 'next';

import { FondsClient } from './fonds-client';

export const metadata: Metadata = {
  title: 'Fonds-Vergleich',
};

export default function FondsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">VIAC Fonds-Vergleich</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Eigenes Portfolio vs. VIAC-Strategiefonds — Rendite, Volatilität, Sharpe
        </p>
      </div>
      <FondsClient />
    </div>
  );
}
