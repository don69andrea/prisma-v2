import { Suspense } from 'react';
import type { Metadata } from 'next';

import { DecisionClient } from './decision-client';

export const metadata: Metadata = {
  title: 'Signale',
};

export default function DecisionPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Decision Intelligence.</h1>
        <p className="text-sm text-muted-foreground mt-1">
          BUY / HOLD / SELL Signale — Quant 45% + ML 35% + Macro 20%
        </p>
      </div>
      <Suspense>
        <DecisionClient />
      </Suspense>
    </div>
  );
}
