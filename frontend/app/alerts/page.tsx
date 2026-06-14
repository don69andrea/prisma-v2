import { Suspense } from 'react';
import type { Metadata } from 'next';

import { AlertsClient } from './alerts-client';

export const metadata: Metadata = {
  title: 'Alerts',
};

export default function AlertsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Alerts.</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Kurs- und Signal-Benachrichtigungen für Swiss Stocks
        </p>
      </div>
      <Suspense>
        <AlertsClient />
      </Suspense>
    </div>
  );
}
