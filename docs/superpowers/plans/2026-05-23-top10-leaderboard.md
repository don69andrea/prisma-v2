# Top-10-Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Top-10-Spotlight-Sektion zwischen Run-Metadata und Rankings-Tabelle, die die besten Picks in einer Sekunde erfassbar macht — kombiniert Cards (für Ticker-Identifikation) und einen horizontalen Bar-Chart (für Score-Vergleich).

**Architecture:** Pure Daten-Transform in `lib/top10.ts`, drei Präsentations-Komponenten in `components/rankings/` (Container `TopTenLeaderboard`, Card-Grid `TopTenCards`, Recharts-BarChart `TopTenBars`). Container slottet in `app/rankings/[runId]/page.tsx` zwischen Metadata-Card und `RankingsTable`.

**Tech Stack:** Next.js 14, React, Vitest, @testing-library/react, recharts (^2.12.0, schon Dep), lucide-react, Tailwind, shadcn/ui.

**Spec:** `docs/specs/2026-05-23-top10-leaderboard-design.md`

---

## File Structure

**Neue Dateien:**
- `frontend/lib/top10.ts` — `selectTopN` Funktion
- `frontend/lib/__tests__/top10.test.ts` — Tests
- `frontend/components/rankings/TopTenLeaderboard.tsx` — Container
- `frontend/components/rankings/TopTenCards.tsx` — Karten-Grid
- `frontend/components/rankings/TopTenBars.tsx` — Recharts-BarChart
- `frontend/components/rankings/__tests__/TopTenLeaderboard.test.tsx`
- `frontend/components/rankings/__tests__/TopTenCards.test.tsx`
- `frontend/components/rankings/__tests__/TopTenBars.test.tsx`

**Geänderte Dateien:**
- `frontend/app/rankings/[runId]/page.tsx` — fügt `<TopTenLeaderboard>` ein

---

### Task 1: `selectTopN` Daten-Modul (TDD)

**Files:**
- Create: `frontend/lib/top10.ts`
- Test: `frontend/lib/__tests__/top10.test.ts`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/lib/__tests__/top10.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

import { selectTopN } from '../top10';
import type { RankingItem } from '@/lib/api/runs';

function makeItem(ticker: string, rank: number | null, avg: number | null = 0): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: avg,
    is_sweet_spot: false,
    per_model_ranks: {},
  };
}

