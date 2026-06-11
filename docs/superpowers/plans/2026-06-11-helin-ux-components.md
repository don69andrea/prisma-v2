# Helin UX Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drei UI-Aufgaben auf Branch `feature/helin-ux-components`: SignalBadge + PrismaScore + ExplainButton (R2.3-3), Glassmorphism Cards + LoadingState (R2.3-4), Navigation 5 Gruppen (R2.4-4).

**Architecture:** Alle neuen Komponenten unter `frontend/components/ui/`. PRISMA-Farben als eigene CSS-Custom-Properties in `globals.css` neben den bestehenden Tailwind-HSL-Vars. ExplainButton streamt via bestehendem SSE-Chat-Endpoint (`/api/v1/chat`). Navigation-Restrukturierung aktualisiert `nav-links.tsx` + bestehende Tests.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, Radix UI (Popover), lucide-react, CSS keyframe animations (kein framer-motion installiert)

---

## File Map

| Datei | Aktion |
|---|---|
| `frontend/app/globals.css` | Modify — PRISMA-Farbvars + `.glass-card` + `@keyframes pulse-glow` + `@keyframes typewriter` |
| `frontend/components/ui/SignalBadge.tsx` | Create — BUY/HOLD/WATCH Badge mit Glow |
| `frontend/components/ui/PrismaScore.tsx` | Create — Gradient-Score-Bar mit Label |
| `frontend/components/ui/ExplainButton.tsx` | Create — "?" Button → SSE-Stream → Typewriter-Popover |
| `frontend/components/ui/LoadingState.tsx` | Create — Smarte PRISMA-Lademeldungen |
| `frontend/app/nav-links.tsx` | Modify — Flat 14 Links → 5 Gruppen |
| `frontend/app/__tests__/nav-links.test.tsx` | Modify — Tests an neue Struktur anpassen |
| `frontend/app/layout.tsx` | Modify — `dark` Klasse auf `<html>` erzwingen |

---

## Task 1: PRISMA CSS-Vars + Dark Mode erzwingen

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: PRISMA-Farbvars + glass-card + Animationen in globals.css einfügen**

Füge **am Ende** von `frontend/app/globals.css` ein:

```css
/* ── PRISMA Design Tokens ─────────────────────────────── */
:root {
  --prisma-bg:        #0d1117;
  --prisma-surface:   #161b22;
  --prisma-border:    #21262d;
  --prisma-text:      #e6edf3;
  --prisma-muted:     #8b949e;
  --prisma-blue:      #58a6ff;
  --prisma-green:     #7ee787;
  --prisma-orange:    #ffa657;
  --prisma-red:       #f85149;
  --prisma-purple:    #bc8cff;
}

/* ── Glassmorphism Card ───────────────────────────────── */
.glass-card {
  background: rgba(22, 27, 34, 0.8);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(88, 166, 255, 0.15);
  border-radius: 16px;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

/* ── BUY Glow Pulse ───────────────────────────────────── */
@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 20px rgba(126, 231, 135, 0.4), 0 0 40px rgba(126, 231, 135, 0.15); }
  50%       { box-shadow: 0 0 28px rgba(126, 231, 135, 0.6), 0 0 56px rgba(126, 231, 135, 0.25); }
}

/* ── Typewriter für ExplainButton ────────────────────── */
@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
```

- [ ] **Step 2: `dark` Klasse auf `<html>` erzwingen**

In `frontend/app/layout.tsx` ändere:
```tsx
// Vorher:
<html lang="de" suppressHydrationWarning>

// Nachher:
<html lang="de" className="dark" suppressHydrationWarning>
```

- [ ] **Step 3: Committen**

```bash
cd /Users/andreapetretta/prisma-v2
git add frontend/app/globals.css frontend/app/layout.tsx
git commit -m "feat: PRISMA design tokens + dark mode force + glass-card class"
```

---

## Task 2: SignalBadge

**Files:**
- Create: `frontend/components/ui/SignalBadge.tsx`

- [ ] **Step 1: Komponente erstellen**

