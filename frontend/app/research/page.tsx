import type { Metadata } from 'next';
import { ResearchClient } from './research-client';

export const metadata: Metadata = { title: 'Research' };

export default function ResearchPage() {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">Research</h1>
      <p className="text-sm text-muted-foreground">
        Semantische Suche in SIX Jahresberichten und SEC Filings (pgvector)
      </p>
      <div className="pt-4">
        <ResearchClient />
      </div>
    </div>
  );
}
