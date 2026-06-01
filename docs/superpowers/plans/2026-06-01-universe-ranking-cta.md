# Universe → Ranking CTA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nach dem Anlegen eines Universums erscheint ein Dialog, der fragt ob direkt ein Ranking gestartet werden soll; zusätzlich bekommt jede Zeile in der Universumsliste einen "Ranking starten"-Button.

**Architecture:** Ein neues `StartRankingDialog`-Component (Dialog-Primitive aus Radix) übernimmt die Mutation `createRun → router.push('/rankings/<id>')`. Beide Erstellungsseiten (`new/page.tsx`, `wizard/page.tsx`) tauschen ihren `router.push('/universes')` onSuccess gegen `setCreatedUniverse(data)` aus. `UniverseList` wird Client-Component und rendert den Dialog ebenfalls.

**Tech Stack:** Next.js 14 App Router, React, `@radix-ui/react-dialog` (bereits installiert), `@tanstack/react-query`, Vitest + React Testing Library

---

## File Map

| Aktion | Pfad |
|---|---|
| **Neu** | `frontend/components/ui/dialog.tsx` |
| **Neu** | `frontend/components/universes/StartRankingDialog.tsx` |
| **Neu** | `frontend/components/universes/__tests__/StartRankingDialog.test.tsx` |
| **Ändern** | `frontend/app/universes/new/page.tsx` |
| **Ändern** | `frontend/app/universes/wizard/page.tsx` |
| **Ändern** | `frontend/app/universes/universe-list.tsx` |
| **Ändern** | `frontend/app/universes/__tests__/universe-list.test.tsx` |

---

## Task 1: Dialog UI-Primitive erstellen

**Files:**
- Create: `frontend/components/ui/dialog.tsx`

- [ ] **Step 1: Datei erstellen**

```tsx
// frontend/components/ui/dialog.tsx
"use client"

import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"

const Dialog = DialogPrimitive.Root
const DialogTrigger = DialogPrimitive.Trigger
const DialogPortal = DialogPrimitive.Portal
const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
        className
      )}
      {...props}
    >
      {children}
      <DialogClose className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
        <X className="h-4 w-4" />
        <span className="sr-only">Schliessen</span>
      </DialogClose>
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitive.Content.displayName

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props} />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props} />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
))
DialogTitle.displayName = DialogPrimitive.Title.displayName

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
DialogDescription.displayName = DialogPrimitive.Description.displayName

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ui/dialog.tsx
git commit -m "feat(frontend): Dialog UI-Primitive (Radix)"
```

---

## Task 2: StartRankingDialog Component + Tests

**Files:**
- Create: `frontend/components/universes/StartRankingDialog.tsx`
- Create: `frontend/components/universes/__tests__/StartRankingDialog.test.tsx`

- [ ] **Step 1: Failing Test schreiben**

```tsx
// frontend/components/universes/__tests__/StartRankingDialog.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { StartRankingDialog } from '../StartRankingDialog';
import type { RunResponse } from '@/lib/api/runs';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockCreateRun = vi.fn();
vi.mock('@/lib/api/runs', () => ({
  createRun: (id: string) => mockCreateRun(id),
}));

const sampleRun: RunResponse = {
  id: 'run-99',
  status: 'pending',
  universe_id: 'u-1',
  universe_name: 'SMI',
  created_at: '2026-06-01T10:00:00Z',
};

function renderDialog(universe: { id: string; name: string } | null, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <StartRankingDialog universe={universe} onClose={onClose} />
    </QueryClientProvider>
  );
}

describe('StartRankingDialog', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockCreateRun.mockReset();
  });

  it('rendert nichts wenn universe null ist', () => {
    renderDialog(null);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('zeigt Universum-Namen und Ja/Nein-Buttons', () => {
    renderDialog({ id: 'u-1', name: 'SMI' });
    expect(screen.getByText(/SMI/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ja/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Nein/i })).toBeInTheDocument();
  });

  it('Ja-Klick ruft createRun auf und navigiert zu /rankings/<id>', async () => {
    mockCreateRun.mockResolvedValue(sampleRun);
    renderDialog({ id: 'u-1', name: 'SMI' });
    fireEvent.click(screen.getByRole('button', { name: /Ja/i }));
    await waitFor(() => expect(mockCreateRun).toHaveBeenCalledWith('u-1'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/rankings/run-99'));
  });

  it('Nein-Klick ruft onClose auf', () => {
    const onClose = vi.fn();
    renderDialog({ id: 'u-1', name: 'SMI' }, onClose);
    fireEvent.click(screen.getByRole('button', { name: /Nein/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('zeigt Fehlermeldung wenn createRun fehlschlägt', async () => {
    mockCreateRun.mockRejectedValue(new Error('Backend nicht erreichbar'));
    renderDialog({ id: 'u-1', name: 'SMI' });
    fireEvent.click(screen.getByRole('button', { name: /Ja/i }));
    await waitFor(() =>
      expect(screen.getByText(/Backend nicht erreichbar/)).toBeInTheDocument()
    );
  });
});
```

