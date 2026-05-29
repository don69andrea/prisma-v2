# Memo-Drilldown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Memo-Drilldown Frontend-Feature: Klick auf Rankings-Tabellen-Zeile öffnet Slide-In-Sheet mit strukturiertem Research-Memo (One-Liner, Stärken, Risiken, Widersprüche, Confidence). Backend-API ist vollständig; minimaler Backend-Touch nur für `stock_id` im `RankingItem`-Response. Gleiche Memo-Anzeige auch auf Factsheet-Page (Stub-Replacement).

**Architecture:** 3 Layer — (1) Backend: `RankingItem.stock_id: UUID | None` im Response-Schema + JSONB-Befüllung, (2) Frontend-API + Tanstack-Query-Hook (`useStockMemo`), (3) UI: `MemoContent` (Präsentation), `MemoSheet` (slide-in wrapper), `MemoEmpty`/`MemoErrorCard` (sub-states). Reusable Components — `MemoContent` lebt in Sheet UND Factsheet-`MemoPanel`.

**Tech Stack:** FastAPI/Python 3.12 (pytest, pydantic) — Next.js 14 (App Router) / TypeScript / Tanstack Query v5 / shadcn-ui / Vitest + Testing-Library / Tailwind CSS

**Spec:** `docs/specs/2026-05-28-memo-drilldown-design.md`

**Branch:** `feat/memo-drilldown`

---

## Task 1: Backend — `RankingItem` Schema um `stock_id` erweitern

**Files:**
- Modify: `backend/interfaces/rest/schemas/runs.py:52-57`
- Test: `backend/tests/unit/interfaces/test_runs_schema.py` (neu, falls noch nicht existent)

- [ ] **Step 1: Test-Datei vorbereiten + Failing Test**

Check ob `backend/tests/unit/interfaces/test_runs_schema.py` existiert. Wenn ja, Test ergänzen. Wenn nein, neu anlegen:

```python
"""Schema-Tests für runs-Response-Modelle."""
import uuid

import pytest

from backend.interfaces.rest.schemas.runs import RankingItem


pytestmark = pytest.mark.unit


class TestRankingItemSchema:
    def test_accepts_stock_id_uuid(self) -> None:
        """Neue Runs liefern stock_id als UUID — Schema akzeptiert es."""
        stock_id = uuid.uuid4()
        item = RankingItem.model_validate(
            {
                "stock_id": str(stock_id),
                "ticker": "AAPL",
                "total_rank": 1,
                "weighted_avg": 0.95,
                "is_sweet_spot": True,
                "per_model_ranks": {"quality_classic": 1},
            }
        )
        assert item.stock_id == stock_id

    def test_stock_id_optional_for_legacy_runs(self) -> None:
        """Alte Runs ohne stock_id im JSONB müssen valid sein (stock_id default None)."""
        item = RankingItem.model_validate(
            {
                "ticker": "MSFT",
                "total_rank": 2,
                "weighted_avg": 0.88,
                "is_sweet_spot": False,
                "per_model_ranks": {"quality_classic": 2},
            }
        )
        assert item.stock_id is None
```

- [ ] **Step 2: Test läuft und failt**

Run: `pytest backend/tests/unit/interfaces/test_runs_schema.py -v`
Expected: FAIL mit `ValidationError` für `extra_forbidden` (Pydantic-Default ist `extra="ignore"`, also kann es auch sein dass Test 1 fehlschlägt mit "stock_id field not defined") oder `AttributeError: stock_id`.

- [ ] **Step 3: `RankingItem` um `stock_id` erweitern**

In `backend/interfaces/rest/schemas/runs.py`:

```python
from uuid import UUID  # ggf. bereits importiert

class RankingItem(BaseModel):
    stock_id: UUID | None = None
    ticker: str
    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool
    per_model_ranks: dict[str, int | None]
```

Wichtig: `UUID | None = None` — explizit default `None` für Backwards-Compat.

- [ ] **Step 4: Test läuft grün**

Run: `pytest backend/tests/unit/interfaces/test_runs_schema.py -v`
Expected: 2 PASSED

- [ ] **Step 5: mypy + ruff check**

Run:
```bash
cd backend && mypy backend/interfaces/rest/schemas/runs.py
cd .. && ruff check backend/interfaces/rest/schemas/runs.py backend/tests/unit/interfaces/test_runs_schema.py
ruff format --check backend/interfaces/rest/schemas/runs.py backend/tests/unit/interfaces/test_runs_schema.py
```
Expected: alle clean

- [ ] **Step 6: Commit**

```bash
git add backend/interfaces/rest/schemas/runs.py backend/tests/unit/interfaces/test_runs_schema.py
git commit -m "feat(api): RankingItem.stock_id (Optional, Backwards-Compat)"
```

---

## Task 2: Backend — `stock_id` in JSONB-Results befüllen

**Files:**
- Modify: `backend/application/services/ranking_run_service.py:71-110` (Run-Compute mit results-Build)
- Test: `backend/tests/unit/application/test_ranking_run_service.py` (existiert vermutlich; erweitern oder neuen Test ergänzen)

**Context:** Im aktuellen `ranking_run_service.py:87-101` wird das `results`-JSONB so gebaut:

```python
results: list[dict[str, Any]] = sorted(
    [
        {
            "ticker": r.ticker,
            "total_rank": r.total_rank,
            "weighted_avg": r.weighted_avg,
            "is_sweet_spot": r.is_sweet_spot,
            "per_model_ranks": {...},
        }
        for r in total_results
    ],
    key=lambda x: (x["total_rank"] is None, x["total_rank"] or 0),
)
```

Wir wollen ein `"stock_id"`-Feld ergänzen. Lookup-Strategie: vor dem List-Comprehension ein `ticker → stock_id` Mapping bauen via `StockService.get_by_ticker(ticker)`.

- [ ] **Step 1: Existence-Check für `StockService` im `RankingRunService`-Konstruktor**

Read: `backend/application/services/ranking_run_service.py:34-70` (Konstruktor + `__init__`)

Prüfen ob `_stock_service` oder `_stock_repo` bereits injiziert ist. Falls nicht: in Task 2 ergänzen wir die DI.

```bash
sed -n '30,70p' backend/application/services/ranking_run_service.py
```

