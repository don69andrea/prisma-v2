'use client';

import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';

import { getHealth } from '@/lib/api/health';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function HealthStatus() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    retry: 1,
    staleTime: 30 * 1000,
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">Backend-Status</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-3">
          {isLoading && (
            <>
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Verbinde...</span>
            </>
          )}
          {!isLoading && !isError && data && (
            <>
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <Badge variant="success">API verbunden</Badge>
              <span className="text-sm text-muted-foreground">{data.status}</span>
            </>
          )}
          {!isLoading && isError && (
            <>
              <XCircle className="h-4 w-4 text-destructive" />
              <Badge variant="destructive">API nicht erreichbar</Badge>
              <span className="text-sm text-muted-foreground">
                {error instanceof Error ? error.message : 'Verbindung fehlgeschlagen'}
              </span>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
