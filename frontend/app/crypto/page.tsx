import { Suspense } from 'react';
import type { Metadata } from 'next';
import { CryptoClient } from './crypto-client';

export const metadata: Metadata = {
  title: 'Krypto',
};

export default function CryptoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Krypto.</h1>
        <p className="text-sm text-muted-foreground mt-1">
          10 Top-Kryptowährungen — technisch-sentimentale PRISMA-Signale in CHF
        </p>
      </div>
      <Suspense>
        <CryptoClient />
      </Suspense>
    </div>
  );
}
