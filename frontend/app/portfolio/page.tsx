import type { Metadata } from 'next';

import { PortfolioClient } from './portfolio-client';

export const metadata: Metadata = {
  title: 'Portfolio Rebalancing',
};

export default function PortfolioPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Portfolio Rebalancing.</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Ist- vs. Soll-Gewichtungen — Rebalancing-Plan mit Transaktionskosten
        </p>
      </div>
      <PortfolioClient />
    </div>
  );
}
