import type { Metadata } from 'next';
import { CryptoOverviewClient } from './crypto-overview-client';

export const metadata: Metadata = {
  title: 'Krypto-Signale — PRISMA',
};

export default function CryptoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Krypto-Signale.</h1>
        <p className="text-muted-foreground text-sm mt-1">
          BUY / HOLD / SELL Signale für das Top-10 Krypto-Universum · V4-1 Signal-Engine
        </p>
      </div>
      <CryptoOverviewClient />
    </div>
  );
}
