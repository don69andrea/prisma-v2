# Ranking-UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Liefert eine demo-taugliche Ranking-UI (Form auf `/rankings`, Detail auf `/rankings/[runId]`) plus Playwright-E2E-Suite, integriert in CI.

**Architecture:** Client-side React-Pages (Pattern wie `/universes`), `useQuery`/`useMutation` (TanStack Query), dünner `lib/api/runs.ts`-Wrapper, Vitest + RTL Unit-Tests, Playwright E2E mit Backend in CI. Backend bleibt unverändert.

**Tech Stack:** Next.js 14 App-Router, TanStack Query v5, Tailwind, Vitest 1.6, React Testing Library, Playwright 1.48, Postgres-Service in CI.

**Spec:** `docs/specs/2026-05-17-ranking-ui-design.md`

---

## File Structure

**Erstellen:**
- `frontend/lib/api/runs.ts` — API-Wrapper für `/api/v1/runs`-Endpoints
- `frontend/app/rankings/rankings-form.tsx` — Client-Komponente: Universe-Select + Run-Button
- `frontend/app/rankings/[runId]/page.tsx` — Detail-Page (Run-Status + Tabelle)
- `frontend/app/rankings/[runId]/rankings-table.tsx` — Tabellen-Komponente (9 Spalten)
- `frontend/app/rankings/__tests__/rankings-form.test.tsx` — Vitest Unit-Tests
- `frontend/app/rankings/__tests__/rankings-table.test.tsx` — Vitest Unit-Tests
- `frontend/playwright.config.ts` — Playwright-Konfig (webServer + baseURL)
- `frontend/e2e/rankings.spec.ts` — 3 E2E-Tests
- `frontend/e2e/fixtures.ts` — Test-Universe-Setup via Backend-API

**Modifizieren:**
- `frontend/app/rankings/page.tsx` — ersetzt "Kommt bald"-Platzhalter durch Form
- `frontend/package.json` — `@playwright/test` als devDep, `e2e` + `e2e:install` Scripts
- `frontend/.gitignore` — `playwright-report/`, `test-results/`
- `.github/workflows/ci.yml` — neuer Job `frontend-e2e`

---

## Task 1: API-Layer (`lib/api/runs.ts`)

**Files:**
- Create: `frontend/lib/api/runs.ts`

- [ ] **Step 1: Datei anlegen mit Types + Wrappern**

```typescript
import { apiFetch } from './client';

export type RankingRunStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface RunResponse {
  id: string;
  status: RankingRunStatus;
  universe_id: string;
  created_at: string;
}

export interface RankingItem {
  ticker: string;
  total_rank: number | null;
  weighted_avg: number | null;
  is_sweet_spot: boolean;
  per_model_ranks: Record<string, number | null>;
}

export async function createRun(universeId: string): Promise<RunResponse> {
  return apiFetch<RunResponse>('/api/v1/runs', {
    method: 'POST',
    body: JSON.stringify({ universe_id: universeId }),
  });
}

export async function getRun(runId: string): Promise<RunResponse> {
  return apiFetch<RunResponse>(`/api/v1/runs/${runId}`);
}

export async function getRankings(runId: string): Promise<RankingItem[]> {
  return apiFetch<RankingItem[]>(`/api/v1/runs/${runId}/rankings`);
}
```

- [ ] **Step 2: TypeScript-Check ausführen**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine Errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/runs.ts
git commit -m "feat(frontend): API-Wrapper lib/api/runs.ts für /api/v1/runs"
```

---

## Task 2: RankingsTable Component (TDD)

**Files:**
- Create: `frontend/app/rankings/[runId]/rankings-table.tsx`
- Test: `frontend/app/rankings/__tests__/rankings-table.test.tsx`

- [ ] **Step 1: Test schreiben**

Datei `frontend/app/rankings/__tests__/rankings-table.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { RankingsTable } from '../[runId]/rankings-table';
import type { RankingItem } from '@/lib/api/runs';

