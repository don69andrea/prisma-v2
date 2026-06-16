import { Suspense } from 'react';
import type { Metadata } from 'next';

import { DecisionClient } from './decision-client';

export const metadata: Metadata = {
  title: 'Signale',
};

export default function DecisionPage() {
  return (
    <Suspense>
      <DecisionClient />
    </Suspense>
  );
}
