'use client';

import { useQuery } from '@tanstack/react-query';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export function ApiStatusBadge() {
  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE_URL}/health`, { cache: 'no-store' });
      if (!res.ok) throw new Error('unhealthy');
      return res.json();
    },
    refetchInterval: 30_000,
    retry: 1,
    staleTime: 20_000,
  });

  const online = !!data && !isError;

  return (
    <span
      title={online ? 'API online' : 'API nicht erreichbar'}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground backdrop-blur"
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${online ? 'bg-emerald-400 shadow-[0_0_4px_#34d399]' : 'bg-red-400'}`}
      />
      API
    </span>
  );
}