- [ ] **Step 2: Test laufen lassen — muss FAIL sein**

```bash
cd /private/tmp/prisma-capstone
npx --prefix frontend vitest run components/universes/__tests__/StartRankingDialog.test.tsx
```

Erwartetes Ergebnis: `Cannot find module '../StartRankingDialog'`

- [ ] **Step 3: Verzeichnis anlegen und Component implementieren**

```tsx
// frontend/components/universes/StartRankingDialog.tsx
'use client';

import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { createRun } from '@/lib/api/runs';

interface Props {
  universe: { id: string; name: string } | null;
  onClose: () => void;
}

export function StartRankingDialog({ universe, onClose }: Props) {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: () => createRun(universe!.id),
    onSuccess: (run) => router.push(`/rankings/${run.id}`),
  });

  return (
    <Dialog
      open={universe !== null}
      onOpenChange={(open) => {
        if (!open && !mutation.isPending) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ranking starten?</DialogTitle>
          <DialogDescription>
            Möchtest du direkt einen Ranking-Run für{' '}
            <strong>{universe?.name}</strong> starten?
          </DialogDescription>
        </DialogHeader>

        {mutation.isError && (
          <p className="text-sm text-destructive" role="alert">
            {mutation.error instanceof Error
              ? mutation.error.message
              : 'Fehler beim Starten des Rankings'}
          </p>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Nein
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending && (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            )}
            Ja, Ranking starten
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Tests laufen lassen — müssen PASS sein**

```bash
cd /private/tmp/prisma-capstone
npx --prefix frontend vitest run components/universes/__tests__/StartRankingDialog.test.tsx
```

Erwartetes Ergebnis: 5 Tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/universes/StartRankingDialog.tsx \
        frontend/components/universes/__tests__/StartRankingDialog.test.tsx
git commit -m "feat(frontend): StartRankingDialog — Post-Creation-Prompt"
```

---

## Task 3: Dialog in new/page.tsx einbinden

**Files:**
- Modify: `frontend/app/universes/new/page.tsx`

- [ ] **Step 1: Datei anpassen**

Ersetze den gesamten Inhalt von `frontend/app/universes/new/page.tsx`:

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';
import { createUniverse } from '@/lib/api/universes';

