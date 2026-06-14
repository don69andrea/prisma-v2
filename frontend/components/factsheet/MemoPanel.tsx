'use client';

import { FileText } from 'lucide-react';

import { useStockMemo } from '@/lib/hooks/useStockMemo';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { InfoTooltip } from '@/components/ui/InfoTooltip';
import { MemoContent } from './MemoContent';
import { MemoEmpty } from './MemoEmpty';
import { MemoErrorCard } from './MemoErrorCard';

interface Props {
  stockId: string;
  runId: string;
}

export function MemoPanel({ stockId, runId }: Props) {
  const { memo, isLoading, isError, error, generate, isGenerating } = useStockMemo(
    stockId,
    runId,
  );

  return (
    <Card data-testid="memo-card">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          KI-Analyse
          <InfoTooltip
            text="Dieser Bericht wurde von Claude (KI) automatisch aus Geschäftsberichten, Finanzdaten und Nachrichtenartikeln generiert. Er ersetzt keine professionelle Anlageberatung."
            side="top"
          />
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="space-y-3">
            <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
            <div className="h-4 w-full rounded bg-muted animate-pulse" />
            <div className="h-4 w-5/6 rounded bg-muted animate-pulse" />
            <div className="h-4 w-2/3 rounded bg-muted animate-pulse" />
          </div>
        )}
        {!isLoading && isError && (
          <p className="text-sm text-destructive" role="alert">
            Memo konnte nicht geladen werden: {error?.message ?? 'Unbekannter Fehler'}
          </p>
        )}
        {!isLoading && !isError && memo === null && (
          <MemoEmpty onGenerate={generate} isGenerating={isGenerating} />
        )}
        {!isLoading && !isError && memo && memo.is_error && (
          <MemoErrorCard memo={memo} onRegenerate={generate} isGenerating={isGenerating} />
        )}
        {!isLoading && !isError && memo && !memo.is_error && <MemoContent memo={memo} />}
      </CardContent>
    </Card>
  );
}
