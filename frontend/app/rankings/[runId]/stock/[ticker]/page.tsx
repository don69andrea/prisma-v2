import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import { FactsheetView } from './factsheet-view';

interface PageProps {
  params: { runId: string; ticker: string };
}

export function generateMetadata({ params }: PageProps): Metadata {
  return {
    title: `${params.ticker.toUpperCase()} — PRISMA Factsheet`,
  };
}

export default function FactsheetPage({ params }: PageProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <Link
          href={`/rankings/${params.runId}`}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Zurück zum Ranking
        </Link>
        <h1 className="text-2xl font-bold tracking-tight sr-only">
          {params.ticker.toUpperCase()} Factsheet
        </h1>
      </div>

      <FactsheetView runId={params.runId} ticker={params.ticker.toUpperCase()} />
    </div>
  );
}
