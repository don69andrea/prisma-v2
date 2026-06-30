import type { Metadata } from 'next';
import { CryptoOverviewClient } from './crypto-overview-client';
import { CryptoClient } from './crypto-client';

export const metadata: Metadata = {
  title: 'Krypto-Signale — PRISMA',
};

export default function CryptoPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Krypto-Signale.</h1>
        <p className="text-muted-foreground text-sm mt-1">
          BUY / HOLD / SELL Signale für das Top-10 Krypto-Universum · V4-1 Signal-Engine
        </p>
      </div>

      {/* V4-1 Signal-Engine Dashboard */}
      <CryptoOverviewClient />

      {/* Marktübersicht: Fear & Greed + Score-Breakdown */}
      <div className="border-t border-border/40 pt-6">
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">
          Marktübersicht
        </h2>
        <CryptoClient />
      </div>
    </div>
  );
}
