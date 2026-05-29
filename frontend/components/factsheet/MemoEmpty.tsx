import { FileText, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  onGenerate: () => void;
  isGenerating: boolean;
}

export function MemoEmpty({ onGenerate, isGenerating }: Props) {
  return (
    <Card className="border-dashed">
      <CardContent className="py-10 flex flex-col items-center gap-3 text-center">
        <FileText className="h-10 w-10 text-muted-foreground/40" />
        {isGenerating ? (
          <>
            <p className="text-sm text-muted-foreground">Memo wird generiert (5-15s)…</p>
            <Button disabled variant="outline" size="sm" className="gap-2">
              <Loader2 className="h-4 w-4 animate-spin" /> Generieren…
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">Noch kein Memo für diesen Stock.</p>
            <Button onClick={onGenerate} size="sm">
              Memo generieren
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