- [ ] **Step 2: Failing Test schreiben**

Datei: `backend/tests/unit/application/test_ranking_run_service.py` (existiert vermutlich)

Test ergänzen oder neuen Test schreiben:

```python
async def test_compute_run_writes_stock_id_in_results(
    repo, stock_service_with_aapl, universe_repo, mock_market_data
) -> None:
    """Nach einem Run muss jedes Result-Item die stock_id im JSONB haben."""
    # stock_service_with_aapl: Fixture mit Stock(ticker='AAPL', id=KNOWN_AAPL_ID)
    service = RankingRunService(
        run_repository=repo,
        universe_repository=universe_repo,
        market_data_provider=mock_market_data,
        stock_service=stock_service_with_aapl,
        # ggf. weitere Deps
    )
    run = await service.compute_run(universe_id=...)
    results = await repo.get_results(run.id)
    aapl_result = next(r for r in results if r["ticker"] == "AAPL")
    assert aapl_result["stock_id"] == str(KNOWN_AAPL_ID)
```

Konkret: Test-Setup an existierenden Pattern in `test_ranking_run_service.py` anpassen (keine erratenen Fixtures verwenden — die bestehenden anschauen).

- [ ] **Step 3: Test läuft und failt**

Run: `pytest backend/tests/unit/application/test_ranking_run_service.py::test_compute_run_writes_stock_id_in_results -v`
Expected: FAIL — KeyError oder AssertionError weil `stock_id` nicht im Dict ist

- [ ] **Step 4: Service-Logik anpassen**

In `backend/application/services/ranking_run_service.py`:

```python
# Vor der Result-Comprehension:
tickers_in_results = [r.ticker for r in total_results]
stock_id_by_ticker: dict[str, UUID | None] = {}
for ticker in tickers_in_results:
    stock = await self._stock_service.get_by_ticker(ticker)
    stock_id_by_ticker[ticker] = stock.id if stock else None

results: list[dict[str, Any]] = sorted(
    [
        {
            "stock_id": str(stock_id_by_ticker[r.ticker])
            if stock_id_by_ticker[r.ticker] is not None
            else None,
            "ticker": r.ticker,
            "total_rank": r.total_rank,
            "weighted_avg": r.weighted_avg,
            "is_sweet_spot": r.is_sweet_spot,
            "per_model_ranks": {
                model_name: ticker_ranks.get(r.ticker)
                for model_name, ticker_ranks in ticker_to_model_rank.items()
            },
        }
        for r in total_results
    ],
    key=lambda x: (x["total_rank"] is None, x["total_rank"] or 0),
)
```

Wichtig: JSONB-Serialization erlaubt String/null, daher `str(uuid)` schreiben. Pydantic's `UUID | None` akzeptiert String beim `model_validate`.

- [ ] **Step 5: Wenn `_stock_service` nicht im Konstruktor war: Konstruktor + DI ergänzen**

Wenn Step 1 ergab, dass `RankingRunService.__init__` keinen `stock_service` hat:

1. Konstruktor erweitern: `stock_service: StockService` als kwarg
2. `backend/interfaces/rest/dependencies.py`: `get_ranking_run_service()` mit `stock_service: StockService = Depends(get_stock_service)` erweitern und an `RankingRunService()` durchreichen
3. Falls existierende Tests von `RankingRunService` fehlschlagen wegen neuem Required-Arg → Test-Fixtures anpassen

- [ ] **Step 6: Test grün**

Run: `pytest backend/tests/unit/application/test_ranking_run_service.py -v`
Expected: alle PASS (alter + neuer Test)

- [ ] **Step 7: Integration-Test**

Run: `pytest backend/tests/integration/test_runs_endpoint.py -v`
Expected: PASS (Schema-Änderung bricht keine bestehenden Integration-Tests)

- [ ] **Step 8: Pre-Push CI-Mirror**

Run:
```bash
cd backend && mypy backend/application/services/ranking_run_service.py && cd ..
ruff check backend/application/services/ranking_run_service.py backend/tests/unit/application/test_ranking_run_service.py
ruff format --check backend/application/services/ranking_run_service.py
```
Expected: clean

- [ ] **Step 9: Commit**

```bash
git add backend/application/services/ranking_run_service.py backend/interfaces/rest/dependencies.py backend/tests/unit/application/test_ranking_run_service.py
git commit -m "feat(rankings): stock_id in JSONB-Results befüllen für Memo-API-Lookup"
```

---

## Task 3: Frontend — shadcn `Sheet`-Komponente installieren

**Files:**
- Create: `frontend/components/ui/sheet.tsx` (durch shadcn CLI generiert)

- [ ] **Step 1: shadcn-Sheet installieren**

```bash
cd frontend && npx shadcn@latest add sheet
```

Erwartete Datei: `frontend/components/ui/sheet.tsx` (rund 130 Zeilen, exportiert `Sheet`, `SheetTrigger`, `SheetContent`, `SheetHeader`, `SheetTitle`, `SheetDescription`, `SheetFooter`, `SheetClose`)

- [ ] **Step 2: Build-Verifikation**

Run:
```bash
cd frontend && npm run lint && npm run build
```
Expected: clean (Sheet-Komponente ist self-contained, sollte build-clean sein)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ui/sheet.tsx frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): shadcn Sheet-Komponente hinzufügen"
```

---

## Task 4: Frontend — Memo-API-Layer erweitern

**Files:**
- Modify: `frontend/lib/api/memos.ts` (Memo-Schema voll, `getMemo` ergänzen)
- Modify: `frontend/lib/api/runs.ts` (RankingItem um `stock_id?: string | null`)

- [ ] **Step 1: `RankingItem` im Frontend-Type um `stock_id` ergänzen**

In `frontend/lib/api/runs.ts:12-18`:

```ts
export interface RankingItem {
  stock_id: string | null;  // NEU — null für alte Runs ohne stock_id im JSONB
  ticker: string;
  total_rank: number | null;
  weighted_avg: number | null;
  is_sweet_spot: boolean;
  per_model_ranks: Record<string, number | null>;
}
```

- [ ] **Step 2: `memos.ts` Memo-Type voll erweitern**

`frontend/lib/api/memos.ts` komplett ersetzen mit:

```ts
import { apiFetch, ApiError } from './client';

