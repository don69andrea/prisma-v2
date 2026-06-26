'use client';

// NEXT_PUBLIC_-Variablen werden zur Build-Zeit eingebettet — dieser Check läuft
// also im Browser-Bundle, nicht nur im Server-Log. Ohne sichtbaren Banner bleibt
// ein fehlender Key sonst nur eine console.warn, die niemand im UI bemerkt
// (siehe: Frontend lief tagelang ohne .env.local, alle Datenrouten -> 401).
const API_KEY = process.env.NEXT_PUBLIC_API_KEY;

export function MissingApiKeyBanner() {
  if (API_KEY) {
    return null;
  }

  return (
    <div className="sticky top-0 z-[60] w-full bg-red-600 px-4 py-2 text-center text-xs font-semibold text-white">
      ⚠ NEXT_PUBLIC_API_KEY ist nicht gesetzt — alle authentifizierten API-Aufrufe schlagen mit 401
      fehl. Lege <code className="font-mono">frontend/.env.local</code> an (siehe{' '}
      <code className="font-mono">.env.local.example</code>) und starte den Dev-Server neu.
    </div>
  );
}
