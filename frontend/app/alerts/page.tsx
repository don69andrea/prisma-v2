import { Suspense } from 'react';
import type { Metadata } from 'next';

import { AlertsClient } from './alerts-client';

export const metadata: Metadata = {
  title: 'Alerts',
};

export default function AlertsPage() {
  return (
    <Suspense>
      <AlertsClient />
    </Suspense>
  );
}
