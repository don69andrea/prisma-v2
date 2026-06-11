import { cn } from '@/lib/utils';

const MESSAGES: Record<string, string[]> = {
  stock: [
    'PRISMA analysiert {ticker}…',
    'Quant-Scores werden berechnet…',
    'ML-Modell läuft…',
  ],
  rag: [
    'PRISMA liest den Jahresbericht…',
    'Relevante Abschnitte werden gesucht…',
  ],
  signal: [
    'Signal wird berechnet…',
    'Makro-Kontext wird einbezogen…',
  ],
  discover: [
    'PRISMA kuratiert dein Universe…',
    'Titel werden nach deinem Profil gefiltert…',
  ],
  explain: ['PRISMA erklärt…'],
  default: ['PRISMA lädt…'],
};

interface LoadingStateProps {
  type?: keyof typeof MESSAGES;
  ticker?: string;
  className?: string;
}

export function LoadingState({ type = 'default', ticker, className }: LoadingStateProps) {
  const msgs = MESSAGES[type] ?? MESSAGES.default;
  const msg  = msgs[0].replace('{ticker}', ticker ?? '…');

  return (
    <div className={cn('flex items-center gap-2 text-sm text-[#8b949e]', className)}>
      <span
        className="inline-block h-3.5 w-3.5 rounded-full border-2 border-[#58a6ff] border-t-transparent animate-spin"
        aria-hidden
      />
      <span>{msg}</span>
    </div>
  );
}

export function LoadingStateMulti({ type = 'default', ticker, className }: LoadingStateProps) {
  const msgs = MESSAGES[type] ?? MESSAGES.default;

  return (
    <div className={cn('space-y-1.5', className)} aria-live="polite">
      {msgs.map((m, i) => (
        <div
          key={m}
          className="flex items-center gap-2 text-sm text-[#8b949e] opacity-0 [animation:fadeIn_0.4s_ease-in_forwards]"
          style={{ animationDelay: `${i * 0.6}s` }}
        >
          <span className="h-1 w-1 rounded-full bg-[#58a6ff] shrink-0" aria-hidden />
          <span>{m.replace('{ticker}', ticker ?? '…')}</span>
        </div>
      ))}
    </div>
  );
}
