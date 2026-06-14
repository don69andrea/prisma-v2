import type { Metadata } from 'next';
import { SteuerClient } from './steuer-client';

export const metadata: Metadata = { title: 'Steuer' };

export default function SteuerPage() {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">Steuer-Implikationen.</h1>
      <p className="text-sm text-muted-foreground">
        Verrechnungssteuer, Einkommens- und Vermögenssteuer für CH-Aktienanlagen
      </p>
      <div className="pt-4">
        <SteuerClient />
      </div>
    </div>
  );
}
