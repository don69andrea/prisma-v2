# Dashboard-Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vier Stats-Karten oberhalb der existierenden Runs-Tabelle auf `/dashboard` — Letzter Run, # Universen, # Stocks, Top-Pick aus jüngstem completed Run.

**Architecture:** Reine Frontend-Änderung. Neue `StatsCards`-Präsentations-Komponente + Erweiterung `DashboardClient` um 2 neue Tanstack-Queries (`stocks-total`, `rankings` für latest-completed-Run) und Derivations.

**Tech Stack:** Next.js 14, TypeScript, Tanstack Query v5, shadcn/Tailwind, Vitest + Testing-Library

**Spec:** `docs/specs/2026-05-28-dashboard-stats-design.md`

**Branch:** `feat/dashboard-stats`

---

## Task 1: `StatsCards` Komponente + Tests

**Files:**
- Create: `frontend/components/dashboard/StatsCards.tsx`
- Create: `frontend/components/dashboard/__tests__/StatsCards.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

```tsx
// frontend/components/dashboard/__tests__/StatsCards.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StatsCards } from '../StatsCards';
import type { RunResponse } from '@/lib/api/runs';

const completedRun: RunResponse = {
  id: 'run-1111-2222-3333',
  status: 'completed',
  universe_id: 'uni-1',
  created_at: '2026-05-28T10:00:00Z',
};

const basicProps = {
  latestRun: completedRun,
  universeCount: 3,
  stockCount: 42,
  topPick: { ticker: 'NVDA', isSweetSpot: true, runId: 'run-1111-2222-3333' },
};

