'use client';

import { useQuery } from '@tanstack/react-query';
import { ShieldCheck, ShieldX } from 'lucide-react';

import { getEligibility, type EligibilityReason } from '@/lib/api/eligibility';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

const REASON_LABELS: Record<EligibilityReason, string> = {
  exchange_not_recognized: 'Börse nicht BVV2-anerkannt (kein XSWX)',
  market_cap_too_low:      'Marktkapitalisierung < 100 Mio. CHF',
};

interface Props {
  ticker: string;
}

export function EligibilityPanel({ ticker }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['eligibility', ticker],
    queryFn: () => getEligibility(ticker),
    retry: false,
  });

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-4">
          <div className="h-12 rounded bg-muted animate-pulse" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !data) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          {data.eligible ? (
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
          ) : (
            <ShieldX className="h-4 w-4 text-muted-foreground" />
          )}
          Säule 3a Eignung
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2">
          {data.eligible ? (
            <Badge variant="success">3a-geeignet</Badge>
          ) : (
            <Badge variant="outline">Nicht 3a-geeignet</Badge>
          )}
          <span className="text-xs text-muted-foreground">
            {data.eligible
              ? 'Gemäss BVV2/FINMA-Regelwerk zulässig'
              : 'Nicht alle BVV2/FINMA-Kriterien erfüllt'}
          </span>
        </div>
        {!data.eligible && data.reasons.length > 0 && (
          <ul className="space-y-0.5">
            {data.reasons.map((r) => (
              <li key={r} className="flex gap-1.5 text-xs text-muted-foreground">
                <span>•</span>
                <span>{REASON_LABELS[r] ?? r}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="text-[10px] text-muted-foreground border-t pt-2">
          Regelbasiert (XSWX-Börse + ≥ 100 Mio. CHF Marktkap.) — keine Anlageberatung.
        </p>
      </CardContent>
    </Card>
  );
}
