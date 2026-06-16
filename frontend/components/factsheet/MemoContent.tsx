import { Check, AlertTriangle, Zap, Sparkles } from 'lucide-react';

import type { Memo } from '@/lib/api/memos';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

const CONFIDENCE_VARIANT: Record<Memo['confidence'], 'default' | 'secondary' | 'outline'> = {
  high: 'default',
  medium: 'secondary',
  low: 'outline',
};

const CONFIDENCE_LABEL: Record<Memo['confidence'], string> = {
  high: 'Hohe Konfidenz',
  medium: 'Mittlere Konfidenz',
  low: 'Niedrige Konfidenz',
};

interface Props {
  memo: Memo;
}

export function MemoContent({ memo }: Props) {
  return (
    <div className="space-y-4" data-testid="memo-content">
      {/* Hero */}
      <Card>
        <CardContent className="py-4 flex items-start justify-between gap-3">
          <p className="text-base font-medium italic text-foreground/90 leading-snug">
            <span>&ldquo;{memo.one_liner}&rdquo;</span>
          </p>
          <Badge variant={CONFIDENCE_VARIANT[memo.confidence]} className="shrink-0">
            {CONFIDENCE_LABEL[memo.confidence]}
          </Badge>
        </CardContent>
      </Card>

      {/* Sweet-Spot conditional */}
      {memo.sweet_spot && memo.sweet_spot_explanation && (
        <Card className="border-pink-500/40 bg-pink-50/40 dark:bg-pink-950/20">
          <CardContent className="py-3 flex items-start gap-2">
            <Sparkles className="h-4 w-4 text-pink-600 dark:text-pink-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-pink-700 dark:text-pink-300">Sweet-Spot</p>
              <p className="text-sm text-muted-foreground mt-1">{memo.sweet_spot_explanation}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Strengths + Risks */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card>
          <CardContent className="py-3">
            <h3 className="text-sm font-semibold flex items-center gap-1.5 mb-2 text-emerald-700 dark:text-emerald-400">
              <Check className="h-4 w-4" /> Stärken
            </h3>
            <ul className="space-y-1 text-sm">
              {memo.key_strengths.map((s, i) => (
                <li key={i} className="text-muted-foreground">
                  &bull; <span>{s}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-3">
            <h3 className="text-sm font-semibold flex items-center gap-1.5 mb-2 text-orange-700 dark:text-orange-400">
              <AlertTriangle className="h-4 w-4" /> Risiken
            </h3>
            <ul className="space-y-1 text-sm">
              {memo.key_risks.map((r, i) => (
                <li key={i} className="text-muted-foreground">
                  &bull; <span>{r}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Contradictions conditional */}
      {memo.contradictions.length > 0 && (
        <Card>
          <CardContent className="py-3">
            <h3 className="text-sm font-semibold flex items-center gap-1.5 mb-2">
              <Zap className="h-4 w-4 text-amber-600" /> Widersprüche
            </h3>
            <ul className="space-y-2">
              {memo.contradictions.map((c, i) => (
                <li key={i} className="text-sm">
                  <span className="font-medium">
                    <span>{c.model_a}</span>{' '}
                    <span className="text-muted-foreground">↔</span>{' '}
                    <span>{c.model_b}</span>
                  </span>
                  <p className="text-muted-foreground mt-0.5">{c.description}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Interpretation */}
      <Card>
        <CardContent className="py-3">
          <h3 className="text-sm font-semibold mb-2">Interpretation</h3>
          <p className="text-sm text-muted-foreground whitespace-pre-line">
            {memo.ranking_interpretation}
          </p>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-xs text-muted-foreground flex justify-between pt-1 border-t">
        <span>Modell: {memo.model_version}</span>
        <span>Generiert am {new Date(memo.created_at).toLocaleDateString('de-CH', { dateStyle: 'medium' })}</span>
      </div>
    </div>
  );
}