// Spiegelt backend/domain/entities/research_memo.py:ContradictionItem
export interface ContradictionItem {
  model_a: string;
  model_b: string;
  description: string;
}

// Spiegelt backend/interfaces/rest/routers/memos.py:MemoResponse
export interface Memo {
  id: string;
  stock_id: string;
  model_run_id: string;
  language: 'de' | 'en';
  one_liner: string;
  ranking_interpretation: string;
  sweet_spot: boolean;
  sweet_spot_explanation: string | null;
  contradictions: ContradictionItem[];
  key_strengths: string[];
  key_risks: string[];
  confidence: 'low' | 'medium' | 'high';
  model_version: string;
  created_at: string;
  is_error: boolean;
}

/**
 * Holt ein Memo für (stock_id, run_id). Gibt null zurück bei 404 (kein Memo existiert).
 */
export async function getMemo(stockId: string, runId: string): Promise<Memo | null> {
  try {
    return await apiFetch<Memo>(`/api/v1/memos/${stockId}/${runId}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

export function generateMemo(
  stockId: string,
  modelRunId: string,
  language: 'de' | 'en' = 'de',
): Promise<Memo> {
  return apiFetch<Memo>('/api/v1/memos/generate', {
    method: 'POST',
    body: JSON.stringify({ stock_id: stockId, model_run_id: modelRunId, language }),
  });
}
```

- [ ] **Step 3: TS-Compile-Check**

Run:
```bash
cd frontend && npx tsc --noEmit
```
Expected: keine Errors. Falls existing Code `Memo.content` nutzt (alter Stub): Error wird angezeigt. Lösung: nur in Step 2 prüfen ob Memo.content nirgends mehr referenziert wird.

```bash
grep -rn "Memo.content\|memo\.content" frontend --include="*.ts" --include="*.tsx" | grep -v node_modules
```
Wenn Treffer: in jeweiliger Datei auf neue Felder anpassen oder vorerst kommentieren (wird in späteren Tasks ersetzt).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/api/memos.ts frontend/lib/api/runs.ts
git commit -m "feat(frontend): Memo-API-Schema voll + getMemo() + RankingItem.stock_id"
```

---

## Task 5: Frontend — `useStockMemo` Hook + Test

**Files:**
- Create: `frontend/lib/hooks/useStockMemo.ts`
- Create: `frontend/lib/hooks/__tests__/useStockMemo.test.tsx`

- [ ] **Step 1: Failing Test schreiben**

Erstelle `frontend/lib/hooks/__tests__/useStockMemo.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { useStockMemo } from '../useStockMemo';
import * as memosApi from '@/lib/api/memos';
import type { Memo } from '@/lib/api/memos';

const STOCK_ID = '11111111-1111-1111-1111-111111111111';
const RUN_ID = '22222222-2222-2222-2222-222222222222';

const fakeMemo: Memo = {
  id: 'memo-1',
  stock_id: STOCK_ID,
  model_run_id: RUN_ID,
  language: 'de',
  one_liner: 'Solide Quality-Geschichte mit Trend-Rückenwind.',
  ranking_interpretation: 'Interpretation.',
  sweet_spot: true,
  sweet_spot_explanation: 'Top-Quintil in allen 5 Modellen.',
  contradictions: [],
  key_strengths: ['Strong ROE', 'Low Debt'],
  key_risks: ['China-Exposure'],
  confidence: 'high',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useStockMemo', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns memo when API returns 200', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    const { result } = renderHook(() => useStockMemo(STOCK_ID, RUN_ID), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.memo).toEqual(fakeMemo);
  });

  it('returns null when API returns 404', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    const { result } = renderHook(() => useStockMemo(STOCK_ID, RUN_ID), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.memo).toBeNull();
  });

  it('does not query when stockId is null', () => {
    const spy = vi.spyOn(memosApi, 'getMemo');
    renderHook(() => useStockMemo(null, RUN_ID), { wrapper });
    expect(spy).not.toHaveBeenCalled();
  });

  it('generate() triggers POST and invalidates query', async () => {
    const getSpy = vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    const genSpy = vi.spyOn(memosApi, 'generateMemo').mockResolvedValue(fakeMemo);

    const { result } = renderHook(() => useStockMemo(STOCK_ID, RUN_ID), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.memo).toBeNull();

    await act(async () => {
      await result.current.generate();
    });

    expect(genSpy).toHaveBeenCalledWith(STOCK_ID, RUN_ID, 'de');
    await waitFor(() => expect(getSpy.mock.calls.length).toBeGreaterThanOrEqual(2));
  });
});
```

- [ ] **Step 2: Test ausführen — failt mit "useStockMemo nicht gefunden"**

Run: `cd frontend && npx vitest run lib/hooks/__tests__/useStockMemo.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: Hook implementieren**

Erstelle `frontend/lib/hooks/useStockMemo.ts`:

```ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { getMemo, generateMemo, type Memo } from '@/lib/api/memos';

export interface UseStockMemoResult {
  memo: Memo | null | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  generate: () => Promise<Memo>;
  isGenerating: boolean;
}

/**
 * Lädt ein Memo für (stockId, runId) und stellt Generate-Mutation bereit.
 * Wenn stockId null ist (z.B. legacy Run ohne stock_id), wird kein Query ausgeführt.
 */
export function useStockMemo(stockId: string | null, runId: string): UseStockMemoResult {
  const queryClient = useQueryClient();
  const queryKey = ['memo', stockId, runId];

  const query = useQuery({
    queryKey,
    queryFn: () => getMemo(stockId!, runId),
    enabled: stockId !== null,
    staleTime: 5 * 60 * 1000,
  });

  const mutation = useMutation({
    mutationFn: () => generateMemo(stockId!, runId, 'de'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return {
    memo: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error as Error | null,
    generate: () => mutation.mutateAsync(),
    isGenerating: mutation.isPending,
  };
}
```

- [ ] **Step 4: Test grün**