```tsx
// frontend/components/ui/SignalBadge.tsx
import { cn } from '@/lib/utils';
import { TrendingUp, Minus, Eye } from 'lucide-react';

export type SignalType = 'BUY' | 'HOLD' | 'WATCH' | 'SELL';

interface SignalBadgeProps {
  signal: SignalType;
  confidence?: number;
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
  className?: string;
}

const SIGNAL_CONFIG = {
  BUY: {
    bg:     'bg-[#0d2d1a]',
    text:   'text-[#7ee787]',
    border: 'border-[#7ee787]/30',
    label:  'BUY',
    Icon:   TrendingUp,
  },
  HOLD: {
    bg:     'bg-[#2d1a0d]',
    text:   'text-[#ffa657]',
    border: 'border-[#ffa657]/30',
    label:  'HOLD',
    Icon:   Minus,
  },
  WATCH: {
    bg:     'bg-[#0d1f3c]',
    text:   'text-[#58a6ff]',
    border: 'border-[#58a6ff]/30',
    label:  'BEOBACHTEN',
    Icon:   Eye,
  },
  SELL: {
    bg:     'bg-[#2d0d0d]',
    text:   'text-[#f85149]',
    border: 'border-[#f85149]/30',
    label:  'SELL',
    Icon:   TrendingUp,
  },
} satisfies Record<SignalType, { bg: string; text: string; border: string; label: string; Icon: React.ComponentType<{ className?: string }> }>;

const SIZE_CONFIG = {
  sm: { wrap: 'px-2 py-0.5 text-[10px] gap-1',   icon: 'h-2.5 w-2.5' },
  md: { wrap: 'px-3 py-1   text-xs     gap-1.5',  icon: 'h-3   w-3'   },
  lg: { wrap: 'px-4 py-1.5 text-sm     gap-2',    icon: 'h-3.5 w-3.5' },
};

export function SignalBadge({
  signal,
  confidence,
  size = 'md',
  animated = false,
  className,
}: SignalBadgeProps) {
  const cfg  = SIGNAL_CONFIG[signal] ?? SIGNAL_CONFIG.WATCH;
  const szcfg = SIZE_CONFIG[size];

  return (
    <div
      className={cn(
        'inline-flex items-center rounded-full border font-semibold tracking-wide',
        cfg.bg, cfg.text, cfg.border,
        szcfg.wrap,
        animated && signal === 'BUY' && '[animation:pulse-glow_2s_ease-in-out_infinite]',
        className,
      )}
    >
      <cfg.Icon className={cn(szcfg.icon, signal === 'SELL' && 'rotate-180')} aria-hidden />
      <span>{cfg.label}</span>
      {confidence !== undefined && (
        <span className="opacity-60 font-normal">
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Smoke-Test im Browser (nach npm run dev)**

Navigiere zu `/decision`. Die bestehenden Badges zeigen noch die alten Varianten — das ist OK für jetzt (wir tauschen sie in R2.3-4 aus). Kopiere kurz ins Browser-Console:
```js
// kein eigener Test nötig — Vitest-Test folgt in Step 3
```

- [ ] **Step 3: Unit-Test schreiben**

Erstelle `frontend/components/ui/__tests__/SignalBadge.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SignalBadge } from '../SignalBadge';

describe('SignalBadge', () => {
  it('zeigt BUY mit Konfidenz', () => {
    render(<SignalBadge signal="BUY" confidence={0.74} />);
    expect(screen.getByText('BUY')).toBeInTheDocument();
    expect(screen.getByText('74%')).toBeInTheDocument();
  });

  it('zeigt WATCH ohne Konfidenz', () => {
    render(<SignalBadge signal="WATCH" />);
    expect(screen.getByText('BEOBACHTEN')).toBeInTheDocument();
  });

  it('BUY mit animated hat pulse-Klasse', () => {
    const { container } = render(<SignalBadge signal="BUY" animated />);
    expect(container.firstChild).toHaveClass('[animation:pulse-glow_2s_ease-in-out_infinite]');
  });
});
```

- [ ] **Step 4: Tests ausführen**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/ui/__tests__/SignalBadge.test.tsx
```

Erwartet: 3 Tests grün.

- [ ] **Step 5: Committen**

```bash
git add frontend/components/ui/SignalBadge.tsx frontend/components/ui/__tests__/SignalBadge.test.tsx
git commit -m "feat: SignalBadge — BUY/HOLD/WATCH/SELL mit Glow und Konfidenz"
```

