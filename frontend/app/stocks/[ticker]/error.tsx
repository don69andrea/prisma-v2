'use client';

import Link from 'next/link';

export default function StockDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-2xl py-16 text-center space-y-4">
      <p className="text-lg font-medium text-foreground">Seite konnte nicht geladen werden</p>
      <p className="text-sm text-muted-foreground">{error.message ?? 'Unbekannter Fehler'}</p>
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={reset}
          className="rounded-md px-4 py-2 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90"
        >
          Nochmal versuchen
        </button>
        <Link
          href="/discover"
          className="rounded-md px-4 py-2 text-sm font-medium border border-input hover:bg-accent"
        >
          Zurück zu Mein Universe
        </Link>
      </div>
    </div>
  );
}