describe('selectTopN', () => {
  it('leeres Array bleibt leer', () => {
    expect(selectTopN([], 10)).toEqual([]);
  });

  it('sortiert nach total_rank aufsteigend', () => {
    const items = [makeItem('C', 3), makeItem('A', 1), makeItem('B', 2)];
    expect(selectTopN(items, 10).map((i) => i.ticker)).toEqual(['A', 'B', 'C']);
  });

  it('limitiert auf n Items', () => {
    const items = [
      makeItem('A', 1),
      makeItem('B', 2),
      makeItem('C', 3),
      makeItem('D', 4),
      makeItem('E', 5),
    ];
    expect(selectTopN(items, 3).map((i) => i.ticker)).toEqual(['A', 'B', 'C']);
  });

  it('n größer als items.length → gibt alle items zurück', () => {
    const items = [makeItem('A', 1), makeItem('B', 2)];
    expect(selectTopN(items, 10)).toHaveLength(2);
  });

  it('Items mit total_rank=null landen am Ende', () => {
    const items = [
      makeItem('NULL1', null),
      makeItem('A', 1),
      makeItem('NULL2', null),
      makeItem('B', 2),
    ];
    expect(selectTopN(items, 10).map((i) => i.ticker)).toEqual(['A', 'B', 'NULL1', 'NULL2']);
  });

  it('ist non-mutating (Original-Array unverändert)', () => {
    const items = [makeItem('C', 3), makeItem('A', 1), makeItem('B', 2)];
    const originalOrder = items.map((i) => i.ticker);
    selectTopN(items, 10);
    expect(items.map((i) => i.ticker)).toEqual(originalOrder);
  });

  it('Default n=10', () => {
    const items = Array.from({ length: 15 }, (_, i) => makeItem(`T${i}`, i + 1));
    expect(selectTopN(items)).toHaveLength(10);
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run lib/__tests__/top10.test.ts
```

Expected: FAIL — `Cannot find module '../top10'`

- [ ] **Step 3: Implementierung**

Erstelle `frontend/lib/top10.ts`:

```typescript
import type { RankingItem } from '@/lib/api/runs';

/**
 * Sortiert items nach total_rank aufsteigend (nulls zuletzt) und gibt die ersten n zurück.
 * Non-mutating — gibt eine neue Liste zurück.
 */
export function selectTopN(items: RankingItem[], n = 10): RankingItem[] {
  return [...items]
    .sort((a, b) => {
      const ar = a.total_rank ?? Infinity;
      const br = b.total_rank ?? Infinity;
      if (ar === Infinity && br === Infinity) return 0;
      if (ar === Infinity) return 1;
      if (br === Infinity) return -1;
      return ar - br;
    })
    .slice(0, n);
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run lib/__tests__/top10.test.ts
```

Expected: PASS, 7 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/top10.ts frontend/lib/__tests__/top10.test.ts
git commit -m "feat(frontend): selectTopN — sortiert + limitiert Rankings-Items

Pure non-mutating Funktion, Nulls zuletzt. Vorbereitung für
Top-10-Leaderboard auf Rankings-Detail-Page.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `TopTenCards` Komponente (TDD)

**Files:**
- Create: `frontend/components/rankings/TopTenCards.tsx`
- Test: `frontend/components/rankings/__tests__/TopTenCards.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/components/rankings/__tests__/TopTenCards.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { TopTenCards } from '../TopTenCards';
import type { RankingItem } from '@/lib/api/runs';

function makeItem(ticker: string, rank: number, sweetSpot = false): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: rank,
    is_sweet_spot: sweetSpot,
    per_model_ranks: {},
  };
}

const items: RankingItem[] = [
  makeItem('AAPL', 1, true),
  makeItem('MSFT', 2, true),
  makeItem('NVDA', 3, false),
];

describe('TopTenCards', () => {
  it('rendert eine Karte pro Item', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
  });

  it('zeigt Rank-Badge mit Hash-Prefix', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText('#3')).toBeInTheDocument();
  });

  it('zeigt Sweet-Spot-Stern nur bei is_sweet_spot=true', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    const stars = screen.getAllByLabelText('Sweet-Spot');
    expect(stars).toHaveLength(2); // AAPL + MSFT
  });

  it('Sweet-Spot-Karten haben Amber-Border-Klasse', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    const aaplLink = screen.getByText('AAPL').closest('a');
    expect(aaplLink?.className).toMatch(/border-amber-400/);
    const nvdaLink = screen.getByText('NVDA').closest('a');
    expect(nvdaLink?.className).not.toMatch(/border-amber-400/);
  });

  it('jede Karte ist ein Link zur Factsheet-Route', () => {
    render(<TopTenCards items={items} runId="run-1" />);
    const aaplLink = screen.getByText('AAPL').closest('a');
    expect(aaplLink).toHaveAttribute('href', '/rankings/run-1/stock/AAPL');
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run components/rankings/__tests__/TopTenCards.test.tsx
```

Expected: FAIL — `Cannot find module '../TopTenCards'`

- [ ] **Step 3: Implementierung**

Erstelle `frontend/components/rankings/TopTenCards.tsx`:

```tsx
import Link from 'next/link';
import { Star } from 'lucide-react';

import { ROUTES } from '@/lib/routes';
import type { RankingItem } from '@/lib/api/runs';

interface Props {
  items: RankingItem[];
  runId: string;
}

export function TopTenCards({ items, runId }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {items.map((item) => {
        const sweetSpotClasses = item.is_sweet_spot
          ? 'border-amber-400 bg-amber-50/60 dark:border-amber-500 dark:bg-amber-950/30'
          : 'border-border bg-card';
        return (
          <Link
            key={item.ticker}
            href={ROUTES.factsheet(runId, item.ticker)}
            className={`block rounded-lg border p-3 transition-colors hover:bg-muted/50 ${sweetSpotClasses}`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                #{item.total_rank ?? '—'}
              </span>
              {item.is_sweet_spot && (
                <Star
                  className="h-3.5 w-3.5 fill-amber-400 text-amber-400"
                  aria-label="Sweet-Spot"
                />
              )}
            </div>
            <div className="mt-1 font-mono text-xl font-bold">{item.ticker}</div>
          </Link>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run components/rankings/__tests__/TopTenCards.test.tsx
```

Expected: PASS, 5 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/rankings/TopTenCards.tsx frontend/components/rankings/__tests__/TopTenCards.test.tsx
git commit -m "feat(frontend): TopTenCards — Karten-Grid mit Sweet-Spot-Akzent

10 Karten (2/3/5 Cols responsive), Rank-Badge + Ticker + Sweet-Spot-Stern.
Sweet-Spot-Karten in Amber-Border + dezenter Background-Tint.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `TopTenBars` Komponente (TDD)

**Files:**
- Create: `frontend/components/rankings/TopTenBars.tsx`
- Test: `frontend/components/rankings/__tests__/TopTenBars.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/components/rankings/__tests__/TopTenBars.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { TopTenBars } from '../TopTenBars';
import type { RankingItem } from '@/lib/api/runs';

// next/navigation mock — Recharts-Klick navigiert via router.push
const pushMock = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

// Recharts braucht Dimensionen in jsdom — ResponsiveContainer mit Fixed-Size mocken
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  };
});

function makeItem(ticker: string, rank: number, avg: number, sweetSpot = false): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: avg,
    is_sweet_spot: sweetSpot,
    per_model_ranks: {},
  };
}

const items: RankingItem[] = [
  makeItem('AAPL', 1, 1.8, true),
  makeItem('MSFT', 2, 2.2, true),
  makeItem('NVDA', 3, 2.5, false),
];

describe('TopTenBars', () => {
  it('rendert für jedes Item einen Tick mit Ticker', () => {
    render(<TopTenBars items={items} runId="run-1" />);
    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.getByText('NVDA')).toBeInTheDocument();
  });

  it('Sweet-Spot-Bars haben Amber-Fill, andere Primary-Fill', () => {
    const { container } = render(<TopTenBars items={items} runId="run-1" />);
    const cells = container.querySelectorAll('.recharts-bar-rectangle path');
    // 3 Bars — AAPL und MSFT sind sweet-spot (Amber), NVDA nicht
    const fills = Array.from(cells).map((c) => c.getAttribute('fill'));
    const amberCount = fills.filter((f) => f === '#f59e0b').length;
    expect(amberCount).toBe(2);
  });

  it('Klick auf Y-Tick-Label navigiert zur Factsheet', () => {
    render(<TopTenBars items={items} runId="run-1" />);
    const aaplLabel = screen.getByText('AAPL');
    fireEvent.click(aaplLabel);
    expect(pushMock).toHaveBeenCalledWith('/rankings/run-1/stock/AAPL');
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run components/rankings/__tests__/TopTenBars.test.tsx
```

Expected: FAIL — `Cannot find module '../TopTenBars'`

- [ ] **Step 3: Implementierung**

Erstelle `frontend/components/rankings/TopTenBars.tsx`:

```tsx
'use client';

import { useRouter } from 'next/navigation';
import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts';

import { ROUTES } from '@/lib/routes';
import type { RankingItem } from '@/lib/api/runs';

interface Props {
  items: RankingItem[];
  runId: string;
}

interface ChartDatum {
  ticker: string;
  weighted_avg: number;
  is_sweet_spot: boolean;
}

const AMBER = '#f59e0b';
const PRIMARY = 'hsl(var(--primary))';

function TickLabel(props: {
  x?: number;
  y?: number;
  payload?: { value: string };
  data: ChartDatum[];
  onClick: (ticker: string) => void;
}) {
  const { x, y, payload, data, onClick } = props;
  if (!payload) return null;
  const ticker = payload.value;
  const datum = data.find((d) => d.ticker === ticker);
  const fill = datum?.is_sweet_spot ? AMBER : 'currentColor';
  return (
    <text
      x={x}
      y={y}
      dy={4}
      textAnchor="end"
      className="cursor-pointer font-mono text-xs"
      fill={fill}
      onClick={() => onClick(ticker)}
    >
      {ticker}
    </text>
  );
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartDatum }> }) {
  if (!active || !payload || payload.length === 0) return null;
  const { ticker, weighted_avg, is_sweet_spot } = payload[0].payload;
  return (
    <div className="rounded border bg-popover px-2 py-1 text-sm text-popover-foreground shadow-sm">
      <span className="font-mono">{ticker}</span>
      <span className="text-muted-foreground"> — Avg {weighted_avg.toFixed(2)}</span>
      {is_sweet_spot && <span className="text-amber-500"> • Sweet-Spot</span>}
    </div>
  );
}

export function TopTenBars({ items, runId }: Props) {
  const router = useRouter();
  const chartData: ChartDatum[] = items.map((item) => ({
    ticker: item.ticker,
    weighted_avg: item.weighted_avg ?? 0,
    is_sweet_spot: item.is_sweet_spot,
  }));

  const handleNavigate = (ticker: string) => {
    router.push(ROUTES.factsheet(runId, ticker));
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart
        data={chartData}
        layout="vertical"
        margin={{ top: 4, right: 32, bottom: 4, left: 4 }}
      >
        <XAxis type="number" hide reversed />
        <YAxis
          type="category"
          dataKey="ticker"
          width={64}
          tickLine={false}
          axisLine={false}
          tick={(tickProps) => (
            <TickLabel {...tickProps} data={chartData} onClick={handleNavigate} />
          )}
        />
        <Tooltip cursor={{ fill: 'hsl(var(--muted))', opacity: 0.3 }} content={<CustomTooltip />} />
        <Bar dataKey="weighted_avg" radius={[0, 4, 4, 0]}>
          {chartData.map((entry, index) => (
            <Cell key={index} fill={entry.is_sweet_spot ? AMBER : PRIMARY} />
          ))}
          <LabelList
            dataKey="weighted_avg"
            position="right"
            formatter={(value: number) => value.toFixed(2)}
            className="fill-foreground text-xs"
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run components/rankings/__tests__/TopTenBars.test.tsx
```

Expected: PASS, 3 Tests grün.

> **Falls Test 2 ("Amber-Fill") fehlschlägt** weil Recharts die Fills auf andere Elemente setzt: alternative DOM-Selektor `container.querySelectorAll('g.recharts-bar > g > path')` oder direkt auf `<rect>`. Inspiziere `container.innerHTML` mit `screen.debug()` und passe an. Die Assertion-Logik (2 von 3 Bars in Amber) bleibt gleich.

> **Falls Test 3 ("Y-Tick-Klick") fehlschlägt:** Custom-Tick rendert nur wenn Recharts die `tick`-Prop akzeptiert. Wenn der `text`-Knoten nicht klickbar ist, ist evtl. der ganze `<g>`-Wrapper darüber das Klick-Target. Fallback: pointer-Events expliziter setzen oder ein `<g>` um den `<text>` legen mit `onClick`.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/rankings/TopTenBars.tsx frontend/components/rankings/__tests__/TopTenBars.test.tsx
git commit -m "feat(frontend): TopTenBars — Recharts horizontaler BarChart

Top-10 als horizontale Bars, Amber für Sweet-Spot, Primary sonst.
Y-Tick-Klick navigiert zur Factsheet. Custom-Tooltip mit Ticker+Score.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `TopTenLeaderboard` Container (TDD)

**Files:**
- Create: `frontend/components/rankings/TopTenLeaderboard.tsx`
- Test: `frontend/components/rankings/__tests__/TopTenLeaderboard.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/components/rankings/__tests__/TopTenLeaderboard.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { TopTenLeaderboard } from '../TopTenLeaderboard';
import type { RankingItem } from '@/lib/api/runs';

// Recharts ResponsiveContainer Mock (siehe TopTenBars-Test)
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 600, height: 300 }}>{children}</div>
    ),
  };
});

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function makeItem(ticker: string, rank: number): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: rank,
    is_sweet_spot: false,
    per_model_ranks: {},
  };
}

