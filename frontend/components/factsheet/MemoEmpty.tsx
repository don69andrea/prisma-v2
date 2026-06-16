import { FileText, Loader2, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';

interface Props {
  onGenerate: () => void;
  isGenerating: boolean;
}

export function MemoEmpty({ onGenerate, isGenerating }: Props) {
  return (
    <div className="flex flex-col items-center gap-4 py-8 text-center">
      <div className="rounded-full bg-muted p-4">
        <FileText className="h-8 w-8 text-muted-foreground/60" />
      </div>
      {isGenerating ? (
        <>
          <div className="space-y-1">
            <p className="text-sm font-medium">KI-Analyse wird erstellt…</p>
            <p className="text-xs text-muted-foreground">Das dauert in der Regel 5–15 Sekunden.</p>
          </div>
          <div className="space-y-2 w-full max-w-sm">
            <div className="h-3 w-full rounded-full bg-muted animate-pulse" />
            <div className="h-3 w-5/6 rounded-full bg-muted animate-pulse" />
            <div className="h-3 w-4/5 rounded-full bg-muted animate-pulse" />
          </div>
          <Button disabled variant="outline" size="sm" className="gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Analyse wird erstellt…
          </Button>
        </>
      ) : (
        <>
          <div className="space-y-1">
            <p className="text-sm font-medium">Noch kein Analysebericht vorhanden</p>
            <p className="text-xs text-muted-foreground max-w-xs">
              Generiere eine KI-gestützte Analyse mit Stärken, Risiken und Interpretation — basierend auf Finanzdaten und Nachrichten.
            </p>
          </div>
          <Button onClick={onGenerate} size="sm" className="gap-2">
            <Sparkles className="h-4 w-4" />
            KI-Analyse generieren
          </Button>
        </>
      )}
    </div>
  );
}
