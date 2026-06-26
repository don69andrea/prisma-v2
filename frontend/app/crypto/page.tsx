import type { Metadata } from 'next';
import { CryptoClient } from './crypto-client';

export const metadata: Metadata = {
  title: 'Krypto — PRISMA',
};

export default function CryptoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Krypto.</h1>
        <p className="text-muted-foreground text-sm mt-1">
          10 Top-Kryptowährungen
        </p>
      </div>
      <CryptoClient />
    </div>
  );
}