const sampleItems: RankingItem[] = [
  {
    ticker: 'AAPL',
    total_rank: 1,
    weighted_avg: 2.1,
    is_sweet_spot: true,
    per_model_ranks: {
      quality_classic: 1,
      diversification: 3,
      trend_momentum: 2,
      value_alpha_potential: 2,
      alpha: 1,
    },
  },
  {
    ticker: 'MSFT',
    total_rank: 2,
    weighted_avg: 2.4,
    is_sweet_spot: false,
    per_model_ranks: {
      quality_classic: 2,
      diversification: null,
      trend_momentum: 4,
      value_alpha_potential: 1,
      alpha: 3,
    },
  },
];

describe('RankingsTable', () => {
  it('rendert eine Zeile pro Item', () => {
    render(<RankingsTable items={sampleItems} />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('zeigt Sweet-Spot-Badge nur wenn is_sweet_spot=true', () => {
    render(<RankingsTable items={sampleItems} />);
    const badges = screen.queryAllByText('★');
    expect(badges).toHaveLength(1);
  });

  it('zeigt em-dash für null-Werte', () => {
    render(<RankingsTable items={sampleItems} />);
    const dashes = screen.queryAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('rendert Modell-Spalten in fixer Reihenfolge', () => {
    render(<RankingsTable items={sampleItems} />);
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent);
    expect(headers).toEqual([
      '#',
      'Ticker',
      'Avg',
      'Sweet-Spot',
      'Quality',
      'Diversification',
      'Trend',
      'Value',
      'Alpha',
    ]);
  });

  it('zeigt Empty-State wenn items leer', () => {
    render(<RankingsTable items={[]} />);
    expect(screen.getByText(/Keine Ergebnisse/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Test laufen → muss fehlschlagen**

Run: `cd frontend && npm test -- rankings-table`
Expected: FAIL — Modul `../[runId]/rankings-table` existiert nicht.

- [ ] **Step 3: Implementierung schreiben**

Datei `frontend/app/rankings/[runId]/rankings-table.tsx`:

```typescript
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { RankingItem } from '@/lib/api/runs';

const MODEL_COLUMNS: Array<{ key: string; label: string }> = [
  { key: 'quality_classic', label: 'Quality' },
  { key: 'diversification', label: 'Diversification' },
  { key: 'trend_momentum', label: 'Trend' },
  { key: 'value_alpha_potential', label: 'Value' },
  { key: 'alpha', label: 'Alpha' },
];

function formatNumber(value: number | null, digits = 0): string {
  if (value === null) return '—';
  return digits === 0 ? String(value) : value.toFixed(digits);
}

export function RankingsTable({ items }: { items: RankingItem[] }) {
  if (items.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">Keine Ergebnisse</div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>#</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead>Avg</TableHead>
          <TableHead>Sweet-Spot</TableHead>
          {MODEL_COLUMNS.map((col) => (
            <TableHead key={col.key}>{col.label}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.ticker}>
            <TableCell>{formatNumber(item.total_rank)}</TableCell>
            <TableCell className="font-mono">{item.ticker}</TableCell>
            <TableCell>{formatNumber(item.weighted_avg, 2)}</TableCell>
            <TableCell>
              {item.is_sweet_spot ? <Badge variant="default">★</Badge> : null}
            </TableCell>
            {MODEL_COLUMNS.map((col) => (
              <TableCell key={col.key}>{formatNumber(item.per_model_ranks[col.key] ?? null)}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 4: Test laufen → muss durchgehen**

Run: `cd frontend && npm test -- rankings-table`
Expected: PASS, 5 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/rankings/[runId]/rankings-table.tsx frontend/app/rankings/__tests__/rankings-table.test.tsx
git commit -m "feat(frontend): RankingsTable mit 9 Spalten + Tests"
```

---

## Task 3: RankingsForm Component (TDD)

**Files:**
- Create: `frontend/app/rankings/rankings-form.tsx`
- Test: `frontend/app/rankings/__tests__/rankings-form.test.tsx`

- [ ] **Step 1: Test schreiben**

Datei `frontend/app/rankings/__tests__/rankings-form.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { RankingsForm } from '../rankings-form';
import type { UniverseListResponse } from '@/lib/api/universes';
import type { RunResponse } from '@/lib/api/runs';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockListUniverses = vi.fn();
const mockCreateRun = vi.fn();
vi.mock('@/lib/api/universes', () => ({
  listUniverses: () => mockListUniverses(),
}));
vi.mock('@/lib/api/runs', () => ({
  createRun: (universeId: string) => mockCreateRun(universeId),
}));

const sampleUniverses: UniverseListResponse = {
  total: 2,
  items: [
    { id: 'u-1', name: 'SMI', region: 'CH', tickers: ['NESN', 'NOVN'] },
    { id: 'u-2', name: 'Tech-5', region: 'US', tickers: ['AAPL', 'MSFT'] },
  ],
};

const sampleRun: RunResponse = {
  id: 'run-42',
  status: 'completed',
  universe_id: 'u-1',
  created_at: '2026-05-17T12:00:00Z',
};

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <RankingsForm />
    </QueryClientProvider>
  );
}

describe('RankingsForm', () => {
  beforeEach(() => {
    mockPush.mockReset();
    mockListUniverses.mockReset();
    mockCreateRun.mockReset();
  });

  it('rendert Universe-Optionen aus listUniverses', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    renderForm();
    await waitFor(() => expect(screen.getByText('SMI')).toBeInTheDocument());
    expect(screen.getByText('Tech-5')).toBeInTheDocument();
  });

  it('disabled Run-Button solange kein Universe gewählt', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    renderForm();
    const button = await screen.findByRole('button', { name: /Run starten/i });
    expect(button).toBeDisabled();
  });

  it('submit ruft createRun und navigiert zur Detail-URL', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    mockCreateRun.mockResolvedValue(sampleRun);
    renderForm();
    await screen.findByText('SMI');
    fireEvent.change(screen.getByLabelText(/Universe/i), { target: { value: 'u-1' } });
    fireEvent.click(screen.getByRole('button', { name: /Run starten/i }));
    await waitFor(() => expect(mockCreateRun).toHaveBeenCalledWith('u-1'));
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/rankings/run-42'));
  });

  it('zeigt Error-Banner wenn createRun fehlschlägt', async () => {
    mockListUniverses.mockResolvedValue(sampleUniverses);
    mockCreateRun.mockRejectedValue(new Error('Backend down'));
    renderForm();
    await screen.findByText('SMI');
    fireEvent.change(screen.getByLabelText(/Universe/i), { target: { value: 'u-1' } });
    fireEvent.click(screen.getByRole('button', { name: /Run starten/i }));
    await waitFor(() => expect(screen.getByText(/Backend down/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Test laufen → muss fehlschlagen**

Run: `cd frontend && npm test -- rankings-form`
Expected: FAIL — Modul `../rankings-form` existiert nicht.

- [ ] **Step 3: Implementierung schreiben**

Datei `frontend/app/rankings/rankings-form.tsx`:

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { listUniverses } from '@/lib/api/universes';
import { createRun } from '@/lib/api/runs';

export function RankingsForm() {
  const router = useRouter();
  const [universeId, setUniverseId] = useState<string>('');

  const universesQuery = useQuery({
    queryKey: ['universes'],
    queryFn: listUniverses,
    staleTime: 30 * 1000,
  });

  const mutation = useMutation({
    mutationFn: () => createRun(universeId),
    onSuccess: (run) => router.push(`/rankings/${run.id}`),
  });

  const isPending = mutation.isPending;
  const disabled = !universeId || isPending;

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!disabled) mutation.mutate();
      }}
    >
      <div className="space-y-1">
        <label htmlFor="universe" className="text-sm font-medium">
          Universe
        </label>
        <select
          id="universe"
          value={universeId}
          onChange={(e) => setUniverseId(e.target.value)}
          disabled={isPending || universesQuery.isLoading}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <option value="">— wählen —</option>
          {universesQuery.data?.items.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
      </div>

      {universesQuery.isError && (
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            Universen konnten nicht geladen werden:{' '}
            {universesQuery.error instanceof Error ? universesQuery.error.message : 'Unbekannter Fehler'}
          </span>
        </div>
      )}

      {mutation.isError && (
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            {mutation.error instanceof Error ? mutation.error.message : 'Run konnte nicht gestartet werden'}
          </span>
        </div>
      )}

      <Button type="submit" disabled={disabled} aria-busy={isPending}>
        {isPending ? 'Run läuft (~30-60s)…' : 'Run starten'}
      </Button>
    </form>
  );
}
```

- [ ] **Step 4: Test laufen → muss durchgehen**

Run: `cd frontend && npm test -- rankings-form`
Expected: PASS, 4 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/rankings/rankings-form.tsx frontend/app/rankings/__tests__/rankings-form.test.tsx
git commit -m "feat(frontend): RankingsForm mit Universe-Select + Tests"
```

---

## Task 4: `/rankings` Page (Form-Wrapper)

**Files:**
- Modify: `frontend/app/rankings/page.tsx`

- [ ] **Step 1: Platzhalter durch Form ersetzen**

Datei `frontend/app/rankings/page.tsx` komplett ersetzen:

```typescript
import type { Metadata } from 'next';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RankingsForm } from './rankings-form';

export const metadata: Metadata = {
  title: 'Rankings',
};

export default function RankingsPage() {
  return (
    <div className="space-y-6 max-w-lg">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Ranking starten</h1>
        <p className="text-muted-foreground text-sm">
          Wähle ein Universum und starte einen Ranking-Run über alle 5 Modelle.
        </p>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Neuer Run</CardTitle>
        </CardHeader>
        <CardContent>
          <RankingsForm />
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Lint + Type-Check**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: keine Errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/rankings/page.tsx
git commit -m "feat(frontend): /rankings zeigt RankingsForm statt Platzhalter"
```

---

## Task 5: `/rankings/[runId]` Detail-Page

**Files:**
- Create: `frontend/app/rankings/[runId]/page.tsx`

- [ ] **Step 1: Detail-Page schreiben**

Datei `frontend/app/rankings/[runId]/page.tsx`:

```typescript
'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { XCircle, ArrowLeft } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { getRun, getRankings } from '@/lib/api/runs';
import { getUniverse } from '@/lib/api/universes';
import { ApiError } from '@/lib/api/client';

import { RankingsTable } from './rankings-table';

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {[1, 2, 3].map((i) => (
        <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
      ))}
    </div>
  );
}

export default function RankingDetailPage({ params }: { params: { runId: string } }) {
  const runQuery = useQuery({
    queryKey: ['run', params.runId],
    queryFn: () => getRun(params.runId),
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 5000 : false),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });

  const isCompleted = runQuery.data?.status === 'completed';

  const rankingsQuery = useQuery({
    queryKey: ['rankings', params.runId],
    queryFn: () => getRankings(params.runId),
    enabled: isCompleted,
  });

  const universeQuery = useQuery({
    queryKey: ['universe', runQuery.data?.universe_id],
    queryFn: () => getUniverse(runQuery.data!.universe_id),
    enabled: !!runQuery.data?.universe_id,
  });

  const is404 = runQuery.error instanceof ApiError && runQuery.error.status === 404;

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link href="/rankings" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-1 h-4 w-4" />
          Neuer Run
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Ranking-Ergebnis</h1>
      </div>

      {is404 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-lg font-medium">Run nicht gefunden</p>
            <p className="text-sm text-muted-foreground mt-1">Run-ID: {params.runId}</p>
          </CardContent>
        </Card>
      )}

      {!is404 && runQuery.data && (
        <Card>
          <CardContent className="py-4 flex items-center gap-4 text-sm">
            <span>
              <span className="text-muted-foreground">Universe:</span>{' '}
              <span className="font-medium">{universeQuery.data?.name ?? runQuery.data.universe_id}</span>
            </span>
            <Badge
              variant={
                runQuery.data.status === 'completed'
                  ? 'default'
                  : runQuery.data.status === 'failed'
                    ? 'destructive'
                    : 'secondary'
              }
            >
              {runQuery.data.status}
            </Badge>
            <span className="text-muted-foreground">
              {new Date(runQuery.data.created_at).toLocaleString('de-CH')}
            </span>
          </CardContent>
        </Card>
      )}

      {runQuery.data?.status === 'running' && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" role="status">
          <span>Run läuft noch. Seite aktualisiert sich alle 5s.</span>
        </div>
      )}

      {runQuery.data?.status === 'failed' && (
        <Card>
          <CardContent className="py-8 flex items-center gap-2 text-destructive">
            <XCircle className="h-5 w-5 shrink-0" />
            <span>Run fehlgeschlagen. Prüfe Backend-Logs.</span>
          </CardContent>
        </Card>
      )}

      {!is404 && (runQuery.isLoading || (isCompleted && rankingsQuery.isLoading)) && <TableSkeleton />}

      {isCompleted && rankingsQuery.data && <RankingsTable items={rankingsQuery.data} />}

      {isCompleted && rankingsQuery.isError && (
        <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
          <XCircle className="h-4 w-4 shrink-0" />
          <span>
            Rankings konnten nicht geladen werden:{' '}
            {rankingsQuery.error instanceof Error ? rankingsQuery.error.message : 'Unbekannter Fehler'}
          </span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Lint + Type-Check**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: keine Errors.

- [ ] **Step 3: Build verifizieren**

Run: `cd frontend && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build`
Expected: success, neue Routes `/rankings` und `/rankings/[runId]` sichtbar im Build-Output.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/rankings/[runId]/page.tsx
git commit -m "feat(frontend): /rankings/[runId] Detail-Page mit Run-Status + Tabelle"
```

---

## Task 6: Playwright Setup

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/.gitignore`
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/.gitkeep` (Verzeichnis)

- [ ] **Step 1: Playwright als Dev-Dependency installieren**

Run: `cd frontend && npm install --save-dev @playwright/test@^1.48`
Expected: lockfile + package.json aktualisiert, kein Build-Error.

- [ ] **Step 2: Scripts in `package.json` ergänzen**

In `frontend/package.json`, im `scripts`-Block hinzufügen:

```json
"e2e": "playwright test",
"e2e:install": "playwright install --with-deps chromium",
"e2e:report": "playwright show-report"
```

- [ ] **Step 3: `.gitignore` erweitern**

In `frontend/.gitignore` ergänzen (falls noch nicht vorhanden):

```
playwright-report/
test-results/
playwright/.cache/
```

- [ ] **Step 4: Playwright-Config schreiben**

Datei `frontend/playwright.config.ts`:

```typescript
import { defineConfig, devices } from '@playwright/test';

const PORT = 3000;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  timeout: 120_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: process.env.PLAYWRIGHT_NO_WEBSERVER
    ? undefined
    : {
        command: `npm run start -- --port ${PORT}`,
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
```

**Hintergrund:** `webServer` startet Next.js automatisch. In CI nutzen wir `PLAYWRIGHT_NO_WEBSERVER=1` falls der Frontend-Server in einem separaten Step gestartet wird (entscheiden wir in Task 9). `fullyParallel: false` weil Tests einen gemeinsamen Backend-DB-State teilen.

- [ ] **Step 5: Playwright-Browser installieren**

Run: `cd frontend && npm run e2e:install`
Expected: Chromium-Browser wird heruntergeladen (~150MB). Falls Permission-Errors auf macOS: `sudo npx playwright install-deps`.

- [ ] **Step 6: Smoke-Test dass Playwright funktioniert**

Datei `frontend/e2e/smoke.spec.ts` (temporär):

```typescript
import { test, expect } from '@playwright/test';

test('playwright läuft', async () => {
  expect(1 + 1).toBe(2);
});
```

Run: `cd frontend && npm run e2e`
Expected: 1 passed.

Danach Datei löschen: `rm frontend/e2e/smoke.spec.ts`.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/playwright.config.ts frontend/.gitignore
git commit -m "chore(frontend): Playwright setup (config, scripts, gitignore)"
```

---

## Task 7: E2E-Fixtures + Smoke + Universe-Flow

**Files:**
- Create: `frontend/e2e/fixtures.ts`
- Create: `frontend/e2e/rankings.spec.ts`

- [ ] **Step 1: Fixtures-Datei mit Backend-API-Helpers**

Datei `frontend/e2e/fixtures.ts`:

```typescript
const API_BASE = process.env.E2E_API_BASE_URL ?? 'http://localhost:8000';

export interface Universe {
  id: string;
  name: string;
  region: string;
  tickers: string[];
}

export async function createTestUniverse(suffix: string): Promise<Universe> {
  const response = await fetch(`${API_BASE}/api/v1/universes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: `e2e-test-${suffix}`,
      region: 'US',
      tickers: ['AAPL', 'MSFT', 'GOOGL'],
    }),
  });
  if (!response.ok) {
    throw new Error(`Universe-Setup fehlgeschlagen: ${response.status} ${await response.text()}`);
  }
  return response.json();
}
```

- [ ] **Step 2: Spec-Datei mit Smoke + Universe-Flow**

Datei `frontend/e2e/rankings.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

test.describe('PRISMA E2E', () => {
  test('1. Startseite lädt und zeigt Navigation', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/PRISMA|Dashboard/);
    await expect(page.getByRole('link', { name: /Universen/i })).toBeVisible();
  });

  test('2. Universe-Flow: neues Universum anlegen', async ({ page }) => {
    await page.goto('/universes');
    await page.getByRole('link', { name: /Neues Universum/i }).click();
    await expect(page).toHaveURL(/\/universes\/new/);

    const suffix = Date.now();
    await page.getByLabel('Name').fill(`e2e-flow-${suffix}`);
    await page.getByLabel('Region').fill('US');
    await page.getByLabel(/Ticker/i).fill('AAPL, MSFT');
    await page.getByRole('button', { name: /Universum anlegen/i }).click();

    await expect(page).toHaveURL(/\/universes$/);
    await expect(page.getByText(`e2e-flow-${suffix}`)).toBeVisible({ timeout: 10_000 });
  });
});
```

- [ ] **Step 3: Tests laufen lassen (Backend muss laufen)**

In separatem Terminal: Backend starten (z.B. `uv run uvicorn backend.interfaces.rest.main:app --port 8000`).

Run: `cd frontend && npm run e2e`
Expected: 2 passed (Tests #1 und #2).

- [ ] **Step 4: Falls Test #1 wegen Titel-Mismatch failt:**

Title in `frontend/app/layout.tsx` checken (`grep -n "title" frontend/app/layout.tsx`). Falls anderer Titel, im Test anpassen — nicht im Code ändern.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/fixtures.ts frontend/e2e/rankings.spec.ts
git commit -m "test(e2e): Smoke + Universe-Flow Tests"
```

---

## Task 8: E2E Ranking-Flow

**Files:**
- Modify: `frontend/e2e/rankings.spec.ts`

- [ ] **Step 1: Dritten Test hinzufügen**

In `frontend/e2e/rankings.spec.ts` an das `test.describe`-Ende anhängen:

```typescript
  test('3. Ranking-Flow: Run starten und Ergebnis-Tabelle sehen', async ({ page }) => {
    const { createTestUniverse } = await import('./fixtures');
    const universe = await createTestUniverse(`run-${Date.now()}`);

    await page.goto('/rankings');
    await expect(page.getByRole('heading', { name: /Ranking starten/i })).toBeVisible();

    await page.getByLabel('Universe').selectOption(universe.id);
    await page.getByRole('button', { name: /Run starten/i }).click();

    await expect(page).toHaveURL(/\/rankings\/[0-9a-f-]+$/, { timeout: 90_000 });
    await expect(page.getByRole('heading', { name: /Ranking-Ergebnis/i })).toBeVisible();

    // Mindestens eine Datenzeile (Header + ≥1 Body-Row)
    const rows = page.locator('tbody tr');
    await expect(rows.first()).toBeVisible({ timeout: 60_000 });
    expect(await rows.count()).toBeGreaterThanOrEqual(1);

    // Erste Ticker-Spalte enthält einen unserer Test-Tickers
    const firstTickerCell = page.locator('tbody tr td.font-mono').first();
    await expect(firstTickerCell).toHaveText(/^(AAPL|MSFT|GOOGL)$/);
  });
```

- [ ] **Step 2: Test laufen (Backend + Test-Universe-Cleanup beachten)**

Run: `cd frontend && npm run e2e -- --grep "Ranking-Flow"`
Expected: PASS — Test legt eigenes Universe an, Run dauert <90s (mit Stub-Providern <5s).

- [ ] **Step 3: Alle 3 Tests zusammen**

Run: `cd frontend && npm run e2e`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/rankings.spec.ts
git commit -m "test(e2e): Ranking-Flow Test mit Run-Start und Tabellen-Verifikation"
```

---

## Task 9: CI Job `frontend-e2e`

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Bestehende `ci.yml` lesen, um Stelle für neuen Job zu finden**

Run: `cat .github/workflows/ci.yml | head -30`
Expected: Job-Liste am Anfang. Den neuen Job `frontend-e2e` nach `frontend-build` einfügen.

- [ ] **Step 2: Neuen Job ans Ende von `.github/workflows/ci.yml` hängen**

```yaml

  frontend-e2e:
    name: Frontend E2E (Playwright)
    runs-on: ubuntu-latest
    needs: [frontend-build]
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: prisma_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    env:
      DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/prisma_test
      E2E_API_BASE_URL: http://localhost:8000
      NEXT_PUBLIC_API_URL: http://localhost:8000
      PLAYWRIGHT_NO_WEBSERVER: "1"
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        run: pip install uv

      - name: Install backend deps
        run: uv sync

      - name: Run Alembic migrations
        run: uv run alembic upgrade head

      - name: Start backend (background)
        run: |
          uv run uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port 8000 &
          echo "BACKEND_PID=$!" >> $GITHUB_ENV

      - name: Wait for backend health
        run: |
          for i in {1..30}; do
            if curl -sf http://localhost:8000/health > /dev/null; then
              echo "Backend ready"
              exit 0
            fi
            sleep 2
          done
          echo "Backend not ready after 60s"
          exit 1

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend deps
        working-directory: frontend
        run: npm ci

      - name: Cache Playwright browsers
        uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ runner.os }}-${{ hashFiles('frontend/package-lock.json') }}

      - name: Install Playwright browsers
        working-directory: frontend
        run: npx playwright install --with-deps chromium

      - name: Build frontend
        working-directory: frontend
        run: npm run build

      - name: Start frontend (background)
        working-directory: frontend
        run: |
          npm run start -- --port 3000 &
          echo "FRONTEND_PID=$!" >> $GITHUB_ENV

      - name: Wait for frontend
        run: |
          for i in {1..30}; do
            if curl -sf http://localhost:3000 > /dev/null; then
              echo "Frontend ready"
              exit 0
            fi
            sleep 2
          done
          echo "Frontend not ready after 60s"
          exit 1

      - name: Run Playwright tests
        working-directory: frontend
        run: npm run e2e

      - name: Upload Playwright report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: frontend/playwright-report
          retention-days: 7
```

- [ ] **Step 3: Verifizieren, dass der Health-Endpoint `/health` heißt**

Run: `grep -rn '"/health"\|/health' backend/interfaces/rest/ --include="*.py" | head -5`
Expected: zeigt den exakten Pfad. Falls anders (z.B. `/api/v1/health`), in CI-Job die `curl`-URLs anpassen.

- [ ] **Step 4: Verifizieren, dass `alembic upgrade head` ohne weitere Config läuft**

Run: `grep -n "DATABASE_URL\|sqlalchemy" backend/alembic/env.py | head -10`
Expected: `env.py` liest `DATABASE_URL` aus ENV (was wir setzen). Falls anders konfiguriert (z.B. nur `.env`-File), als zusätzlichen Step in CI ergänzen: `cp .env.example .env` oder ENV-Variable in `env.py` ergänzen.

- [ ] **Step 5: YAML-Syntax checken**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: keine Exception.

- [ ] **Step 6: Commit + Push, CI beobachten**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: Frontend-E2E-Job mit Postgres + Backend + Playwright"
git push -u origin feat/ranking-ui
```

- [ ] **Step 7: PR erstellen + CI-Status beobachten**

```bash
gh pr create --title "feat: Ranking-UI + Playwright E2E (Closes Codex #1 + #5)" --body "$(cat <<'EOF'
## Summary

- `/rankings` zeigt Universe-Select + Run-Button (statt "Kommt bald")
- `/rankings/[runId]` zeigt 9-Spalten-Tabelle mit Rank, Ticker, Avg, Sweet-Spot, 5 Modell-Ranks
- Vitest Unit-Tests für RankingsForm + RankingsTable
- Playwright E2E-Suite (3 Tests: Smoke, Universe-Flow, Ranking-Flow)
- Neuer CI-Job `frontend-e2e` mit Postgres + Backend + Stub-Providern

Schliesst Codex-Review-Punkte #1 (E2E fehlt) und #5 (Ranking-UI ist Platzhalter).

## Spec

`docs/specs/2026-05-17-ranking-ui-design.md`

## Test plan

- [x] `npm test` grün lokal
- [x] `npm run build` grün lokal
- [x] `npm run e2e` grün lokal (mit Backend)
- [ ] CI grün auf diesem PR
- [ ] Manueller Demo: Run starten, Tabelle sichtbar

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 8: Falls CI failt → Logs prüfen, iterieren**

Häufige Probleme:
- `/health`-Endpoint heißt anders → URLs in CI-Step anpassen
- Alembic findet `DATABASE_URL` nicht → `env.py` anschauen
- Stub-Provider liefern keine Daten → kein Run-Result → Test #3 timeout. Stub-Output prüfen via lokalem Run.
- Frontend findet Backend nicht → `NEXT_PUBLIC_API_URL` muss zur Build-Zeit gesetzt sein (ist es: `env`-Block am Job-Top + Build-Step erbt es).

---

## Done-Definition

- [ ] Alle 9 Tasks committed
- [ ] PR auf `feat/ranking-ui` offen
- [ ] CI-Jobs grün: `backend`, `frontend-build`, `frontend-e2e`
- [ ] Spec-Status auf "Final" gesetzt (`docs/specs/2026-05-17-ranking-ui-design.md`)
- [ ] PR gemerged

---

## Risiken & Mitigations

| Risiko | Mitigation |
|---|---|
| Stub-Provider liefern Daten, bei denen kein Sweet-Spot entsteht | E2E-Test #3 prüft nur, dass Ticker sichtbar ist — kein Assert auf Sweet-Spot-Existenz |
| `alembic` failt in CI mangels Config | Step 4 von Task 9 verifiziert vor dem Push |
| Playwright-Browser-Download in CI flakig | `actions/cache@v4` für `~/.cache/ms-playwright` (im Job enthalten) |
| `npm install` für `@playwright/test` verschiebt andere Versionen | Nach Task 6 Step 1: `git diff package-lock.json` prüfen, nur Playwright-bezogene Änderungen erwartet |
| Lange Test-Dauer in CI (E2E + Browser-Install) | Akzeptiert — typisch 4-6min, einmal pro PR-Push |
