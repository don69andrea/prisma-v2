'use client';

import Link from 'next/link';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center py-24 space-y-4 text-center">
      <p className="text-xl font-semibold text-foreground">Etwas ist schiefgelaufen</p>
      <p className="text-sm text-muted-foreground max-w-sm">
        {error.message ?? 'Ein unbekannter Fehler ist aufgetreten.'}
      </p>
      <div className="flex items-center gap-3">
        <button
          onClick={reset}
          className="rounded-md px-4 py-2 text-sm font-medium bg-primary text-primary-foreground hover:opacity-90"
        >
          Nochmal versuchen
        </button>
        <Link
          href="/"
          className="rounded-md px-4 py-2 text-sm font-medium border border-input hover:bg-accent"
        >
          Zum Dashboard
        </Link>
      </div>
    </div>
  );
}
