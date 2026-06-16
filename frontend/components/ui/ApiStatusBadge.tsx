'use client';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api/client';

export function ApiStatusBadge() {
  const { isSuccess } = useQuery({
    queryKey: ['api-status'],
    // Authentifizierter Call statt /health: /health prüft nur Infrastruktur-Liveness
    // und bleibt grün selbst wenn X-API-Key fehlt/falsch ist (alle Datenrouten -> 401).
    queryFn: () => apiFetch('/api/v1/universes'),
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 20_000,
  });

  const online = isSuccess;

  return (
    <span
      title={online ? 'API online & authentifiziert' : 'API nicht erreichbar oder X-API-Key ungültig'}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur"
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-emerald-400 shadow-[0_0_4px_#34d399]' : 'bg-red-400'}`}
      />
      API
    </span>
  );
}
