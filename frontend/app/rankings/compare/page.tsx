import { Suspense } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import type { Metadata } from 'next';

import { CompareClient } from './compare-client';

export const metadata: Metadata = {
  title: 'Run-Vergleich',
};

function PageSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-24 rounded-md bg-muted animate-pulse" />
      <div className="h-64 rounded-md bg-muted animate-pulse" />
    </div>
  );
}

export default function ComparePage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="space-y-2">
        <Link
          href="/rankings"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Zurück
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Run-Vergleich.</h1>
      </div>

      <Suspense fallback={<PageSkeleton />}>
        <CompareClient />
      </Suspense>
    </div>
  );
}
