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
      className="fixed inset-x-0 top-0 z-[100] flex items-center justify-center gap-2 bg-amber-500/95 px-4 py-2 text-center text-sm font-medium text-black shadow-md"
    >
      <span
        className="inline-block h-3 w-3 rounded-full border-2 border-black/70 border-t-transparent animate-spin shrink-0"
        aria-hidden
      />
      <span>App startet — kann beim ersten Aufruf bis zu einer Minute dauern…</span>
    </div>
  );
}
