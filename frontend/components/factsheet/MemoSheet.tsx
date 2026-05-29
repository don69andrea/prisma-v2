'use client';

import Link from 'next/link';
import { ExternalLink, Loader2 } from 'lucide-react';

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { useStockMemo } from '@/lib/hooks/useStockMemo';
import { MemoContent } from './MemoContent';
import { MemoEmpty } from './MemoEmpty';
import { MemoErrorCard } from './MemoErrorCard';

interface Props {
  stockId: string | null;
  runId: string;
  ticker: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MemoSheet({ stockId, runId, ticker, open, onOpenChange }: Props) {
  const { memo, isLoading, isError, error, generate, isGenerating } = useStockMemo(
    stockId,
    runId,
  );

  if (stockId === null) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-[640px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-2xl font-bold">{ticker}</SheetTitle>
          <SheetDescription>Research-Memo aus der Narrative-Engine</SheetDescription>
        </SheetHeader>

        <div className="mt-6 pb-6">
          {isLoading && (
            <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Memo wird geladen…</span>
            </div>
          )}

          {!isLoading && isError && (
            <div className="text-sm text-destructive py-4" role="alert">
              Memo konnte nicht geladen werden: {error?.message ?? 'Unbekannter Fehler'}
            </div>
          )}

          {!isLoading && !isError && memo === null && (
            <MemoEmpty onGenerate={generate} isGenerating={isGenerating} />
          )}

          {!isLoading && !isError && memo && memo.is_error && (
            <MemoErrorCard memo={memo} onRegenerate={generate} isGenerating={isGenerating} />
          )}

          {!isLoading && !isError && memo && !memo.is_error && <MemoContent memo={memo} />}
        </div>

        <div className="border-t pt-4">
          <Link
            href={`/rankings/${runId}/stock/${ticker}`}
            className="text-sm text-primary hover:underline inline-flex items-center gap-1"
          >
            Vollständiges Factsheet <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