export default function NewUniversePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [tickersRaw, setTickersRaw] = useState('');
  const [createdUniverse, setCreatedUniverse] = useState<{ id: string; name: string } | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      createUniverse({
        name: name.trim(),
        region: region.trim(),
        tickers: tickersRaw
          .split(',')
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['universes'] });
      setCreatedUniverse({ id: data.id, name: data.name });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Neues Universum</h1>
        <p className="text-muted-foreground text-sm">
          Definiere einen Aktien-Pool für Ranking-Runs.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Universum-Details</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="name" className="text-sm font-medium">
                Name
              </label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="z.B. SMI"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="region" className="text-sm font-medium">
                Region
              </label>
              <Input
                id="region"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                placeholder="z.B. CH, US, EU"
                required
              />
            </div>

            <div className="space-y-1">
              <label htmlFor="tickers" className="text-sm font-medium">
                Ticker (kommagetrennt)
              </label>
              <textarea
                id="tickers"
                value={tickersRaw}
                onChange={(e) => setTickersRaw(e.target.value)}
                placeholder="z.B. NESN, NOVN, ROG"
                required
                rows={3}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none"
              />
              <p className="text-xs text-muted-foreground">
                Ticker werden automatisch in Grossbuchstaben umgewandelt.
              </p>
            </div>

            {mutation.isError && (
              <div className="flex items-center gap-2 text-destructive text-sm">
                <XCircle className="h-4 w-4 shrink-0" />
                <span>
                  {mutation.error instanceof Error
                    ? mutation.error.message
                    : 'Fehler beim Speichern'}
                </span>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? 'Speichern...' : 'Universum anlegen'}
              </Button>
              <Button variant="outline" asChild>
                <Link href="/universes">Abbrechen</Link>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <StartRankingDialog
        universe={createdUniverse}
        onClose={() => {
          setCreatedUniverse(null);
          router.push('/universes');
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/universes/new/page.tsx
git commit -m "feat(frontend): Post-Creation-Dialog in new/page.tsx"
```

---

## Task 4: Dialog in wizard/page.tsx einbinden

**Files:**
- Modify: `frontend/app/universes/wizard/page.tsx`

- [ ] **Step 1: Datei anpassen**

Ersetze den gesamten Inhalt von `frontend/app/universes/wizard/page.tsx`:

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Sparkles, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';
import {
  createUniverse,
  suggestUniverse,
  type UniverseSuggestion,
} from '@/lib/api/universes';

export default function WizardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [description, setDescription] = useState('');
  const [suggestion, setSuggestion] = useState<UniverseSuggestion | null>(null);
  const [name, setName] = useState('');
  const [region, setRegion] = useState('');
  const [tickersRaw, setTickersRaw] = useState('');
  const [createdUniverse, setCreatedUniverse] = useState<{ id: string; name: string } | null>(null);

  const suggestMutation = useMutation({
    mutationFn: () => suggestUniverse(description),
    onSuccess: (data) => {
      setSuggestion(data);
      setName(data.name);
      setRegion(data.region);
      setTickersRaw(data.tickers.join(', '));
    },
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createUniverse({
        name: name.trim(),
        region: region.trim(),
        tickers: tickersRaw
          .split(',')
          .map((t) => t.trim().toUpperCase())
          .filter(Boolean),
      }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['universes'] });
      setCreatedUniverse({ id: data.id, name: data.name });
    },
  });

  function resetSuggestion() {
    setSuggestion(null);
    setName('');
    setRegion('');
    setTickersRaw('');
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <Link
        href="/universes"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="mr-1 h-4 w-4" />
        Zurück zu Universen
      </Link>

      <div>
        <h1 className="text-2xl font-bold tracking-tight">Universe mit KI generieren</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Beschreibe, welches Universe du suchst — Claude wählt passende Tickers aus dem
          verfügbaren Stock-Katalog.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Beschreibung</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Beschreibe dein Universe — z.B. 'Tech-Stocks USA mit Fokus Halbleiter'"
            className="w-full min-h-[100px] rounded-md border bg-background px-3 py-2 text-sm"
            disabled={suggestMutation.isPending}
          />
          <Button
            onClick={() => suggestMutation.mutate()}
            disabled={description.trim().length < 3 || suggestMutation.isPending}
            className="gap-2"
          >
            {suggestMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Vorschlag generieren
          </Button>
          {suggestMutation.isError && (
            <p className="text-sm text-destructive" role="alert">
              {suggestMutation.error instanceof Error
                ? suggestMutation.error.message
                : 'Vorschlag konnte nicht erstellt werden'}
            </p>
          )}
        </CardContent>
      </Card>

      {suggestion && (
        <>
          <Card className="border-pink-500/40 bg-pink-50/40 dark:bg-pink-950/20">
            <CardContent className="py-4 flex items-start gap-2">
              <Sparkles className="h-4 w-4 text-pink-600 dark:text-pink-400 shrink-0 mt-0.5" />
              <p className="text-sm text-muted-foreground">{suggestion.reasoning}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Vorschlag anpassen</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-sm font-medium block mb-1">Name</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">Region</label>
                <Input value={region} onChange={(e) => setRegion(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium block mb-1">
                  Tickers (komma-separiert)
                </label>
                <Input
                  value={tickersRaw}
                  onChange={(e) => setTickersRaw(e.target.value)}
                />
              </div>
              <div className="flex gap-2 pt-2">
                <Button
                  onClick={() => createMutation.mutate()}
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? 'Erstellt...' : 'Erstellen'}
                </Button>
                <Button variant="outline" onClick={resetSuggestion}>
                  Vorschlag verwerfen
                </Button>
              </div>
              {createMutation.isError && (
                <p className="text-sm text-destructive" role="alert">
                  {createMutation.error instanceof Error
                    ? createMutation.error.message
                    : 'Erstellung fehlgeschlagen'}
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <StartRankingDialog
        universe={createdUniverse}
        onClose={() => {
          setCreatedUniverse(null);
          router.push('/universes');
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/universes/wizard/page.tsx
git commit -m "feat(frontend): Post-Creation-Dialog in wizard/page.tsx"
```

---

## Task 5: CTA-Button pro Zeile in UniverseList + Tests aktualisieren

**Files:**
- Modify: `frontend/app/universes/universe-list.tsx`
- Modify: `frontend/app/universes/__tests__/universe-list.test.tsx`

- [ ] **Step 1: Failing Test für "Ranking starten"-Button schreiben**

Ersetze `frontend/app/universes/__tests__/universe-list.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { UniverseList } from '../universe-list';
import type { UniverseRead } from '@/lib/api/universes';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/components/universes/StartRankingDialog', () => ({
  StartRankingDialog: ({ universe }: { universe: { name: string } | null }) =>
    universe ? <div data-testid="dialog">{universe.name}</div> : null,
}));

const sampleUniverses: UniverseRead[] = [
  {
    id: '11111111-0000-0000-0000-000000000001',
    name: 'SMI',
    region: 'CH',
    tickers: ['NESN', 'NOVN', 'ROG'],
  },
  {
    id: '11111111-0000-0000-0000-000000000002',
    name: 'S&P 500',
    region: 'US',
    tickers: ['AAPL', 'MSFT'],
  },
];

describe('UniverseList', () => {
  it('shows universe names in the table', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.getByText('SMI')).toBeInTheDocument();
    expect(screen.getByText('S&P 500')).toBeInTheDocument();
  });

  it('shows region for each universe', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.getByText('CH')).toBeInTheDocument();
    expect(screen.getByText('US')).toBeInTheDocument();
  });

  it('shows ticker count correctly', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows empty-state message when list is empty', () => {
    render(<UniverseList universes={[]} />);
    expect(screen.getByText(/Noch keine Universen angelegt/)).toBeInTheDocument();
  });

  it('renders a "Ranking starten" button for each universe', () => {
    render(<UniverseList universes={sampleUniverses} />);
    const buttons = screen.getAllByRole('button', { name: /Ranking starten/i });
    expect(buttons).toHaveLength(2);
  });

  it('klick auf Button öffnet Dialog mit richtigem Universe', () => {
    render(<UniverseList universes={sampleUniverses} />);
    expect(screen.queryByTestId('dialog')).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /Ranking starten/i })[0]);
    expect(screen.getByTestId('dialog')).toHaveTextContent('SMI');
  });
});
```

- [ ] **Step 2: Tests laufen lassen — neue Tests müssen FAIL sein**

```bash
cd /private/tmp/prisma-capstone
npx --prefix frontend vitest run app/universes/__tests__/universe-list.test.tsx
```

Erwartetes Ergebnis: `renders a "Ranking starten" button` und `klick auf Button öffnet Dialog` FAIL

- [ ] **Step 3: universe-list.tsx aktualisieren**

Ersetze `frontend/app/universes/universe-list.tsx`:

```tsx
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Play } from 'lucide-react';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { StartRankingDialog } from '@/components/universes/StartRankingDialog';
import type { UniverseRead } from '@/lib/api/universes';

export function UniverseList({ universes }: { universes: UniverseRead[] }) {
  const [selectedUniverse, setSelectedUniverse] = useState<{ id: string; name: string } | null>(null);

  if (universes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        Noch keine Universen angelegt.{' '}
        <Link href="/universes/new" className="underline">
          Erstes Universum erstellen
        </Link>
      </p>
    );
  }

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Region</TableHead>
            <TableHead>Anzahl Ticker</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {universes.map((u) => (
            <TableRow key={u.id}>
              <TableCell className="font-medium">{u.name}</TableCell>
              <TableCell>{u.region}</TableCell>
              <TableCell>{u.tickers.length}</TableCell>
              <TableCell className="text-right">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedUniverse({ id: u.id, name: u.name })}
                >
                  <Play className="h-3 w-3 mr-1" />
                  Ranking starten
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <StartRankingDialog
        universe={selectedUniverse}
        onClose={() => setSelectedUniverse(null)}
      />
    </>
  );
}
```

- [ ] **Step 4: Alle Tests laufen lassen — müssen PASS sein**

```bash
cd /private/tmp/prisma-capstone
npx --prefix frontend vitest run app/universes/__tests__/universe-list.test.tsx
```

Erwartetes Ergebnis: 6 Tests PASS

- [ ] **Step 5: Gesamte Test-Suite grün**

```bash
cd /private/tmp/prisma-capstone
npx --prefix frontend vitest run
```

Alle bestehenden Tests müssen weiterhin PASS sein.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/universes/universe-list.tsx \
        frontend/app/universes/__tests__/universe-list.test.tsx
git commit -m "feat(frontend): Ranking-starten-CTA pro Universe-Zeile"
```

---

## Self-Review

**Spec-Coverage:**
- ✅ Dialog nach Erstellung (both `new/` und `wizard/`) → Task 2, 3, 4
- ✅ "Ja" startet Run und navigiert zu `/rankings/<id>` → Task 2 (`StartRankingDialog`)
- ✅ "Nein" schliesst Dialog, bleibt auf Universen → Task 3 + 4 (`onClose` → `router.push('/universes')`)
- ✅ CTA-Button pro Zeile in der Liste → Task 5

**Placeholder-Scan:** Keine TBDs, alle Code-Blöcke vollständig.

**Type-Konsistenz:** `universe: { id: string; name: string } | null` in `StartRankingDialog` matcht mit `UniverseRead` (hat beide Felder). `createRun(universe!.id)` gibt `RunResponse` zurück — `run.id` existiert.