Run: `cd frontend && npx vitest run lib/hooks/__tests__/useStockMemo.test.tsx`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/hooks/useStockMemo.ts frontend/lib/hooks/__tests__/useStockMemo.test.tsx
git commit -m "feat(frontend): useStockMemo Hook — fetch + generate via Tanstack Query"
```

---

## Task 6: Frontend — `MemoContent` Präsentations-Komponente + Test

**Files:**
- Create: `frontend/components/factsheet/MemoContent.tsx`
- Create: `frontend/components/factsheet/__tests__/MemoContent.test.tsx`

- [ ] **Step 1: Failing Test schreiben**

Erstelle `frontend/components/factsheet/__tests__/MemoContent.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MemoContent } from '../MemoContent';
import type { Memo } from '@/lib/api/memos';

const baseMemo: Memo = {
  id: 'memo-1',
  stock_id: 'stock-1',
  model_run_id: 'run-1',
  language: 'de',
  one_liner: 'Solide Quality-Geschichte mit Trend-Rückenwind.',
  ranking_interpretation: 'Stock liegt im Top-Quintil aller 5 Modelle.',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: ['Strong ROE', 'Low Debt'],
  key_risks: ['China-Exposure'],
  confidence: 'high',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

describe('MemoContent', () => {
  it('renders one_liner as hero', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/Solide Quality-Geschichte/)).toBeDefined();
  });

  it('renders all key_strengths', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText('Strong ROE')).toBeDefined();
    expect(screen.getByText('Low Debt')).toBeDefined();
  });

  it('renders all key_risks', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText('China-Exposure')).toBeDefined();
  });

  it('renders confidence badge', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/high/i)).toBeDefined();
  });

  it('hides sweet-spot card when sweet_spot is false', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.queryByText(/Sweet-Spot/)).toBeNull();
  });

  it('shows sweet-spot card with explanation when sweet_spot=true', () => {
    const sweetMemo: Memo = {
      ...baseMemo,
      sweet_spot: true,
      sweet_spot_explanation: 'Top-Quintil in allen 5 Modellen.',
    };
    render(<MemoContent memo={sweetMemo} />);
    expect(screen.getByText(/Sweet-Spot/)).toBeDefined();
    expect(screen.getByText(/Top-Quintil in allen 5 Modellen/)).toBeDefined();
  });

  it('hides contradictions section when array is empty', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.queryByText(/Widersprüche/)).toBeNull();
  });

  it('shows contradictions with model_a, model_b, description', () => {
    const contraMemo: Memo = {
      ...baseMemo,
      contradictions: [
        { model_a: 'Quality', model_b: 'Value', description: 'Hohe Margen, aber teuer.' },
      ],
    };
    render(<MemoContent memo={contraMemo} />);
    expect(screen.getByText(/Widersprüche/)).toBeDefined();
    expect(screen.getByText(/Quality/)).toBeDefined();
    expect(screen.getByText(/Value/)).toBeDefined();
    expect(screen.getByText(/Hohe Margen, aber teuer/)).toBeDefined();
  });

  it('renders ranking_interpretation', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/Top-Quintil aller 5 Modelle/)).toBeDefined();
  });

  it('renders model_version in footer', () => {
    render(<MemoContent memo={baseMemo} />);
    expect(screen.getByText(/claude-sonnet-4-6/)).toBeDefined();
  });
});
```

- [ ] **Step 2: Test failt**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoContent.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: `MemoContent.tsx` implementieren**

Erstelle `frontend/components/factsheet/MemoContent.tsx`:

```tsx
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
    <div className="space-y-4">
      {/* Hero — One-Liner + Confidence */}
      <Card>
        <CardContent className="py-4 flex items-start justify-between gap-3">
          <p className="text-base font-medium italic text-foreground/90 leading-snug">
            &ldquo;{memo.one_liner}&rdquo;
          </p>
          <Badge variant={CONFIDENCE_VARIANT[memo.confidence]} className="shrink-0">
            {CONFIDENCE_LABEL[memo.confidence]}
          </Badge>
        </CardContent>
      </Card>

      {/* Sweet-Spot (conditional) */}
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

      {/* Stärken + Risiken — 2-Spalten */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Card>
          <CardContent className="py-3">
            <h3 className="text-sm font-semibold flex items-center gap-1.5 mb-2 text-emerald-700 dark:text-emerald-400">
              <Check className="h-4 w-4" /> Stärken
            </h3>
            <ul className="space-y-1 text-sm">
              {memo.key_strengths.map((s, i) => (
                <li key={i} className="text-muted-foreground">
                  &bull; {s}
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
                  &bull; {r}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* Widersprüche (conditional) */}
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
                    {c.model_a} <span className="text-muted-foreground">↔</span> {c.model_b}
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

      {/* Footer — Meta */}
      <div className="text-xs text-muted-foreground flex justify-between pt-1">
        <span>Modell: {memo.model_version}</span>
        <span>{new Date(memo.created_at).toLocaleDateString('de-CH')}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Test grün**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoContent.test.tsx`
Expected: 10 PASS

- [ ] **Step 5: Lint + TypeCheck**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add frontend/components/factsheet/MemoContent.tsx frontend/components/factsheet/__tests__/MemoContent.test.tsx
git commit -m "feat(frontend): MemoContent — strukturierte Memo-Anzeige (Hero/Sweet-Spot/Strengths+Risks/Contradictions)"
```

---

## Task 7: Frontend — `MemoEmpty` und `MemoErrorCard` Sub-States + Tests

**Files:**
- Create: `frontend/components/factsheet/MemoEmpty.tsx`
- Create: `frontend/components/factsheet/MemoErrorCard.tsx`
- Create: `frontend/components/factsheet/__tests__/MemoEmpty.test.tsx`
- Create: `frontend/components/factsheet/__tests__/MemoErrorCard.test.tsx`

- [ ] **Step 1: Tests schreiben**

`frontend/components/factsheet/__tests__/MemoEmpty.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { MemoEmpty } from '../MemoEmpty';

describe('MemoEmpty', () => {
  it('shows hint and generate button', () => {
    render(<MemoEmpty onGenerate={() => {}} isGenerating={false} />);
    expect(screen.getByText(/Noch kein Memo/)).toBeDefined();
    expect(screen.getByRole('button', { name: /Memo generieren/ })).toBeDefined();
  });

  it('calls onGenerate when button clicked', () => {
    const onGenerate = vi.fn();
    render(<MemoEmpty onGenerate={onGenerate} isGenerating={false} />);
    fireEvent.click(screen.getByRole('button', { name: /Memo generieren/ }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it('shows generating state when isGenerating', () => {
    render(<MemoEmpty onGenerate={() => {}} isGenerating={true} />);
    expect(screen.getByText(/Memo wird generiert/)).toBeDefined();
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

`frontend/components/factsheet/__tests__/MemoErrorCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { MemoErrorCard } from '../MemoErrorCard';
import type { Memo } from '@/lib/api/memos';

const errorMemo: Memo = {
  id: 'memo-err',
  stock_id: 'stock-1',
  model_run_id: 'run-1',
  language: 'de',
  one_liner: '',
  ranking_interpretation: '',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: [],
  key_risks: [],
  confidence: 'low',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: true,
};

describe('MemoErrorCard', () => {
  it('shows error state and regenerate button', () => {
    render(<MemoErrorCard memo={errorMemo} onRegenerate={() => {}} isGenerating={false} />);
    expect(screen.getByText(/fehlgeschlagen/i)).toBeDefined();
    expect(screen.getByRole('button', { name: /Erneut generieren/ })).toBeDefined();
  });

  it('calls onRegenerate on click', () => {
    const onRegenerate = vi.fn();
    render(<MemoErrorCard memo={errorMemo} onRegenerate={onRegenerate} isGenerating={false} />);
    fireEvent.click(screen.getByRole('button', { name: /Erneut generieren/ }));
    expect(onRegenerate).toHaveBeenCalledOnce();
  });

  it('disables button while regenerating', () => {
    render(<MemoErrorCard memo={errorMemo} onRegenerate={() => {}} isGenerating={true} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });
});
```

- [ ] **Step 2: Tests failen**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoEmpty.test.tsx components/factsheet/__tests__/MemoErrorCard.test.tsx`
Expected: FAIL — modules not found

- [ ] **Step 3: `MemoEmpty.tsx` implementieren**

```tsx
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
```

- [ ] **Step 4: `MemoErrorCard.tsx` implementieren**

```tsx
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
```

- [ ] **Step 5: Tests grün**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoEmpty.test.tsx components/factsheet/__tests__/MemoErrorCard.test.tsx`
Expected: 6 PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/components/factsheet/MemoEmpty.tsx frontend/components/factsheet/MemoErrorCard.tsx frontend/components/factsheet/__tests__/MemoEmpty.test.tsx frontend/components/factsheet/__tests__/MemoErrorCard.test.tsx
git commit -m "feat(frontend): MemoEmpty + MemoErrorCard — Sub-States für Memo-Sheet"
```

---

## Task 8: Frontend — `MemoSheet` Wrapper + Test

**Files:**
- Create: `frontend/components/factsheet/MemoSheet.tsx`
- Create: `frontend/components/factsheet/__tests__/MemoSheet.test.tsx`

- [ ] **Step 1: Failing Test schreiben**

`frontend/components/factsheet/__tests__/MemoSheet.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { MemoSheet } from '../MemoSheet';
import * as memosApi from '@/lib/api/memos';
import type { Memo } from '@/lib/api/memos';

const STOCK_ID = '11111111-1111-1111-1111-111111111111';
const RUN_ID = '22222222-2222-2222-2222-222222222222';

const fakeMemo: Memo = {
  id: 'memo-1',
  stock_id: STOCK_ID,
  model_run_id: RUN_ID,
  language: 'de',
  one_liner: 'Solider Pick.',
  ranking_interpretation: 'Top-Quintil.',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: ['Strong ROE'],
  key_risks: ['Volatility'],
  confidence: 'medium',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('MemoSheet', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders ticker in header when open', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(
      <MemoSheet
        stockId={STOCK_ID}
        runId={RUN_ID}
        ticker="AAPL"
        open={true}
        onOpenChange={() => {}}
      />,
    );
    await waitFor(() => expect(screen.getByText('AAPL')).toBeDefined());
  });

  it('renders MemoContent when memo loaded', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() => expect(screen.getByText(/Solider Pick/)).toBeDefined());
  });

  it('renders MemoEmpty when memo is null', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Memo generieren/ })).toBeDefined(),
    );
  });

  it('renders MemoErrorCard when memo.is_error', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue({ ...fakeMemo, is_error: true });
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() => expect(screen.getByText(/fehlgeschlagen/i)).toBeDefined());
  });

  it('renders nothing when stockId is null', () => {
    wrap(
      <MemoSheet stockId={null} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    expect(screen.queryByText('AAPL')).toBeNull();
  });

  it('shows factsheet-link in footer', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(
      <MemoSheet stockId={STOCK_ID} runId={RUN_ID} ticker="AAPL" open onOpenChange={() => {}} />,
    );
    await waitFor(() => {
      const link = screen.getByRole('link', { name: /Vollständiges Factsheet/ });
      expect(link.getAttribute('href')).toBe(`/rankings/${RUN_ID}/stock/AAPL`);
    });
  });
});
```

- [ ] **Step 2: Test failt**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoSheet.test.tsx`
Expected: FAIL

- [ ] **Step 3: `MemoSheet.tsx` implementieren**

```tsx
'use client';

import Link from 'next/link';
import { ExternalLink, Loader2 } from 'lucide-react';

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { useStockMemo } from '@/lib/hooks/useStockMemo';
import { MemoContent } from './MemoContent';
import { MemoEmpty } from './MemoEmpty';
import { MemoErrorCard } from './MemoErrorCard';

interface Props {
  stockId: string | null;
  runId: string;
  ticker: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MemoSheet({ stockId, runId, ticker, open, onOpenChange }: Props) {
  const { memo, isLoading, isError, error, generate, isGenerating } = useStockMemo(
    stockId,
    runId,
  );

  if (stockId === null) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-[640px] overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="text-2xl font-bold">{ticker}</SheetTitle>
          <SheetDescription>Research-Memo aus der Narrative-Engine</SheetDescription>
        </SheetHeader>

        <div className="mt-6 pb-6">
          {isLoading && (
            <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Memo wird geladen…</span>
            </div>
          )}

          {!isLoading && isError && (
            <div className="text-sm text-destructive py-4" role="alert">
              Memo konnte nicht geladen werden: {error?.message ?? 'Unbekannter Fehler'}
            </div>
          )}

          {!isLoading && !isError && memo === null && (
            <MemoEmpty onGenerate={generate} isGenerating={isGenerating} />
          )}

          {!isLoading && !isError && memo && memo.is_error && (
            <MemoErrorCard memo={memo} onRegenerate={generate} isGenerating={isGenerating} />
          )}

          {!isLoading && !isError && memo && !memo.is_error && <MemoContent memo={memo} />}
        </div>

        <div className="border-t pt-4">
          <Link
            href={`/rankings/${runId}/stock/${ticker}`}
            className="text-sm text-primary hover:underline inline-flex items-center gap-1"
          >
            Vollständiges Factsheet <ExternalLink className="h-3 w-3" />
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 4: Tests grün**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoSheet.test.tsx`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/factsheet/MemoSheet.tsx frontend/components/factsheet/__tests__/MemoSheet.test.tsx
git commit -m "feat(frontend): MemoSheet Slide-In-Wrapper mit State-Machine"
```

---

## Task 9: Frontend — `RankingsTable` Row-Click + Sheet-Integration

**Files:**
- Modify: `frontend/app/rankings/[runId]/rankings-table.tsx`
- Modify: `frontend/app/rankings/__tests__/rankings-table.test.tsx`

- [ ] **Step 1: Failing Test schreiben (zusätzlich zu existierenden Tests)**

Read first: `cat frontend/app/rankings/__tests__/rankings-table.test.tsx | head -50`

Ergänze in `rankings-table.test.tsx` neue Test-Cases:

```tsx
// Imports oben sicherstellen — QueryClient nötig wenn MemoSheet im RankingsTable lebt
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Helper für Tests die den QueryProvider brauchen:
function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('RankingsTable — Memo-Sheet-Integration', () => {
  const items = [
    {
      stock_id: '11111111-1111-1111-1111-111111111111',
      ticker: 'AAPL',
      total_rank: 1,
      weighted_avg: 0.95,
      is_sweet_spot: true,
      per_model_ranks: {},
    },
  ];

  it('opens memo sheet on row click', () => {
    renderWithQuery(<RankingsTable items={items} runId="run-1" />);
    const row = screen.getByText('AAPL').closest('tr');
    expect(row).not.toBeNull();
    fireEvent.click(row!);
    // Sheet öffnet — Ticker erscheint auch im Sheet-Header (zweimal im DOM)
    expect(screen.getAllByText('AAPL').length).toBeGreaterThanOrEqual(2);
  });

  it('ticker link still navigates to factsheet page (stopPropagation)', () => {
    renderWithQuery(<RankingsTable items={items} runId="run-1" />);
    const tickerLink = screen.getByRole('link', { name: 'AAPL' });
    expect(tickerLink.getAttribute('href')).toContain('/rankings/run-1/stock/AAPL');
  });

  it('row without stock_id (legacy) does not open sheet', () => {
    const legacyItems = [{ ...items[0], stock_id: null }];
    renderWithQuery(<RankingsTable items={legacyItems} runId="run-1" />);
    const row = screen.getByText('AAPL').closest('tr');
    fireEvent.click(row!);
    // Kein Sheet-Header (Ticker erscheint nur einmal im DOM)
    expect(screen.getAllByText('AAPL').length).toBe(1);
  });
});
```

**Hinweis:** Wenn der existing Test bereits ohne QueryProvider rendert, muss er ebenfalls auf `renderWithQuery` umgestellt werden, sobald `RankingsTable` `useStockMemo` indirekt nutzt.

- [ ] **Step 2: Test failt**

Run: `cd frontend && npx vitest run app/rankings/__tests__/rankings-table.test.tsx`
Expected: FAIL — neue Tests, alte könnten auch failen wenn QueryProvider fehlt

- [ ] **Step 3: `rankings-table.tsx` anpassen**

In `frontend/app/rankings/[runId]/rankings-table.tsx`:

**3a.** Imports oben ergänzen:

```tsx
import { useState } from 'react';
import { MemoSheet } from '@/components/factsheet/MemoSheet';
```

**3b.** Im Component-Body (vor dem `return`):

```tsx
const [selectedStock, setSelectedStock] = useState<{ stockId: string; ticker: string } | null>(
  null,
);
```

**3c.** Tabellen-Zeilen erweitern. Aktuelle Zeile ist vermutlich `<TableRow>` mit klickbarem Ticker-`<Link>`. Anpassen:

```tsx
<TableRow
  key={item.ticker}
  onClick={() => {
    if (item.stock_id) {
      setSelectedStock({ stockId: item.stock_id, ticker: item.ticker });
    }
  }}
  className={item.stock_id ? 'cursor-pointer hover:bg-muted/50' : ''}
>
  <TableCell>
    <Link
      href={ROUTES.stockFactsheet(runId, item.ticker)}
      onClick={(e) => e.stopPropagation()}
      className="font-medium text-primary hover:underline"
    >
      {item.ticker}
    </Link>
  </TableCell>
  {/* ... restliche Cells ... */}
</TableRow>
```

**3d.** Am Ende vor schließendem `</>` oder Fragment: `MemoSheet` rendern:

```tsx
<MemoSheet
  stockId={selectedStock?.stockId ?? null}
  runId={runId}
  ticker={selectedStock?.ticker ?? ''}
  open={selectedStock !== null}
  onOpenChange={(o) => {
    if (!o) setSelectedStock(null);
  }}
/>
```

**3e.** `RankingsTable` Props um `runId: string` erweitern, falls noch nicht vorhanden. Aufrufer (`frontend/app/rankings/[runId]/page.tsx`) entsprechend anpassen.

```bash
grep -n "interface.*Props\|<RankingsTable" frontend/app/rankings/[runId]/rankings-table.tsx frontend/app/rankings/[runId]/page.tsx
```

- [ ] **Step 4: Tests grün**

Run: `cd frontend && npx vitest run app/rankings/__tests__/rankings-table.test.tsx`
Expected: alle PASS

- [ ] **Step 5: Lint + TypeCheck + Build**

Run: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add frontend/app/rankings/[runId]/rankings-table.tsx frontend/app/rankings/[runId]/page.tsx frontend/app/rankings/__tests__/rankings-table.test.tsx
git commit -m "feat(frontend): RankingsTable Row-Click öffnet MemoSheet"
```

---

## Task 10: Frontend — `MemoPanel` Stub ersetzen + Factsheet-Page-Integration

**Files:**
- Modify: `frontend/components/factsheet/MemoPanel.tsx` (Stub-Replacement)
- Modify: `frontend/components/factsheet/__tests__/MemoPanel.test.tsx`
- Modify: `frontend/app/rankings/[runId]/stock/[ticker]/factsheet-view.tsx` (Props-Durchreichung)

- [ ] **Step 1: Failing Test schreiben**

`frontend/components/factsheet/__tests__/MemoPanel.test.tsx` komplett ersetzen:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';

import { MemoPanel } from '../MemoPanel';
import * as memosApi from '@/lib/api/memos';
import type { Memo } from '@/lib/api/memos';

const STOCK_ID = 'aaaa1111-bbbb-cccc-dddd-eeeeeeeeeeee';
const RUN_ID = 'rrrr1111-rrrr-rrrr-rrrr-rrrrrrrrrrrr';

const fakeMemo: Memo = {
  id: 'memo-1',
  stock_id: STOCK_ID,
  model_run_id: RUN_ID,
  language: 'de',
  one_liner: 'Hero one-liner.',
  ranking_interpretation: 'Interpretation.',
  sweet_spot: false,
  sweet_spot_explanation: null,
  contradictions: [],
  key_strengths: ['S1'],
  key_risks: ['R1'],
  confidence: 'high',
  model_version: 'claude-sonnet-4-6',
  created_at: '2026-05-28T10:00:00Z',
  is_error: false,
};

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('MemoPanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders MemoContent when memo present', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(fakeMemo);
    wrap(<MemoPanel stockId={STOCK_ID} runId={RUN_ID} />);
    await waitFor(() => expect(screen.getByText(/Hero one-liner/)).toBeDefined());
  });

  it('renders MemoEmpty when no memo', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue(null);
    wrap(<MemoPanel stockId={STOCK_ID} runId={RUN_ID} />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /Memo generieren/ })).toBeDefined(),
    );
  });

  it('renders MemoErrorCard when memo.is_error', async () => {
    vi.spyOn(memosApi, 'getMemo').mockResolvedValue({ ...fakeMemo, is_error: true });
    wrap(<MemoPanel stockId={STOCK_ID} runId={RUN_ID} />);
    await waitFor(() => expect(screen.getByText(/fehlgeschlagen/i)).toBeDefined());
  });
});
```

- [ ] **Step 2: Test failt**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoPanel.test.tsx`
Expected: FAIL

- [ ] **Step 3: `MemoPanel.tsx` komplett ersetzen**

```tsx
'use client';

import { FileText } from 'lucide-react';

import { useStockMemo } from '@/lib/hooks/useStockMemo';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MemoContent } from './MemoContent';
import { MemoEmpty } from './MemoEmpty';
import { MemoErrorCard } from './MemoErrorCard';

interface Props {
  stockId: string;
  runId: string;
}

export function MemoPanel({ stockId, runId }: Props) {
  const { memo, isLoading, isError, error, generate, isGenerating } = useStockMemo(
    stockId,
    runId,
  );

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          Research Memo
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <div className="h-24 rounded-lg bg-muted animate-pulse" />
        )}
        {!isLoading && isError && (
          <p className="text-sm text-destructive" role="alert">
            Memo konnte nicht geladen werden: {error?.message ?? 'Unbekannter Fehler'}
          </p>
        )}
        {!isLoading && !isError && memo === null && (
          <MemoEmpty onGenerate={generate} isGenerating={isGenerating} />
        )}
        {!isLoading && !isError && memo && memo.is_error && (
          <MemoErrorCard memo={memo} onRegenerate={generate} isGenerating={isGenerating} />
        )}
        {!isLoading && !isError && memo && !memo.is_error && <MemoContent memo={memo} />}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: `factsheet-view.tsx` anpassen — stockId + runId an MemoPanel reichen**

In `frontend/app/rankings/[runId]/stock/[ticker]/factsheet-view.tsx` Zeile 99 (`<MemoPanel />`):

```tsx
<MemoPanel stockId={stock.id} runId={runId} />
```

`stock.id` kommt aus `factsheetQuery.data.stock` (siehe Zeile 87: `const { stock, latest_ranking } = factsheetQuery.data!;`). `runId` ist bereits als Prop verfügbar.

- [ ] **Step 5: TypeCheck-Verify, dass `stock.id` existiert**

Run: `cd frontend && grep -n "id" frontend/lib/api/stocks.ts | head -10`
Expected: `stocks.ts` exportiert `Stock` mit `id: string` Feld. Falls nicht: Type-Definition prüfen und Backend-Schema vergleichen.

- [ ] **Step 6: Tests grün**

Run: `cd frontend && npx vitest run components/factsheet/__tests__/MemoPanel.test.tsx`
Expected: 3 PASS

- [ ] **Step 7: Vollständige Test-Suite**

Run: `cd frontend && npm run test`
Expected: alle PASS (Regression-Check)

- [ ] **Step 8: Build + Lint**

Run: `cd frontend && npm run lint && npm run build`
Expected: clean

- [ ] **Step 9: Commit**

```bash
git add frontend/components/factsheet/MemoPanel.tsx frontend/components/factsheet/__tests__/MemoPanel.test.tsx frontend/app/rankings/[runId]/stock/[ticker]/factsheet-view.tsx
git commit -m "feat(frontend): MemoPanel zeigt echten Memo-Inhalt (Stub ersetzt)"
```

---

## Task 11: Manual Verification

**Ziel:** Vor PR-Erstellung manuell verifizieren, dass das Feature in einer echten Demo-Umgebung funktioniert.

- [ ] **Step 1: Backend lokal starten**

```bash
cd backend && uvicorn backend.interfaces.rest.app:app --reload --port 8000
```

- [ ] **Step 2: Frontend lokal starten**

```bash
cd frontend && npm run dev
```
Erwartet: Frontend auf `http://localhost:3000`

- [ ] **Step 3: Neuen Rankings-Run starten (damit `stock_id` im JSONB landet)**

Über UI: `/rankings` → Universe wählen → Run starten → warten bis `completed`.

- [ ] **Step 4: Rankings-Detail-Page öffnen**

`/rankings/{run_id}` öffnen, Top-Stocks sichtbar.

- [ ] **Step 5: Memo-Drilldown testen — Empty-State**

Klick auf eine Tabellen-Zeile (NICHT auf den Ticker-Link). Erwartet:
- Sheet öffnet von rechts
- Header zeigt Ticker
- Empty-State mit "Memo generieren"-Button

- [ ] **Step 6: Memo generieren testen**

Klick auf "Memo generieren". Erwartet:
- Loading-Spinner "Memo wird generiert (5-15s)…"
- Nach ~10s: MemoContent mit Hero, Stärken, Risiken, etc.
- Sweet-Spot-Card erscheint bei Sweet-Spot-Stocks

- [ ] **Step 7: Sheet schließen + erneut öffnen**

Erwartet: Cached Memo wird ohne weiteren API-Call angezeigt (Tanstack staleTime=5min).

- [ ] **Step 8: Ticker-Link testen**

Klick direkt auf den Ticker-Text (nicht Row). Erwartet: Navigation zu `/rankings/{run_id}/stock/{ticker}` — Factsheet-Page öffnet, MemoPanel zeigt dort dasselbe Memo.

- [ ] **Step 9: Factsheet-MemoPanel testen**

Auf der Factsheet-Page: MemoPanel im Layout. Erwartet: derselbe Inhalt wie im Sheet.

- [ ] **Step 10: Mobile Viewport testen**

DevTools → iPhone-Viewport. Sheet sollte full-width sein, Content lesbar, Row-Click weiterhin funktional.

- [ ] **Step 11: Legacy-Run testen (optional, wenn alter Run in DB)**

Alten Run öffnen (vor diesem PR erzeugt). Erwartet:
- Tabellen-Zeilen NICHT klickbar (kein hover-Effekt)
- Ticker-Link funktioniert weiterhin (Page-Navigation)
- Sheet öffnet nicht

- [ ] **Step 12: Pre-Push CI-Mirror**

Run im Repo-Root:
```bash
cd backend && mypy backend/ && ruff check backend/ && ruff format --check backend/ && pytest backend/tests/ -x && cd ..
cd frontend && npm run lint && npx tsc --noEmit && npm run test && npm run build && cd ..
```
Expected: alles grün.

- [ ] **Step 13: PR-Erstellung**

```bash
git push -u origin feat/memo-drilldown
gh pr create --title "feat: Memo-Drilldown — Sheet von Rankings-Tabelle + MemoPanel füllen" --body "$(cat <<'EOF'
## Summary

- **Backend (minimal):** `RankingItem.stock_id: UUID | None` ergänzt + Befüllung im JSONB-Run-Compute
- **Frontend:** Klick auf Rankings-Zeile öffnet Slide-In-Sheet mit strukturiertem Memo (One-Liner, Stärken, Risiken, Widersprüche, Confidence)
- **Frontend:** MemoPanel-Stub auf Factsheet-Page durch echte Anzeige ersetzt (gleiche `MemoContent`-Komponente)
- **Empty-State:** "Memo generieren"-Button → POST /memos/generate, 5-15s Loading, dann Anzeige
- **Backwards-Compat:** Alte Runs ohne `stock_id` im JSONB öffnen kein Sheet, Ticker-Link bleibt funktional

## Spec & Plan

- Spec: [`docs/specs/2026-05-28-memo-drilldown-design.md`](docs/specs/2026-05-28-memo-drilldown-design.md)
- Plan: [`docs/superpowers/plans/2026-05-28-memo-drilldown.md`](docs/superpowers/plans/2026-05-28-memo-drilldown.md)

## Test plan

- [x] Backend Unit + Integration grün (pytest)
- [x] Frontend Unit + Component-Tests grün (vitest)
- [x] mypy + ruff check + ruff format clean
- [x] npm run build + lint + tsc clean
- [x] Manual: neuer Run → Row-Click → Sheet → Generate → Memo erscheint
- [x] Manual: Factsheet-Page zeigt dasselbe Memo
- [x] Manual: alter Run → Row nicht klickbar, Ticker-Link funktioniert

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 14: AI-USAGE.md Eintrag (Capstone-40%-Achse)**

Nach erfolgreichem PR-Erstellen einen Eintrag in `docs/AI-USAGE.md` oben einfügen mit:
- Agent (Claude Code Opus 4.7)
- Scope (Spec → Plan → 10 Tasks → Demo)
- Was gut lief / nicht klappte
- Lektion

Separater Commit auf demselben Branch (vor Merge).

---

## Spec-Coverage-Check

| Spec-Anforderung | Task |
|---|---|
| `RankingItem.stock_id` Schema | Task 1 |
| `stock_id` in JSONB-Befüllung | Task 2 |
| Backwards-Compat `stock_id` Optional | Task 1 + Task 9 (`if item.stock_id`) |
| `Memo`-Type voll | Task 4 |
| `getMemo` mit 404→null | Task 4 |
| `useStockMemo` Hook | Task 5 |
| `MemoContent` Komponente (Hero/Sweet-Spot/Strengths/Risks/Contradictions/Interpretation/Meta) | Task 6 |
| `MemoEmpty` + Generate-Button | Task 7 |
| `MemoErrorCard` für `is_error=true` | Task 7 |
| `MemoSheet` Wrapper + State-Machine | Task 8 |
| `RankingsTable` Row-Click | Task 9 |
| Ticker-Link bleibt (stopPropagation) | Task 9 |
| `MemoPanel` Stub ersetzen | Task 10 |
| `factsheet-view.tsx` stockId weiterreichen | Task 10 |
| Sprache hardcoded DE | Task 4 (`generateMemo` default), Task 5 (`useStockMemo` ruft mit `'de'`) |
| Sweet-Spot-Pink | Task 6 (`border-pink-500/40 bg-pink-50/40`) |
| Confidence-Badge | Task 6 |
| Manual Test mit echtem Memo | Task 11 |
