'use client';

import { useEffect, useState } from 'react';

import { subscribeColdStart } from '@/lib/api/cold-start-store';

/**
 * Globaler Hinweis-Banner für lange Erst-Requests (Render-Free-Tier Cold
 * Start, siehe Audit-Finding F-RENDER-2 / W-19). Abonniert den
 * cold-start-store, der von apiFetch() (lib/api/client.ts) zentral befüllt
 * wird — kein Pro-Seiten-Code nötig.
 */
export function ColdStartBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => subscribeColdStart(setVisible), []);

  if (!visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-4 left-4 z-[100] flex items-center gap-2 rounded-lg bg-amber-500/90 px-3 py-2 text-xs font-medium text-black shadow-lg max-w-xs"
    >
      <span
        className="inline-block h-2.5 w-2.5 rounded-full border-2 border-black/70 border-t-transparent animate-spin shrink-0"
        aria-hidden
      />
      <span>App startet…</span>
    </div>
  );
}
