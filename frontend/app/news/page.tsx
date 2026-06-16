import type { Metadata } from 'next';
import { NewsClient } from './news-client';

export const metadata: Metadata = { title: 'News' };

export default function NewsPage() {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">News.</h1>
      <p className="text-sm text-muted-foreground">
        Was heute relevant ist — für dein Universum.
      </p>
      <div className="pt-4">
        <NewsClient />
      </div>
    </div>
  );
}
