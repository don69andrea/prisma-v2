'use client';

import { useQuery } from '@tanstack/react-query';

export function ApiStatusBadge() {
  const { data, isError } = useQuery({
    queryKey: ['api-health'],
    queryFn: async () => {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? ''}/health`);
      if (!res.ok) throw new Error('unhealthy');
      return res.json() as Promise<{ status: string }>;
    },
    refetchInterval: 30_000,
    retry: false,
  });

  const ok = !isError && data?.status === 'ok';
  return (
    <span className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`} title={ok ? 'API online' : 'API offline'} />
  );
}