---

## Task 3: PrismaScore

**Files:**
- Create: `frontend/components/ui/PrismaScore.tsx`

- [ ] **Step 1: Komponente erstellen**

```tsx
// frontend/components/ui/PrismaScore.tsx
import { cn } from '@/lib/utils';

interface PrismaScoreProps {
  label: string;
  score: number;
  color?: 'green' | 'blue' | 'purple' | 'orange';
  showExplain?: boolean;
  onExplain?: () => void;
  className?: string;
}

const COLOR_GRADIENT: Record<NonNullable<PrismaScoreProps['color']>, string> = {
  green:  'from-[#f85149] via-[#ffa657] to-[#7ee787]',
  blue:   'from-[#f85149] via-[#ffa657] to-[#58a6ff]',
  purple: 'from-[#f85149] via-[#ffa657] to-[#bc8cff]',
  orange: 'from-[#f85149] via-[#ffa657] to-[#ffa657]',
};

function scoreColor(score: number): string {
  if (score >= 70) return 'text-[#7ee787]';
  if (score >= 40) return 'text-[#ffa657]';
  return 'text-[#f85149]';
}

export function PrismaScore({
  label,
  score,
  color = 'green',
  showExplain = false,
  onExplain,
  className,
}: PrismaScoreProps) {
  const pct = Math.max(0, Math.min(100, Math.round(score)));

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span className="text-xs text-[#8b949e] w-24 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-[#21262d] overflow-hidden">
        <div
          className={cn('h-full rounded-full bg-gradient-to-r', COLOR_GRADIENT[color])}
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${pct}`}
        />
      </div>
      <span className={cn('text-xs font-mono font-semibold w-7 text-right', scoreColor(pct))}>
        {pct}
      </span>
      {showExplain && (
        <button
          type="button"
          onClick={onExplain}
          aria-label={`${label} erklären`}
          className="text-[10px] text-[#8b949e] hover:text-[#58a6ff] transition-colors w-4 shrink-0"
        >
          ?
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Unit-Test**

Erstelle `frontend/components/ui/__tests__/PrismaScore.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PrismaScore } from '../PrismaScore';

describe('PrismaScore', () => {
  it('rendert Label und Score', () => {
    render(<PrismaScore label="Quality" score={82} />);
    expect(screen.getByText('Quality')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
  });

  it('progressbar hat aria-valuenow', () => {
    render(<PrismaScore label="Trend" score={61} />);
    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '61');
  });

  it('? Button ruft onExplain auf', () => {
    const onExplain = vi.fn();
    render(<PrismaScore label="Value" score={34} showExplain onExplain={onExplain} />);
    fireEvent.click(screen.getByRole('button', { name: /erklären/i }));
    expect(onExplain).toHaveBeenCalledOnce();
  });

  it('klemmt Score bei 0 und 100', () => {
    const { rerender } = render(<PrismaScore label="X" score={-5} />);
    expect(screen.getByText('0')).toBeInTheDocument();
    rerender(<PrismaScore label="X" score={150} />);
    expect(screen.getByText('100')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Tests laufen lassen**

```bash
npx vitest run components/ui/__tests__/PrismaScore.test.tsx
```

Erwartet: 4 Tests grün.

- [ ] **Step 4: Committen**

```bash
git add frontend/components/ui/PrismaScore.tsx frontend/components/ui/__tests__/PrismaScore.test.tsx
git commit -m "feat: PrismaScore — Gradient-Bar mit Accessibility + optionalem Explain-Button"
```

---

## Task 4: ExplainButton

**Files:**
- Create: `frontend/components/ui/ExplainButton.tsx`

Nutzt den bestehenden SSE-Endpoint `/api/v1/chat` mit einem festen System-Prompt für kurze deutsche Erklärungen.

- [ ] **Step 1: Komponente erstellen**

```tsx
// frontend/components/ui/ExplainButton.tsx
'use client';

import { useState, useRef } from 'react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { streamChat } from '@/lib/api/chat';

const CONTEXT_PROMPTS: Record<string, string> = {
  quality_score:       'Was bedeutet der Quality-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  trend_score:         'Was bedeutet der Trend-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  value_score:         'Was bedeutet der Value-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  macro_score:         'Was bedeutet der Makro-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  diversification:     'Was bedeutet Diversification-Score bei Aktien? Erkläre in max. 3 Sätzen auf Deutsch.',
  ml_prediction:       'Was bedeutet die ML-Prediction bei PRISMA? Erkläre in max. 3 Sätzen auf Deutsch.',
  confidence:          'Was bedeutet der Konfidenz-Wert bei PRISMA-Signalen? Erkläre in max. 3 Sätzen auf Deutsch.',
  signal:              'Was bedeutet BUY/HOLD/WATCH bei PRISMA? Erkläre in max. 3 Sätzen auf Deutsch.',
};

interface ExplainButtonProps {
  context: keyof typeof CONTEXT_PROMPTS | string;
  ticker?: string;
  label?: string;
  className?: string;
}

export function ExplainButton({
  context,
  ticker,
  label = '?',
  className,
}: ExplainButtonProps) {
  const [open, setOpen]       = useState(false);
  const [text, setText]       = useState('');
  const [loading, setLoading] = useState(false);
  const cancelRef             = useRef<(() => void) | null>(null);

  function handleOpen(isOpen: boolean) {
    setOpen(isOpen);
    if (!isOpen) {
      cancelRef.current?.();
      return;
    }
    if (text) return; // bereits geladen

    const prompt =
      CONTEXT_PROMPTS[context] ??
      `Was bedeutet "${context}"${ticker ? ` für ${ticker}` : ''}? Erkläre in max. 3 Sätzen auf Deutsch.`;

    setText('');
    setLoading(true);

    const cancel = streamChat(
      prompt,
      [],
      (event) => {
        if (event.type === 'token' && event.content) {
          setText((prev) => prev + event.content);
        }
      },
      () => setLoading(false),
      () => setLoading(false),
    );
    cancelRef.current = cancel;
  }

  return (
    <Popover open={open} onOpenChange={handleOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={`${context} erklären`}
          className={
            className ??
            'inline-flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold text-[#8b949e] hover:text-[#58a6ff] hover:bg-[#21262d] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#58a6ff]'
          }
        >
          {label}
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="max-w-xs text-sm leading-relaxed bg-[#161b22] border-[#21262d] text-[#e6edf3]"
        side="top"
      >
        {loading && !text && (
          <p className="text-[#8b949e] text-xs">PRISMA erklärt…</p>
        )}
        {text && (
          <p className="whitespace-pre-wrap">
            {text}
            {loading && (
              <span
                className="inline-block w-[1px] h-[1em] bg-[#58a6ff] ml-0.5 align-middle [animation:blink-cursor_1s_step-end_infinite]"
                aria-hidden
              />
            )}
          </p>
        )}
        {!loading && !text && (
          <p className="text-[#f85149] text-xs">Erklärung nicht verfügbar.</p>
        )}
        <p className="mt-2 text-[10px] text-[#8b949e] border-t border-[#21262d] pt-1.5">
          Erklärt von Claude Haiku
        </p>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 2: Unit-Test**

Erstelle `frontend/components/ui/__tests__/ExplainButton.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ExplainButton } from '../ExplainButton';

vi.mock('@/lib/api/chat', () => ({
  streamChat: vi.fn(() => () => {}),
}));

vi.mock('@/components/ui/popover', () => ({
  Popover: ({ children, onOpenChange }: { children: React.ReactNode; onOpenChange?: (v: boolean) => void }) => (
    <div onClick={() => onOpenChange?.(true)}>{children}</div>
  ),
  PopoverTrigger: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PopoverContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe('ExplainButton', () => {
  it('rendert den ? Button', () => {
    render(<ExplainButton context="quality_score" />);
    expect(screen.getByRole('button', { name: /erklären/i })).toBeInTheDocument();
  });

  it('ruft streamChat auf wenn geöffnet', async () => {
    const { streamChat } = await import('@/lib/api/chat');
    render(<ExplainButton context="quality_score" />);
    const btn = screen.getByRole('button', { name: /erklären/i });
    fireEvent.click(btn);
    expect(streamChat).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Tests laufen lassen**

```bash
npx vitest run components/ui/__tests__/ExplainButton.test.tsx
```

Erwartet: 2 Tests grün.

- [ ] **Step 4: Committen**

```bash
git add frontend/components/ui/ExplainButton.tsx frontend/components/ui/__tests__/ExplainButton.test.tsx
git commit -m "feat: ExplainButton — SSE-Streaming Typewriter-Popover auf Deutsch"
```

---

## Task 5: LoadingState

**Files:**
- Create: `frontend/components/ui/LoadingState.tsx`

- [ ] **Step 1: Komponente erstellen**

```tsx
// frontend/components/ui/LoadingState.tsx
import { cn } from '@/lib/utils';

const MESSAGES: Record<string, string[]> = {
  stock:    [
    'PRISMA analysiert {ticker}…',
    'Quant-Scores werden berechnet…',
    'ML-Modell läuft…',
  ],
  rag:      [
    'PRISMA liest den Jahresbericht…',
    'Relevante Abschnitte werden gesucht…',
  ],
  signal:   [
    'Signal wird berechnet…',
    'Makro-Kontext wird einbezogen…',
  ],
  discover: [
    'PRISMA kuratiert dein Universe…',
    'Titel werden nach deinem Profil gefiltert…',
  ],
  explain:  ['PRISMA erklärt…'],
  default:  ['PRISMA lädt…'],
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
          className="flex items-center gap-2 text-sm text-[#8b949e] opacity-0 animate-[fadeIn_0.4s_ease-in_forwards]"
          style={{ animationDelay: `${i * 0.6}s` }}
        >
          <span className="h-1 w-1 rounded-full bg-[#58a6ff] shrink-0" aria-hidden />
          <span>{m.replace('{ticker}', ticker ?? '…')}</span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: `fadeIn` Keyframe in globals.css ergänzen**

Füge am Ende des PRISMA-Blocks in `globals.css` hinzu:

```css
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0);   }
}
```

- [ ] **Step 3: Unit-Test**

Erstelle `frontend/components/ui/__tests__/LoadingState.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingState } from '../LoadingState';

describe('LoadingState', () => {
  it('zeigt Stock-Meldung mit Ticker', () => {
    render(<LoadingState type="stock" ticker="NESN.SW" />);
    expect(screen.getByText('PRISMA analysiert NESN.SW…')).toBeInTheDocument();
  });

  it('zeigt Default-Meldung', () => {
    render(<LoadingState />);
    expect(screen.getByText('PRISMA lädt…')).toBeInTheDocument();
  });

  it('kein "Loading..." Text vorhanden', () => {
    render(<LoadingState type="signal" />);
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Tests laufen lassen**

```bash
npx vitest run components/ui/__tests__/LoadingState.test.tsx
```

Erwartet: 3 Tests grün.

- [ ] **Step 5: Committen**

```bash
git add frontend/components/ui/LoadingState.tsx frontend/components/ui/__tests__/LoadingState.test.tsx frontend/app/globals.css
git commit -m "feat: LoadingState — smarte PRISMA-Lademeldungen statt 'Loading...'"
```

---

## Task 6: SignalCard mit Glassmorphism in /decision

Tauscht die bestehenden Karten auf der Decision-Seite auf `glass-card` + `SignalBadge` um.

**Files:**
- Modify: `frontend/app/decision/decision-client.tsx`

- [ ] **Step 1: Imports anpassen und SignalCard updaten**

Ersetze in `frontend/app/decision/decision-client.tsx` die bestehende `SignalCard`-Funktion und den `SIGNAL_CONFIG`-Block (Zeilen ~18–75 ca.):

```tsx
// Neue Imports oben einfügen (zusätzlich zu bestehenden):
import { SignalBadge } from '@/components/ui/SignalBadge';

// SIGNAL_CONFIG-Konstante ENTFERNEN (wird nicht mehr gebraucht)

// SignalCard-Funktion ersetzen:
function SignalCard({ item }: { item: DecisionSignal }) {
  return (
    <div className="glass-card p-4 space-y-3 hover:border-[#58a6ff]/30 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div>
          <Link
            href={`/stocks/${item.ticker}`}
            className="font-semibold text-base leading-none text-[#e6edf3] hover:text-[#58a6ff] transition-colors"
          >
            {item.ticker}
          </Link>
          <p className="text-xs text-[#8b949e] mt-0.5">
            {new Date(item.snapshot_date).toLocaleDateString('de-CH', { dateStyle: 'short' })}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <SignalBadge
            signal={item.signal as 'BUY' | 'HOLD' | 'WATCH'}
            confidence={item.confidence}
            animated={item.signal === 'BUY'}
          />
          {item.is_3a_eligible && (
            <span className="text-[10px] text-[#8b949e] border border-[#21262d] rounded px-1.5 py-0.5">
              3a
            </span>
          )}
        </div>
      </div>

      <ConfidenceBar value={item.confidence} />

      <div className="grid grid-cols-3 gap-1 text-[11px]">
        <div className="text-center">
          <p className="text-[#8b949e]">Quant</p>
          <p className="font-medium text-[#e6edf3]">{item.quant_score.toFixed(1)}</p>
        </div>
        <div className="text-center">
          <p className="text-[#8b949e]">ML</p>
          <p className="font-medium text-[#e6edf3]">{item.ml_score.toFixed(0)}</p>
        </div>
        <div className="text-center">
          <p className="text-[#8b949e]">Macro</p>
          <p className="font-medium text-[#e6edf3]">{item.macro_score.toFixed(0)}</p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Manuell prüfen (dev server)**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npm run dev
```

Öffne `http://localhost:3000/decision`. Prüfen:
- Karten haben Glassmorphism-Effekt (blur, semi-transparent background)
- BUY-Badges glühen grün
- HOLD-Badges sind orange
- Kein "Loading..." Text

- [ ] **Step 3: Committen**

```bash
git add frontend/app/decision/decision-client.tsx
git commit -m "feat: /decision SignalCards auf Glassmorphism + SignalBadge migriert"
```

---

## Task 7: Navigation — 5 Gruppen

**Files:**
- Modify: `frontend/app/nav-links.tsx`
- Modify: `frontend/app/__tests__/nav-links.test.tsx`

- [ ] **Step 1: nav-links.tsx umschreiben**

Ersetze den gesamten Inhalt von `frontend/app/nav-links.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { ROUTES } from '@/lib/routes';

const NAV_GROUPS = [
  {
    label: 'ENTDECKEN',
    links: [
      { href: ROUTES.start,    label: 'Einstieg' },
      { href: ROUTES.universes, label: 'Universe' },
      { href: ROUTES.rankings, label: 'Rankings' },
    ],
  },
  {
    label: 'VERSTEHEN',
    links: [
      { href: ROUTES.stocks,   label: 'Aktien' },
      { href: ROUTES.news,     label: 'News' },
      { href: ROUTES.research, label: 'Research' },
    ],
  },
  {
    label: 'VERGLEICHEN',
    links: [
      { href: ROUTES.backtest, label: 'Backtest' },
      { href: ROUTES.fonds,    label: 'Fonds' },
    ],
  },
  {
    label: 'ENTSCHEIDEN',
    links: [
      { href: ROUTES.decision, label: 'Signale' },
      { href: ROUTES.alerts,   label: 'Alerts' },
    ],
  },
  {
    label: 'PORTFOLIO',
    links: [
      { href: ROUTES.portfolio,  label: 'Portfolio' },
      { href: ROUTES.simulator,  label: '3a Sim' },
      { href: ROUTES.steuer,     label: 'Steuer' },
    ],
  },
] as const;

function isActive(href: string, pathname: string): boolean {
  if (href === ROUTES.dashboard) return pathname === ROUTES.dashboard;
  return pathname.startsWith(href);
}

export function NavLinks() {
  const pathname = usePathname();

  return (
    <nav className="flex items-start gap-6 overflow-x-auto scrollbar-none pb-0.5" aria-label="Hauptnavigation">
      {NAV_GROUPS.map((group) => (
        <div key={group.label} className="flex flex-col gap-1 shrink-0">
          <span className="text-[9px] font-semibold tracking-[0.12em] text-[#8b949e] uppercase px-1">
            {group.label}
          </span>
          <div className="flex items-center gap-3">
            {group.links.map((link) => {
              const active = isActive(link.href, pathname);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'text-sm shrink-0 transition-colors hover:text-foreground px-1',
                    active
                      ? 'text-foreground font-medium border-b border-[#58a6ff]'
                      : 'text-muted-foreground',
                  )}
                >
                  {link.label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Tests aktualisieren**

Ersetze den Inhalt von `frontend/app/__tests__/nav-links.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('next/navigation', () => ({
  usePathname: vi.fn(),
}));
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

import { usePathname } from 'next/navigation';
import { NavLinks } from '../nav-links';

describe('NavLinks', () => {
  it('zeigt alle 5 Gruppenbezeichnungen', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    expect(screen.getByText('ENTDECKEN')).toBeInTheDocument();
    expect(screen.getByText('VERSTEHEN')).toBeInTheDocument();
    expect(screen.getByText('VERGLEICHEN')).toBeInTheDocument();
    expect(screen.getByText('ENTSCHEIDEN')).toBeInTheDocument();
    expect(screen.getByText('PORTFOLIO')).toBeInTheDocument();
  });

  it('hebt den aktiven Link hervor und setzt aria-current', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings');
    render(<NavLinks />);
    const active = screen.getByRole('link', { name: 'Rankings' });
    expect(active).toHaveAttribute('aria-current', 'page');
    expect(active.className).toContain('text-foreground');
  });

  it('matched verschachtelte Pfade — /rankings/abc aktiviert Rankings', () => {
    vi.mocked(usePathname).mockReturnValue('/rankings/some-run-id');
    render(<NavLinks />);
    expect(screen.getByRole('link', { name: 'Rankings' })).toHaveAttribute('aria-current', 'page');
  });

  it('Signale-Link ist in Gruppe ENTSCHEIDEN', () => {
    vi.mocked(usePathname).mockReturnValue('/');
    render(<NavLinks />);
    const signaleLink = screen.getByRole('link', { name: 'Signale' });
    expect(signaleLink).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Tests laufen lassen**

```bash
npx vitest run app/__tests__/nav-links.test.tsx
```

Erwartet: 4 Tests grün.

- [ ] **Step 4: Visuell prüfen**

```bash
npm run dev
```

Navigiere zu `http://localhost:3000`. Prüfen:
- Gruppenbezeichnungen (ENTDECKEN, VERSTEHEN, ...) sichtbar in Grau
- Links darunter, aktiver Link hat blauen Unterstrich
- Alle bestehenden Seiten noch erreichbar

- [ ] **Step 5: Committen**

```bash
git add frontend/app/nav-links.tsx frontend/app/__tests__/nav-links.test.tsx
git commit -m "feat: Navigation — 14 flache Links zu 5 semantischen Gruppen restrukturiert"
```

---

## Task 8: Full Test Suite + Push

- [ ] **Step 1: Alle Tests ausführen**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run
```

Erwartet: alle Tests grün, keine Regressions.

- [ ] **Step 2: TypeScript-Check**

```bash
npx tsc --noEmit
```

Erwartet: keine Fehler.

- [ ] **Step 3: CLAUDE.md Status updaten**

In `/Users/andreapetretta/CLAUDE.md` setze R2.3-3, R2.3-4 und R2.4-4 auf `✅ DONE`.

- [ ] **Step 4: Branch pushen**

```bash
cd /Users/andreapetretta/prisma-v2
git push -u origin feature/helin-ux-components
```

---

## Self-Review Checklist

- [x] SignalBadge: BUY/HOLD/WATCH/SELL mit Farben, Glow, Konfidenz, animierter Puls ✓
- [x] PrismaScore: Gradient-Bar, aria-progressbar, ? Button, Score-Klemmung ✓
- [x] ExplainButton: SSE-Streaming, Typewriter-Cursor, Fallback, "Claude Haiku" Attribution ✓
- [x] LoadingState: Kein "Loading...", PRISMA-spezifische Texte, Ticker-Interpolation ✓
- [x] Decision-Karte: glass-card + SignalBadge Integration ✓
- [x] Navigation: 5 Gruppen, Tests aktualisiert, aria-current korrekt ✓
- [x] Dark Mode: `dark` Klasse auf `<html>` erzwungen ✓
- [x] CSS-Vars: `--prisma-*` ergänzt, bestehende Tailwind-HSL-Vars unangetastet ✓
- [x] Framer-Motion: nicht nötig — CSS animations ausreichend ✓
- [x] Alle Texte Deutsch (HOLD-Tooltip, WATCH → BEOBACHTEN) ✓