describe('StatsCards', () => {
  it('renders all four cards', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText(/Letzter Run/i)).toBeDefined();
    expect(screen.getByText(/Universen/i)).toBeDefined();
    expect(screen.getByText(/Stocks/i)).toBeDefined();
    expect(screen.getByText(/Top-Pick/i)).toBeDefined();
  });

  it('renders counts correctly', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
  });

  it('renders top-pick ticker', () => {
    render(<StatsCards {...basicProps} />);
    expect(screen.getByText('NVDA')).toBeDefined();
  });

  it('shows sweet-spot indicator when isSweetSpot=true', () => {
    render(<StatsCards {...basicProps} />);
    // Sweet-Spot uses Sparkles icon + pink-Akzent; check via accessible label or test-id
    expect(screen.getByLabelText(/Sweet-Spot/i)).toBeDefined();
  });

  it('hides sweet-spot indicator when isSweetSpot=false', () => {
    render(
      <StatsCards
        {...basicProps}
        topPick={{ ticker: 'JPM', isSweetSpot: false, runId: 'run-1111-2222-3333' }}
      />,
    );
    expect(screen.queryByLabelText(/Sweet-Spot/i)).toBeNull();
  });

  it('shows em-dash for top-pick when null', () => {
    render(<StatsCards {...basicProps} topPick={null} />);
    expect(screen.queryByText('NVDA')).toBeNull();
    // Top-Pick-Karte muss mindestens ein "—" zeigen
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('shows em-dash for latest run when null', () => {
    render(<StatsCards {...basicProps} latestRun={null} />);
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('top-pick links to factsheet page', () => {
    render(<StatsCards {...basicProps} />);
    const link = screen.getByRole('link', { name: /NVDA/ });
    expect(link.getAttribute('href')).toBe('/rankings/run-1111-2222-3333/stock/NVDA');
  });

  it('latest-run shows status badge', () => {
    render(<StatsCards {...basicProps} />);
    // Status-Badge variantet je nach Run-Status; für 'completed' meist 'success'-Variante
    expect(screen.getByText(/Abgeschlossen|completed/i)).toBeDefined();
  });
});
```

- [ ] **Step 2: Tests laufen → FAIL**

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx vitest run components/dashboard/__tests__/StatsCards.test.tsx
```
Expected: FAIL — module not found

- [ ] **Step 3: `StatsCards.tsx` implementieren**

```tsx
// frontend/components/dashboard/StatsCards.tsx
import Link from 'next/link';
import { Clock, Layers, TrendingUp, Star, Sparkles } from 'lucide-react';

import type { RunResponse, RankingRunStatus } from '@/lib/api/runs';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

const STATUS_LABEL: Record<RankingRunStatus, string> = {
  pending: 'Ausstehend',
  running: 'Läuft',
  completed: 'Abgeschlossen',
  failed: 'Fehler',
};

const STATUS_VARIANT: Record<
  RankingRunStatus,
  'warning' | 'default' | 'success' | 'destructive'
> = {
  pending: 'warning',
  running: 'default',
  completed: 'success',
  failed: 'destructive',
};

export interface TopPick {
  ticker: string;
  isSweetSpot: boolean;
  runId: string;
}

interface Props {
  latestRun: RunResponse | null;
  universeCount: number;
  stockCount: number;
  topPick: TopPick | null;
}

export function StatsCards({ latestRun, universeCount, stockCount, topPick }: Props) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Letzter Run */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>Letzter Run</span>
          </div>
          {latestRun ? (
            <>
              <Link
                href={`/rankings/${latestRun.id}`}
                className="block text-base font-bold hover:underline"
              >
                {new Date(latestRun.created_at).toLocaleDateString('de-CH', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                })}
              </Link>
              <Badge variant={STATUS_VARIANT[latestRun.status]}>
                {STATUS_LABEL[latestRun.status]}
              </Badge>
            </>
          ) : (
            <p className="text-base font-bold">—</p>
          )}
        </CardContent>
      </Card>

      {/* # Universen */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Layers className="h-4 w-4" />
            <span>Universen</span>
          </div>
          <Link href="/universes" className="block text-2xl font-bold hover:underline">
            {universeCount}
          </Link>
        </CardContent>
      </Card>

      {/* # Stocks */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <TrendingUp className="h-4 w-4" />
            <span>Stocks</span>
          </div>
          <p className="text-2xl font-bold">{stockCount}</p>
        </CardContent>
      </Card>

      {/* Top-Pick */}
      <Card>
        <CardContent className="py-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <Star className="h-4 w-4" />
            <span>Top-Pick</span>
          </div>
          {topPick ? (
            <Link
              href={`/rankings/${topPick.runId}/stock/${topPick.ticker}`}
              className="inline-flex items-center gap-2 text-xl font-bold hover:underline"
            >
              {topPick.ticker}
              {topPick.isSweetSpot && (
                <Sparkles
                  className="h-4 w-4 text-pink-600 dark:text-pink-400"
                  aria-label="Sweet-Spot"
                />
              )}
            </Link>
          ) : (
            <p className="text-xl font-bold">—</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Tests laufen → PASS**

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx vitest run components/dashboard/__tests__/StatsCards.test.tsx
```
Expected: 9 PASS

- [ ] **Step 5: Lint + TypeCheck**

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx tsc --noEmit && npm run lint
```
Expected: clean

- [ ] **Step 6: Commit**

```bash
cd /Users/sheyla/Projects/prisma-capstone
git add frontend/components/dashboard/StatsCards.tsx frontend/components/dashboard/__tests__/StatsCards.test.tsx
git commit -m "feat(frontend): StatsCards Komponente (4 Karten — Letzter Run, Universen, Stocks, Top-Pick)"
```

---

## Task 2: `DashboardClient` erweitern + Integration

**Files:**
- Modify: `frontend/app/dashboard/dashboard-client.tsx`

**Pre-discovered context (don't re-explore):**

- `listStocks(limit, offset)` aus `frontend/lib/api/stocks.ts` existiert NICHT — `stocks.ts` exportiert nur `getFactsheet` und `getPrices`. Wir brauchen einen neuen API-Call.

Check first:
```bash
grep -n "export" frontend/lib/api/stocks.ts
grep -n "stocks" backend/interfaces/rest/routers/stocks.py | grep "@router"
```

Backend hat: `GET /api/v1/stocks` listet alle Stocks mit `total` Field (`StockListResponse`).

- [ ] **Step 1: `listStocks`-API-Function ergänzen**

In `frontend/lib/api/stocks.ts` ergänzen (nicht ersetzen):

```ts
export interface StockListResponse {
  items: StockRead[];
  total: number;
}

export function listStocks(limit = 1, offset = 0): Promise<StockListResponse> {
  return apiFetch<StockListResponse>(`/api/v1/stocks?limit=${limit}&offset=${offset}`);
}
```

Falls `StockListResponse` schon definiert ist (typecheck-Konflikt), nur `listStocks` ergänzen.

- [ ] **Step 2: `DashboardClient.tsx` erweitern**

In `frontend/app/dashboard/dashboard-client.tsx`:

**Imports oben ergänzen:**
```tsx
import { listStocks } from '@/lib/api/stocks';
import { getRankings } from '@/lib/api/runs';
import { StatsCards, type TopPick } from '@/components/dashboard/StatsCards';
```

**Im Component-Body nach den existierenden Queries:**
```tsx
// Stats-Card-Daten:
const stocksTotalQuery = useQuery({
  queryKey: ['stocks-total'],
  queryFn: () => listStocks(1, 0),
});

const latestCompletedRun = runs?.find((r) => r.status === 'completed') ?? null;

const rankingsQuery = useQuery({
  queryKey: ['rankings', latestCompletedRun?.id],
  queryFn: () => getRankings(latestCompletedRun!.id),
  enabled: latestCompletedRun !== null,
});

const latestRun = runs?.[0] ?? null;
const universeCount = universesData?.items.length ?? 0;
const stockCount = stocksTotalQuery.data?.total ?? 0;
const topPickItem = rankingsQuery.data?.find((r) => r.total_rank === 1);
const topPick: TopPick | null = topPickItem
  ? {
      ticker: topPickItem.ticker,
      isSweetSpot: topPickItem.is_sweet_spot,
      runId: latestCompletedRun!.id,
    }
  : null;
```

**Im Return — `<StatsCards>` vor der Tabelle einfügen:**

Den existierenden Render-Block (ab `return (...)` line 90) anpassen:

```tsx
return (
  <div className="space-y-6">
    <StatsCards
      latestRun={latestRun}
      universeCount={universeCount}
      stockCount={stockCount}
      topPick={topPick}
    />
    <div className="space-y-4">
      <div className="flex justify-end">
        {/* ... existing button ... */}
      </div>
      <Table>{/* ... existing table ... */}</Table>
    </div>
  </div>
);
```

**Wichtig:** Die Empty-/Loading-/Error-States für die Runs-Tabelle bleiben unverändert. Falls `runs === null`, soll StatsCards trotzdem rendern (mit `latestRun=null`). Daher: StatsCards aus dem early-return-Pfad herauslassen — sie sollte IMMER rendern, auch bei runs-Loading.

Refactor: extract Tabellen-Block in eine kleine sub-Komponente oder render StatsCards VOR dem early-return-Block. Wähle den Weg der weniger invasive ist.

- [ ] **Step 3: Manueller Smoke-Test über Vitest**

Vorhandener Dashboard-Test (`frontend/app/dashboard/__tests__/dashboard-client.test.tsx` falls existent) durchlaufen lassen — wenn er existing-Behavior testet, sollte er weiterhin passen wenn wir die Inner-Struktur nur ergänzen:

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
find . -name "dashboard-client.test*" -not -path "*/node_modules/*"
```

Falls Test existiert: anpassen so dass er auch mit dem neuen StatsCards-Block kompatibel ist. Falls nicht: minimaler neuer Test:

```tsx
// frontend/app/dashboard/__tests__/dashboard-client.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { DashboardClient } from '../dashboard-client';
import * as runsApi from '@/lib/api/runs';
import * as stocksApi from '@/lib/api/stocks';
import * as universesApi from '@/lib/api/universes';

function wrap(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('DashboardClient — StatsCards-Integration', () => {
  it('renders StatsCards above runs table', async () => {
    vi.spyOn(runsApi, 'listRuns').mockResolvedValue([
      {
        id: 'run-1',
        status: 'completed',
        universe_id: 'uni-1',
        created_at: '2026-05-28T10:00:00Z',
      },
    ]);
    vi.spyOn(universesApi, 'listUniverses').mockResolvedValue({
      items: [
        { id: 'uni-1', name: 'Demo-US-5', region: 'US', tickers: ['AAPL', 'MSFT'] },
      ],
      total: 1,
    });
    vi.spyOn(stocksApi, 'listStocks').mockResolvedValue({
      items: [],
      total: 5,
    });
    vi.spyOn(runsApi, 'getRankings').mockResolvedValue([
      {
        stock_id: 'stock-1',
        ticker: 'NVDA',
        total_rank: 1,
        weighted_avg: 1.5,
        is_sweet_spot: true,
        per_model_ranks: {},
      },
    ]);

    wrap(<DashboardClient />);
    await waitFor(() => expect(screen.getByText('NVDA')).toBeDefined());
    expect(screen.getByText('1')).toBeDefined(); // 1 Universum
    expect(screen.getByText('5')).toBeDefined(); // 5 Stocks
  });
});
```

- [ ] **Step 4: Build + Lint**

```bash
cd /Users/sheyla/Projects/prisma-capstone/frontend
npx tsc --noEmit && npm run lint && npm run test
```
Expected: alle clean / PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/sheyla/Projects/prisma-capstone
git add frontend/lib/api/stocks.ts frontend/app/dashboard/dashboard-client.tsx frontend/app/dashboard/__tests__/dashboard-client.test.tsx
git commit -m "feat(frontend): Dashboard zeigt 4 Stats-Karten über Runs-Tabelle"
```

---

## Task 3: Manual Verification + PR

- [ ] **Step 1: Frontend Dev-Server (vermutlich schon läuft)**

Wenn nicht: 
```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Backend Dev-Server (vermutlich schon läuft mit DATABASE_URL override)**

Wenn nicht:
```bash
cd /Users/sheyla/Projects/prisma-capstone
DATABASE_URL=postgresql+asyncpg://prisma:prisma@localhost:5432/prisma .venv/bin/uvicorn backend.interfaces.rest.app:create_app --factory --reload --port 8000
```

- [ ] **Step 3: Dashboard im Browser öffnen**

`http://localhost:3000/dashboard` oder `/`. Erwartung:
- 4 Stats-Karten oben in einer Reihe (Desktop) bzw. gestackt (Mobile)
- Letzter Run zeigt Datum + "Abgeschlossen"-Badge
- # Universen zeigt korrekte Zahl (Link zu /universes)
- # Stocks zeigt korrekte Zahl
- Top-Pick zeigt NVDA (oder den aktuellen Top-Stock) + Sweet-Spot-Sparkles wenn anwendbar

- [ ] **Step 4: Click-Verifikation**

- Klick auf Letzter-Run-Datum → navigiert zur Run-Detail-Page
- Klick auf Universen-Zahl → navigiert zu `/universes`
- Klick auf Top-Pick-Ticker → navigiert zur Factsheet-Page (mit echtem Memo dank #148)

- [ ] **Step 5: Edge-Case: Keine Runs**

Falls möglich (z.B. neue DB ohne Demo-Run): Karten zeigen "—" für Latest-Run + Top-Pick.

- [ ] **Step 6: PR erstellen**

```bash
cd /Users/sheyla/Projects/prisma-capstone
git push -u origin feat/dashboard-stats
gh pr create --title "feat(frontend): Dashboard-Stats — 4 Karten über Runs-Tabelle" --body "$(cat <<'EOF'
## Summary

Frontend-Backlog Priorität 5. Dashboard `/` zeigt jetzt 4 Stats-Karten über der existierenden Runs-Tabelle:

1. **Letzter Run** — Datum + Status-Badge, Link zur Run-Detail
2. **# Universen** — Anzahl, Link zu `/universes`
3. **# Stocks** — Anzahl im System
4. **Top-Pick** — Ticker des Rang-1-Stocks aus jüngstem completed Run, Sweet-Spot-Sparkles wenn anwendbar, Link zur Factsheet-Page

Frontend-only — kein Backend-Touch. Aggregation aus `listRuns()`, `listUniverses()`, `listStocks()`, `getRankings()` via Tanstack Query.

## Spec & Plan

- Spec: [`docs/specs/2026-05-28-dashboard-stats-design.md`](./docs/specs/2026-05-28-dashboard-stats-design.md)
- Plan: [`docs/superpowers/plans/2026-05-28-dashboard-stats.md`](./docs/superpowers/plans/2026-05-28-dashboard-stats.md)

## Test plan

- [x] Vitest: StatsCards Unit-Tests (9 Cases — alle Karten, Empty-States, Sweet-Spot-Conditional)
- [x] Vitest: DashboardClient Integration-Test (StatsCards wird gerendert + Daten korrekt)
- [x] Manual: Karten rendern korrekt mit echten Daten, Klicks navigieren wie spezifiziert
- [x] Manual: Mobile-Viewport — Karten stacken

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