describe('TopTenLeaderboard', () => {
  it('rendert null bei leerer items-Liste', () => {
    const { container } = render(<TopTenLeaderboard items={[]} runId="run-1" />);
    expect(container.firstChild).toBeNull();
  });

  it('Section-Header zeigt "Top 10" bei ≥10 Items', () => {
    const items = Array.from({ length: 12 }, (_, i) => makeItem(`T${i}`, i + 1));
    render(<TopTenLeaderboard items={items} runId="run-1" />);
    expect(screen.getByRole('heading', { name: /Top 10/ })).toBeInTheDocument();
  });

  it('Section-Header zeigt "Top 5" bei 5 Items', () => {
    const items = Array.from({ length: 5 }, (_, i) => makeItem(`T${i}`, i + 1));
    render(<TopTenLeaderboard items={items} runId="run-1" />);
    expect(screen.getByRole('heading', { name: /Top 5/ })).toBeInTheDocument();
  });

  it('rendert maximal 10 Karten auch bei mehr Items', () => {
    const items = Array.from({ length: 15 }, (_, i) => makeItem(`T${i}`, i + 1));
    render(<TopTenLeaderboard items={items} runId="run-1" />);
    // Karten sind Links → genau 10
    expect(screen.getAllByRole('link')).toHaveLength(10);
  });

  it('sortiert nach total_rank (T0 mit rank=1 ist erste Karte)', () => {
    const items = [makeItem('LAST', 99), makeItem('FIRST', 1), makeItem('MID', 50)];
    render(<TopTenLeaderboard items={items} runId="run-1" />);
    const links = screen.getAllByRole('link');
    expect(links[0]).toHaveTextContent('FIRST');
    expect(links[1]).toHaveTextContent('MID');
    expect(links[2]).toHaveTextContent('LAST');
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run components/rankings/__tests__/TopTenLeaderboard.test.tsx
```

Expected: FAIL — `Cannot find module '../TopTenLeaderboard'`

- [ ] **Step 3: Implementierung**

Erstelle `frontend/components/rankings/TopTenLeaderboard.tsx`:

```tsx
import { selectTopN } from '@/lib/top10';
import type { RankingItem } from '@/lib/api/runs';

import { TopTenCards } from './TopTenCards';
import { TopTenBars } from './TopTenBars';

interface Props {
  items: RankingItem[];
  runId: string;
}

export function TopTenLeaderboard({ items, runId }: Props) {
  if (items.length === 0) return null;
  const topN = selectTopN(items, 10);
  const n = topN.length;

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold tracking-tight">Top {n}</h2>
      <TopTenCards items={topN} runId={runId} />
      <TopTenBars items={topN} runId={runId} />
    </section>
  );
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run components/rankings/__tests__/TopTenLeaderboard.test.tsx
```

Expected: PASS, 5 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/rankings/TopTenLeaderboard.tsx frontend/components/rankings/__tests__/TopTenLeaderboard.test.tsx
git commit -m "feat(frontend): TopTenLeaderboard Container

Section-Header + TopTenCards + TopTenBars. Rendert null bei leerer
Liste, zeigt 'Top N' mit dynamischem N.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Integration in Rankings-Detail-Page

**Files:**
- Modify: `frontend/app/rankings/[runId]/page.tsx`

- [ ] **Step 1: Import ergänzen**

In `frontend/app/rankings/[runId]/page.tsx`, nach Zeile 13 (`import { RankingsTable } from './rankings-table';`) einfügen:

```tsx
import { TopTenLeaderboard } from '@/components/rankings/TopTenLeaderboard';
```

- [ ] **Step 2: Komponente einfügen**

In `frontend/app/rankings/[runId]/page.tsx`, suche die Zeile:

```tsx
      {isCompleted && rankingsQuery.data && (
        <RankingsTable items={rankingsQuery.data} runId={params.runId} />
      )}
```

Ersetze durch:

```tsx
      {isCompleted && rankingsQuery.data && (
        <>
          <TopTenLeaderboard items={rankingsQuery.data} runId={params.runId} />
          <RankingsTable items={rankingsQuery.data} runId={params.runId} />
        </>
      )}
```

- [ ] **Step 3: Verifikation**

```bash
cd frontend && npx vitest run && npx tsc --noEmit && npm run lint
```

Expected: alle Tests grün, kein Type-Error, kein Lint-Warning.

- [ ] **Step 4: Dev-Server Smoke-Test**

```bash
cd frontend && npm run dev
```

Öffne `http://localhost:3000/rankings/{any-completed-run-id}`. Erwarte:
- Top-10-Sektion zwischen Metadata-Card und Tabelle
- Karten mit Rank, Ticker, Sweet-Spot-Stern für entsprechende Tickers
- Bar-Chart darunter
- Klick auf Karte → Factsheet-Page
- Klick auf Bar-Y-Tick → Factsheet-Page

Stoppe Dev-Server mit Ctrl-C.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/rankings/[runId]/page.tsx
git commit -m "feat(frontend): Top-10-Leaderboard auf Rankings-Detail-Page

Sektion zwischen Run-Metadata und Tabelle. Greift nur bei completed
runs mit non-empty rankings.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Verifikation (Pre-Push-Mirror) + Manual Smoke

**Files:** keine — Validation-Schritt.

- [ ] **Step 1: Frontend Lint + Typecheck + Tests**

```bash
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Expected: alle grün. Bei Fail: fixen und neu committen, **nicht** weitermachen.

- [ ] **Step 2: Frontend Production Build (Smoke)**

```bash
cd frontend && npm run build
```

Expected: erfolgreich. Bundle-Size für `/rankings/[runId]` wird leicht steigen — das ist OK.

- [ ] **Step 3: Backend-CI-Mirror (unverändertes Backend, sollte grün bleiben)**

```bash
cd backend && uv run mypy . && uv run ruff check . && uv run ruff format --check . && uv run pytest tests/unit -q
```

Expected: grün.

> **Warum auch Backend prüfen:** Sheylas Pre-Push-Mirror-Regel aus ihrer Memory `feedback_pre_push_ci_mirror`. Integration-Tests brauchen Postgres — die laufen wir hier nicht.

- [ ] **Step 4: Manuelle Browser-Verifikation**

```bash
cd frontend && npm run dev
```

In `http://localhost:3000`:

1. Zu `/rankings/[completed-runId]` navigieren.
2. **Karten-Section:**
   - Genau 10 Karten sichtbar (oder weniger, falls Universum kleiner)
   - Karten zeigen `#1`, `#2`, …
   - Sweet-Spot-Karten haben Amber-Border + Stern oben rechts
   - Hover: leichter Background-Shift
   - Klick auf eine Karte → Factsheet öffnet
3. **Bar-Chart:**
   - 10 horizontale Bars, sortiert (#1 oben, längste Bar)
   - Sweet-Spot-Bars in Amber, andere in Primary-Blau
   - Hover über Bar zeigt Custom-Tooltip mit Ticker + Avg + Sweet-Spot
   - Klick auf Y-Tick-Label → Factsheet öffnet
4. **Layout:**
   - Top-10-Sektion liegt zwischen Metadata-Card und Tabelle
   - Tabelle ist immer noch da, mit allen Features (Sort, Filter, CSV)
5. **Mobile-Viewport (DevTools-Toggle):** Karten 2 Cols, Bar-Chart bleibt lesbar.

Dev-Server stoppen.

- [ ] **Step 5: Push + PR (durch Mensch ausgelöst)**

```bash
git push -u origin feat/top10-leaderboard
gh pr create --title "feat(frontend): Top-10-Leaderboard (Items 3+4)" --body "..."
```

(Wird nach Sheylas Freigabe gemacht, nicht automatisch.)

---

## Self-Review

- **Spec-Coverage:**
  - `selectTopN` Daten-Transform → Task 1 ✓
  - TopTenLeaderboard Container → Task 4 ✓
  - TopTenCards mit Sweet-Spot-Akzent → Task 2 ✓
  - TopTenBars Recharts → Task 3 ✓
  - Page-Integration → Task 5 ✓
  - Edge Cases (empty, < 10) → Task 1 Tests + Task 4 Tests ✓
  - A11y (Star aria-label, Card als Link) → Task 2 ✓
  - Click-Handler (Card-Link, Bar-Y-Tick) → Task 2 + Task 3 ✓
  - Verifikation → Task 6 ✓

- **Placeholder-Scan:** Keine TBDs, alle Code-Blöcke vollständig, Test-Code mit konkreten Assertions.

- **Type-Konsistenz:**
  - `RankingItem` aus `@/lib/api/runs` in allen Tasks korrekt importiert.
  - `selectTopN(items, n)` Signatur konsistent zwischen Task 1 (Definition) und Task 4 (Aufruf).
  - `TopTenCards`-Props `{ items, runId }` konsistent zwischen Tests, Implementation und Container-Aufruf.
  - `TopTenBars`-Props `{ items, runId }` konsistent.
  - `ChartDatum` ist lokal in Task 3, nicht extern referenziert.
  - `ROUTES.factsheet(runId, ticker)` in Cards (Task 2) und Bars (Task 3) gleich verwendet.

Plan ist intern stimmig und vollständig.
