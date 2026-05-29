'use client';

import { FileText } from 'lucide-react';

import { useStockMemo } from '@/lib/hooks/useStockMemo';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          Research Memo
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <div className="h-24 rounded-lg bg-muted animate-pulse" />}
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
