'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import type { EligibilityRead } from '@/lib/api/eligibility';

interface EligibilityPanelProps {
  data: EligibilityRead;
}

export function EligibilityPanel({ data }: EligibilityPanelProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          Säule 3a Eignung
          {data.eligible ? (
            <Badge variant="default" className="bg-green-600 text-white">
              3a-geeignet
            </Badge>
          ) : (
            <Badge variant="destructive">Nicht 3a-geeignet</Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {!data.eligible && data.reasons.length > 0 && (
          <ul className="list-disc pl-4 text-sm text-muted-foreground">
            {data.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
        <p className="text-xs text-muted-foreground border-t pt-2">{data.disclaimer}</p>
      </CardContent>
    </Card>
  );
}
