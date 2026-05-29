import { AlertTriangle, Loader2 } from 'lucide-react';

import type { Memo } from '@/lib/api/memos';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  memo: Memo;
  onRegenerate: () => void;
  isGenerating: boolean;
}

export function MemoErrorCard({ memo, onRegenerate, isGenerating }: Props) {
  return (
    <Card className="border-destructive/40 bg-destructive/5">
      <CardContent className="py-4 flex items-start gap-3">
        <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
        <div className="flex-1 space-y-2">
          <p className="text-sm font-medium text-destructive">
            Memo-Generierung ist fehlgeschlagen.
          </p>
          {memo.one_liner && (
            <p className="text-xs text-muted-foreground">{memo.one_liner}</p>
          )}
          <Button
            onClick={onRegenerate}
            disabled={isGenerating}
            variant="outline"
            size="sm"
            className="gap-2"
          >
            {isGenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {isGenerating ? 'Generieren…' : 'Erneut generieren'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
