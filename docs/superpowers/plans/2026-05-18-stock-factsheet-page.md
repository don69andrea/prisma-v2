# Stock-Factsheet Page (Issue #48) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement route `/rankings/[runId]/stock/[ticker]` with a Recharts 1Y-price chart, 5-model rank cards, stock header with Sweet-Spot badge, a memo panel placeholder, and a new `GET /api/v1/stocks/{ticker}/prices?days=252` backend endpoint.

**Architecture:** A new backend endpoint retrieves deterministic stub prices via the existing `MarketDataProvider` port → `StubMarketDataProvider`. The frontend page calls both `factsheet` and `prices` endpoints in parallel via React Query, feeding data to four focused components. The rankings table gets clickable rows linking to the new page.

**Tech Stack:** Python/FastAPI (backend), Next.js 14 App Router, React Query v5, Recharts 2.12, Vitest + @testing-library/react (frontend tests), pytest (backend tests), shadcn/ui (Card, Badge, Table), lucide-react.

---

## File Map

| File | Action |
|---|---|
| `backend/application/services/stock_service.py` | Add `MarketDataProvider` to constructor; move `StockNotFound` here; add `get_price_series()` |
| `backend/application/services/factsheet_service.py` | Import `StockNotFound` from `stock_service` instead of defining it |
| `backend/interfaces/rest/schemas/stock.py` | Add `PricePoint` + `PriceSeriesResponse` |
| `backend/interfaces/rest/routers/stocks.py` | Add `GET /stocks/{ticker}/prices` endpoint |
| `backend/interfaces/rest/dependencies.py` | Update `get_stock_service()` to inject `MarketDataProvider` |
| `backend/tests/integration/test_price_endpoint.py` | NEW: 4 integration tests |
| `frontend/lib/api/stocks.ts` | NEW: types + `getFactsheet()` + `getPrices()` |
| `frontend/lib/routes.ts` | Add `factsheet(runId, ticker)` helper |
| `frontend/app/rankings/[runId]/rankings-table.tsx` | Make rows clickable → factsheet link |
| `frontend/components/factsheet/StockHeader.tsx` | NEW: ticker, name, sector, sweet-spot badge |
| `frontend/components/factsheet/ModelRankCards.tsx` | NEW: 5 model rank cards with quartile colour |
| `frontend/components/factsheet/PriceChart.tsx` | NEW: Recharts LineChart 1Y |
| `frontend/components/factsheet/MemoPanel.tsx` | NEW: placeholder slot for Layer-1 memos |
| `frontend/app/rankings/[runId]/stock/[ticker]/page.tsx` | NEW: server metadata + client factsheet view |
| `frontend/components/factsheet/__tests__/StockHeader.test.tsx` | NEW: Vitest component tests |
| `frontend/components/factsheet/__tests__/ModelRankCards.test.tsx` | NEW: Vitest component tests |
| `frontend/components/factsheet/__tests__/MemoPanel.test.tsx` | NEW: Vitest component tests |

---

## Task 1 — Move `StockNotFound` to `StockService` + add `get_price_series`

**Files:**
- Modify: `backend/application/services/stock_service.py`
- Modify: `backend/application/services/factsheet_service.py`

### Background

`StockNotFound` is currently defined in `factsheet_service.py`. We need it in `stock_service.py` too (to raise it from `get_price_series`). Moving it to `stock_service.py` is semantically correct and avoids circular imports.

`StockService` currently only takes a `StockRepository`. We add `MarketDataProvider` as second constructor argument and a `get_price_series` method.

- [ ] **Step 1: Rewrite `backend/application/services/stock_service.py`**

```python
"""StockService — Use-Case-Orchestrierung für Stock-Abfragen."""

from backend.domain.entities.stock import Stock
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.stock_repository import StockRepository

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 50


class StockNotFound(Exception):
    def __init__(self, ticker: str) -> None:
        super().__init__(f"Stock '{ticker.upper()}' not found")
        self.ticker = ticker


class StockService:
    """Kapselt die Geschäftslogik rund um Stock-Abfragen."""

    def __init__(
        self,
        repository: StockRepository,
        market_data_provider: MarketDataProvider,
    ) -> None:
        self._repository = repository
        self._market_data_provider = market_data_provider

    async def list_stocks(
        self,
        limit: int = _DEFAULT_LIMIT,
        offset: int = 0,
    ) -> list[Stock]:
        """Gibt eine paginierte Stock-Liste zurück.

        Raises:
            ValueError: Wenn limit oder offset ausserhalb des erlaubten Bereichs.
        """
        if limit < 1 or limit > _MAX_LIMIT:
            raise ValueError(f"limit muss zwischen 1 und {_MAX_LIMIT} liegen, erhalten: {limit}")
        if offset < 0:
            raise ValueError(f"offset muss >= 0 sein, erhalten: {offset}")

        return await self._repository.list(limit=limit, offset=offset)

    async def get_price_series(
        self,
        ticker: str,
        days: int = 252,
    ) -> tuple[str, list[dict[str, object]]]:
        """Gibt Preiszeitreihe für einen Ticker zurück (letzte `days` Handelstage).

        Args:
            ticker: Ticker-Symbol (case-insensitive).
            days:   Anzahl Handelstage, 1–504. Default 252 (≈1 Jahr).

        Returns:
            Tuple (normalisierter_ticker, liste_von_{date, close}-dicts).

        Raises:
            StockNotFound: Wenn kein Stock mit diesem Ticker existiert.
        """
        ticker_upper = ticker.upper()
        stock = await self._repository.get_by_ticker(ticker_upper)
        if stock is None:
            raise StockNotFound(ticker_upper)

        df = await self._market_data_provider.get_prices([ticker_upper])
        series = df[ticker_upper].tail(days)
        prices = [
            {"date": idx.date().isoformat(), "close": round(float(val), 4)}
            for idx, val in series.items()
        ]
        return ticker_upper, prices
```

- [ ] **Step 2: Update `backend/application/services/factsheet_service.py` to import `StockNotFound` from `stock_service`**

```python
"""FactsheetService — kombiniert Stock-Stammdaten mit neuestem Ranking-Snapshot."""

from typing import Any

from backend.domain.entities.stock import Stock
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.stock_repository import StockRepository
from backend.application.services.stock_service import StockNotFound  # moved here


class FactsheetService:
    def __init__(
        self,
        stock_repo: StockRepository,
        run_repo: RankingRunRepository,
    ) -> None:
        self._stock_repo = stock_repo
        self._run_repo = run_repo

    async def get_factsheet(self, ticker: str) -> tuple[Stock, dict[str, Any] | None]:
        """Gibt Stock-Entity und neuesten Ranking-Snapshot zurück.

        Raises:
            StockNotFound: Wenn kein Stock mit diesem Ticker existiert.
        """
        stock = await self._stock_repo.get_by_ticker(ticker)
        if stock is None:
            raise StockNotFound(ticker)
        raw = await self._run_repo.get_latest_ticker_result(ticker)
        return stock, raw
```

---

## Task 2 — Add `PricePoint` + `PriceSeriesResponse` schemas

**Files:**
- Modify: `backend/interfaces/rest/schemas/stock.py`

- [ ] **Step 1: Append two schemas to the end of the file**

```python
class PricePoint(BaseModel):
    """Ein Datenpunkt in einer Preiszeitreihe."""

    date: str    # ISO-8601, z.B. "2025-05-18"
    close: float


class PriceSeriesResponse(BaseModel):
    """Preiszeitreihe für einen einzelnen Ticker."""

    ticker: str
    prices: list[PricePoint]
```

Full file after edit:

```python
"""Pydantic-Schemas für den REST-Layer (Request/Response DTOs)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StockRead(BaseModel):
    """Serialisierungsschema für eine einzelne Stock-Entität in API-Responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    name: str
    isin: str | None
    sector: str | None
    country: str | None
    currency: str


class StockListResponse(BaseModel):
    """Wrapper für paginierte Stock-Listen mit Gesamtanzahl."""

    items: list[StockRead]
    total: int


class LatestRankingSnapshot(BaseModel):
    """Ranking-Ergebnis eines Tickers aus dem neuesten abgeschlossenen Run."""

    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool
    per_model_ranks: dict[str, int | None]


class StockFactsheet(BaseModel):
    """Kombiniertes Factsheet: Stock-Stammdaten + neueste Ranking-Momentaufnahme."""

    stock: StockRead
    latest_ranking: LatestRankingSnapshot | None


class PricePoint(BaseModel):
    """Ein Datenpunkt in einer Preiszeitreihe."""

    date: str    # ISO-8601, z.B. "2025-05-18"
    close: float


class PriceSeriesResponse(BaseModel):
    """Preiszeitreihe für einen einzelnen Ticker."""

    ticker: str
    prices: list[PricePoint]
```

---

## Task 3 — Write failing integration tests for the price endpoint

**Files:**
- Create: `backend/tests/integration/test_price_endpoint.py`

- [ ] **Step 1: Create the test file**

```python
"""Integrationstests für GET /api/v1/stocks/{ticker}/prices."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.application.services.stock_service import StockNotFound, StockService
from backend.domain.entities.stock import Stock
from backend.domain.repositories.stock_repository import StockRepository
from backend.infrastructure.providers.stub_market_data import StubMarketDataProvider
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import get_stock_service

pytestmark = pytest.mark.integration

_AAPL_ID = uuid.uuid4()
_AAPL = Stock(
    id=_AAPL_ID,
    ticker="AAPL",
    name="Apple Inc.",
    isin="US0378331005",
    sector="Technology",
    country="US",
    currency="USD",
)


class _FakeStockRepo(StockRepository):
    def __init__(self, stocks: list[Stock]) -> None:
        self._by_ticker = {s.ticker: s for s in stocks}
        self._by_id = {s.id: s for s in stocks}

    async def get_by_ticker(self, ticker: str) -> Stock | None:
        return self._by_ticker.get(ticker.upper())

    async def get(self, stock_id: UUID) -> Stock | None:
        return self._by_id.get(stock_id)

    async def list_by_ids(self, stock_ids: list[UUID]) -> list[Stock]:
        return [self._by_id[i] for i in stock_ids if i in self._by_id]

    async def list_by_tickers(self, tickers: list[str]) -> list[Stock]:
        return [self._by_ticker[t.upper()] for t in tickers if t.upper() in self._by_ticker]

    async def list(self, limit: int, offset: int) -> list[Stock]:
        return sorted(self._by_ticker.values(), key=lambda s: s.ticker)[offset : offset + limit]


def _make_app(stocks: list[Stock]) -> Any:
    app = create_app()
    stock_repo = _FakeStockRepo(stocks)
    provider = StubMarketDataProvider()
    app.dependency_overrides[get_stock_service] = lambda: StockService(
        repository=stock_repo,
        market_data_provider=provider,
    )
    return app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app = _make_app([_AAPL])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def test_prices_known_ticker_returns_200(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/AAPL/prices")
    assert response.status_code == 200


async def test_prices_default_returns_252_points(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/stocks/AAPL/prices")).json()
    assert body["ticker"] == "AAPL"
    assert len(body["prices"]) == 252
    assert "date" in body["prices"][0]
    assert "close" in body["prices"][0]


async def test_prices_unknown_ticker_returns_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/UNKNOWN/prices")
    assert response.status_code == 404


async def test_prices_days_param_out_of_range_returns_422(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/AAPL/prices?days=999")
    assert response.status_code == 422


async def test_prices_custom_days_returns_correct_length(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/stocks/AAPL/prices?days=10")).json()
    assert len(body["prices"]) == 10


async def test_prices_ticker_case_insensitive(client: AsyncClient) -> None:
    response = await client.get("/api/v1/stocks/aapl/prices")
    assert response.status_code == 200
    assert response.json()["ticker"] == "AAPL"
```

- [ ] **Step 2: Run tests — verify they FAIL**

```
cd backend && pytest tests/integration/test_price_endpoint.py -v -m integration
```

Expected: Multiple failures (endpoint does not exist yet).

---

## Task 4 — Implement the price endpoint + update DI

**Files:**
- Modify: `backend/interfaces/rest/routers/stocks.py`
- Modify: `backend/interfaces/rest/dependencies.py`

- [ ] **Step 1: Add the price endpoint to `backend/interfaces/rest/routers/stocks.py`**

```python
"""REST-Router für Stock-Endpunkte unter /api/v1/stocks."""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.factsheet_service import FactsheetService
from backend.application.services.stock_service import StockNotFound, StockService
from backend.interfaces.rest.dependencies import get_factsheet_service, get_stock_service
from backend.interfaces.rest.schemas.stock import (
    LatestRankingSnapshot,
    PriceSeriesResponse,
    StockFactsheet,
    StockListResponse,
    StockRead,
)

router = APIRouter(prefix="/api/v1", tags=["stocks"])


@router.get(
    "/stocks",
    response_model=StockListResponse,
    summary="Alle Stocks auflisten",
    description="Gibt eine paginierte Liste aller im System bekannten Stocks zurück.",
)
async def list_stocks(
    limit: int = Query(default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse"),
    offset: int = Query(default=0, ge=0, description="Anzahl zu überspringender Einträge"),
    service: StockService = Depends(get_stock_service),
) -> StockListResponse:
    stocks = await service.list_stocks(limit=limit, offset=offset)
    items = [StockRead.model_validate(stock) for stock in stocks]
    return StockListResponse(items=items, total=len(items))


@router.get(
    "/stocks/{ticker}/factsheet",
    response_model=StockFactsheet,
    summary="Stock-Factsheet abrufen",
    description="Gibt Stammdaten und neueste Ranking-Momentaufnahme für einen Ticker zurück.",
)
async def get_factsheet(
    ticker: str,
    service: FactsheetService = Depends(get_factsheet_service),
) -> StockFactsheet:
    try:
        stock, raw = await service.get_factsheet(ticker)
    except Exception as exc:
        from backend.application.services.stock_service import StockNotFound as _SNF
        if isinstance(exc, _SNF):
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise
    snapshot = LatestRankingSnapshot.model_validate(raw) if raw is not None else None
    return StockFactsheet(stock=StockRead.model_validate(stock), latest_ranking=snapshot)


@router.get(
    "/stocks/{ticker}/prices",
    response_model=PriceSeriesResponse,
    summary="Preiszeitreihe abrufen",
    description="Gibt die letzten `days` Handelstage als Preiszeitreihe zurück (Stub-Daten).",
)
async def get_prices(
    ticker: str,
    days: int = Query(default=252, ge=1, le=504, description="Anzahl Handelstage, 1–504"),
    service: StockService = Depends(get_stock_service),
) -> PriceSeriesResponse:
    try:
        ticker_upper, prices = await service.get_price_series(ticker, days)
    except StockNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from backend.interfaces.rest.schemas.stock import PricePoint
    return PriceSeriesResponse(
        ticker=ticker_upper,
        prices=[PricePoint(date=p["date"], close=p["close"]) for p in prices],
    )
```

**Note on `get_factsheet` router:** `StockNotFound` was previously imported from `factsheet_service`. Now it lives in `stock_service`. The factsheet router already catches it via the `FactsheetService` — update the import. Simplest fix: import once at top:

Final clean version of the router (replace the whole file):

```python
"""REST-Router für Stock-Endpunkte unter /api/v1/stocks."""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.factsheet_service import FactsheetService
from backend.application.services.stock_service import StockNotFound, StockService
from backend.interfaces.rest.dependencies import get_factsheet_service, get_stock_service
from backend.interfaces.rest.schemas.stock import (
    LatestRankingSnapshot,
    PricePoint,
    PriceSeriesResponse,
    StockFactsheet,
    StockListResponse,
    StockRead,
)

router = APIRouter(prefix="/api/v1", tags=["stocks"])


@router.get(
    "/stocks",
    response_model=StockListResponse,
    summary="Alle Stocks auflisten",
    description="Gibt eine paginierte Liste aller im System bekannten Stocks zurück.",
)
async def list_stocks(
    limit: int = Query(default=50, ge=1, le=200, description="Maximale Anzahl Ergebnisse"),
    offset: int = Query(default=0, ge=0, description="Anzahl zu überspringender Einträge"),
    service: StockService = Depends(get_stock_service),
) -> StockListResponse:
    stocks = await service.list_stocks(limit=limit, offset=offset)
    items = [StockRead.model_validate(stock) for stock in stocks]
    return StockListResponse(items=items, total=len(items))


@router.get(
    "/stocks/{ticker}/factsheet",
    response_model=StockFactsheet,
    summary="Stock-Factsheet abrufen",
    description="Gibt Stammdaten und neueste Ranking-Momentaufnahme für einen Ticker zurück.",
)
async def get_factsheet(
    ticker: str,
    service: FactsheetService = Depends(get_factsheet_service),
) -> StockFactsheet:
    try:
        stock, raw = await service.get_factsheet(ticker)
    except StockNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    snapshot = LatestRankingSnapshot.model_validate(raw) if raw is not None else None
    return StockFactsheet(stock=StockRead.model_validate(stock), latest_ranking=snapshot)


@router.get(
    "/stocks/{ticker}/prices",
    response_model=PriceSeriesResponse,
    summary="Preiszeitreihe abrufen",
    description="Gibt die letzten `days` Handelstage als Preiszeitreihe zurück (Stub-Daten).",
)
async def get_prices(
    ticker: str,
    days: int = Query(default=252, ge=1, le=504, description="Anzahl Handelstage, 1–504"),
    service: StockService = Depends(get_stock_service),
) -> PriceSeriesResponse:
    try:
        ticker_upper, prices = await service.get_price_series(ticker, days)
    except StockNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PriceSeriesResponse(
        ticker=ticker_upper,
        prices=[PricePoint(date=p["date"], close=p["close"]) for p in prices],
    )
```

- [ ] **Step 2: Update `get_stock_service` in `backend/interfaces/rest/dependencies.py`**

Find the existing function (lines 62–66) and replace it:

```python
async def get_stock_service(
    repository: StockRepository = Depends(get_stock_repository),
    market_data_provider: MarketDataProvider = Depends(get_market_data_provider),
) -> StockService:
    """Erstellt einen StockService mit dem injizierten Repository und MarketDataProvider."""
    return StockService(repository=repository, market_data_provider=market_data_provider)
```

- [ ] **Step 3: Run tests — verify they PASS**

```
cd backend && pytest tests/integration/test_price_endpoint.py -v -m integration
```

Expected: All 6 tests PASS.

- [ ] **Step 4: Run the existing factsheet tests — verify no regression**

```
cd backend && pytest tests/integration/test_factsheet_endpoint.py -v -m integration
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/application/services/stock_service.py \
        backend/application/services/factsheet_service.py \
        backend/interfaces/rest/schemas/stock.py \
        backend/interfaces/rest/routers/stocks.py \
        backend/interfaces/rest/dependencies.py \
        backend/tests/integration/test_price_endpoint.py
git commit -m "feat(rest): GET /api/v1/stocks/{ticker}/prices endpoint (closes #48 backend)"
```

---

## Task 5 — Frontend API client + types + routes

**Files:**
- Create: `frontend/lib/api/stocks.ts`
- Modify: `frontend/lib/routes.ts`

- [ ] **Step 1: Create `frontend/lib/api/stocks.ts`**

```typescript
import { apiFetch } from './client';

// ---- Types ----------------------------------------------------------------

export interface StockRead {
  id: string;
  ticker: string;
  name: string;
  isin: string | null;
  sector: string | null;
  country: string | null;
  currency: string;
}

export interface LatestRankingSnapshot {
  total_rank: number | null;
  weighted_avg: number | null;
  is_sweet_spot: boolean;
  per_model_ranks: Record<string, number | null>;
}

export interface StockFactsheet {
  stock: StockRead;
  latest_ranking: LatestRankingSnapshot | null;
}

export interface PricePoint {
  date: string;   // ISO-8601, e.g. "2025-05-18"
  close: number;
}

export interface PriceSeriesResponse {
  ticker: string;
  prices: PricePoint[];
}

// ---- API functions --------------------------------------------------------

export function getFactsheet(ticker: string): Promise<StockFactsheet> {
  return apiFetch<StockFactsheet>(`/api/v1/stocks/${ticker}/factsheet`);
}

export function getPrices(ticker: string, days = 252): Promise<PriceSeriesResponse> {
  return apiFetch<PriceSeriesResponse>(`/api/v1/stocks/${ticker}/prices?days=${days}`);
}
```

- [ ] **Step 2: Update `frontend/lib/routes.ts`**

```typescript
export const ROUTES = {
  dashboard: '/',
  universes: '/universes',
  rankings: '/rankings',
  factsheet: (runId: string, ticker: string) =>
    `/rankings/${runId}/stock/${ticker}` as const,
} as const;

export type Route = (typeof ROUTES)[keyof typeof ROUTES];
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/stocks.ts frontend/lib/routes.ts
git commit -m "feat(frontend): API client + routes for stock factsheet"
```

---

## Task 6 — Make rankings table rows clickable

**Files:**
- Modify: `frontend/app/rankings/[runId]/rankings-table.tsx`

The table currently renders rows without links. Each row should link to the factsheet page.

- [ ] **Step 1: Update `frontend/app/rankings/[runId]/rankings-table.tsx`**

```typescript
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ROUTES } from '@/lib/routes';
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

export function RankingsTable({
  items,
  runId,
}: {
  items: RankingItem[];
  runId: string;
}) {
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
          <TableRow
            key={item.ticker}
            className="cursor-pointer hover:bg-muted/50"
          >
            <TableCell>
              <Link
                href={ROUTES.factsheet(runId, item.ticker)}
                className="block w-full"
              >
                {formatNumber(item.total_rank)}
              </Link>
            </TableCell>
            <TableCell>
              <Link
                href={ROUTES.factsheet(runId, item.ticker)}
                className="block w-full font-mono"
              >
                {item.ticker}
              </Link>
            </TableCell>
            <TableCell>{formatNumber(item.weighted_avg, 2)}</TableCell>
            <TableCell>
              {item.is_sweet_spot ? <Badge variant="default">★</Badge> : null}
            </TableCell>
            {MODEL_COLUMNS.map((col) => (
              <TableCell key={col.key}>
                {formatNumber(item.per_model_ranks[col.key] ?? null)}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Update the parent page to pass `runId` to `RankingsTable`**

In `frontend/app/rankings/[runId]/page.tsx`, find the line:

```tsx
{isCompleted && rankingsQuery.data && <RankingsTable items={rankingsQuery.data} />}
```

Replace with:

```tsx
{isCompleted && rankingsQuery.data && (
  <RankingsTable items={rankingsQuery.data} runId={params.runId} />
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/rankings/[runId]/rankings-table.tsx \
        frontend/app/rankings/[runId]/page.tsx
git commit -m "feat(frontend): make ranking table rows link to factsheet"
```

---

## Task 7 — `StockHeader` component

**Files:**
- Create: `frontend/components/factsheet/StockHeader.tsx`
- Create: `frontend/components/factsheet/__tests__/StockHeader.test.tsx`

- [ ] **Step 1: Create `frontend/components/factsheet/__tests__/StockHeader.test.tsx`**

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { StockHeader } from '../StockHeader';
import type { StockRead, LatestRankingSnapshot } from '@/lib/api/stocks';

const stock: StockRead = {
  id: 'abc-123',
  ticker: 'AAPL',
  name: 'Apple Inc.',
  isin: 'US0378331005',
  sector: 'Technology',
  country: 'US',
  currency: 'USD',
};

const ranking: LatestRankingSnapshot = {
  total_rank: 1,
  weighted_avg: 0.85,
  is_sweet_spot: true,
  per_model_ranks: {},
};

describe('StockHeader', () => {
  it('renders ticker and name', () => {
    render(<StockHeader stock={stock} ranking={null} />);
    expect(screen.getByText('AAPL')).toBeDefined();
    expect(screen.getByText('Apple Inc.')).toBeDefined();
  });

  it('shows Sweet-Spot badge when is_sweet_spot is true', () => {
    render(<StockHeader stock={stock} ranking={ranking} />);
    expect(screen.getByText('Sweet Spot')).toBeDefined();
  });

  it('does not show Sweet-Spot badge when ranking is null', () => {
    render(<StockHeader stock={stock} ranking={null} />);
    expect(screen.queryByText('Sweet Spot')).toBeNull();
  });

  it('shows total rank when ranking is available', () => {
    render(<StockHeader stock={stock} ranking={ranking} />);
    expect(screen.getByText('#1')).toBeDefined();
  });

  it('shows sector and country', () => {
    render(<StockHeader stock={stock} ranking={null} />);
    expect(screen.getByText('Technology')).toBeDefined();
    expect(screen.getByText('US')).toBeDefined();
  });
});
```

- [ ] **Step 2: Run tests — verify they FAIL**

```
cd frontend && npm test -- StockHeader
```

Expected: FAIL (component not found).

- [ ] **Step 3: Create `frontend/components/factsheet/StockHeader.tsx`**

```typescript
import { Star } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import type { LatestRankingSnapshot, StockRead } from '@/lib/api/stocks';

interface Props {
  stock: StockRead;
  ranking: LatestRankingSnapshot | null;
}

export function StockHeader({ stock, ranking }: Props) {
  return (
    <Card>
      <CardContent className="py-5">
        <div className="flex items-start justify-between gap-4">
          {/* Left: ticker + name + meta */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-base px-2 py-0.5">
                {stock.ticker}
              </Badge>
              {ranking?.is_sweet_spot && (
                <Badge variant="default" className="flex items-center gap-1">
                  <Star className="h-3 w-3" />
                  Sweet Spot
                </Badge>
              )}
            </div>
            <h1 className="text-2xl font-bold tracking-tight">{stock.name}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {stock.sector && <span>{stock.sector}</span>}
              {stock.sector && stock.country && <span>·</span>}
              {stock.country && <span>{stock.country}</span>}
              {stock.currency && (
                <>
                  <span>·</span>
                  <span>{stock.currency}</span>
                </>
              )}
            </div>
          </div>

          {/* Right: total rank */}
          {ranking?.total_rank != null && (
            <div className="text-right">
              <div className="text-4xl font-bold tabular-nums">
                #{ranking.total_rank}
              </div>
              <div className="text-xs text-muted-foreground">Gesamtrang</div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run tests — verify they PASS**

```
cd frontend && npm test -- StockHeader
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/factsheet/StockHeader.tsx \
        frontend/components/factsheet/__tests__/StockHeader.test.tsx
git commit -m "feat(frontend): StockHeader component with Sweet-Spot badge"
```

---

## Task 8 — `ModelRankCards` component

**Files:**
- Create: `frontend/components/factsheet/ModelRankCards.tsx`
- Create: `frontend/components/factsheet/__tests__/ModelRankCards.test.tsx`

**Quartile logic:** With 20 stocks (MVP assumption), quartile = `Math.ceil((rank / 20) * 4)`. Q1 (top 25%) = green, Q2 = yellow-green, Q3 = orange, Q4 = red.

- [ ] **Step 1: Create `frontend/components/factsheet/__tests__/ModelRankCards.test.tsx`**

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ModelRankCards } from '../ModelRankCards';

const perModelRanks: Record<string, number | null> = {
  quality_classic: 1,
  alpha: 18,
  trend_momentum: 5,
  value_alpha_potential: null,
  diversification: 10,
};

describe('ModelRankCards', () => {
  it('renders all 5 model cards', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByText('Quality Classic')).toBeDefined();
    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText('Trend Momentum')).toBeDefined();
    expect(screen.getByText('Value Alpha Potential')).toBeDefined();
    expect(screen.getByText('Diversification')).toBeDefined();
  });

  it('shows rank number when available', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByText('1')).toBeDefined();
    expect(screen.getByText('18')).toBeDefined();
  });

  it('shows dash for null rank', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByText('—')).toBeDefined();
  });
});
```

- [ ] **Step 2: Run tests — verify they FAIL**

```
cd frontend && npm test -- ModelRankCards
```

Expected: FAIL.

- [ ] **Step 3: Create `frontend/components/factsheet/ModelRankCards.tsx`**

```typescript
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface Props {
  perModelRanks: Record<string, number | null>;
}

const MODELS: Array<{ key: string; label: string }> = [
  { key: 'quality_classic', label: 'Quality Classic' },
  { key: 'alpha', label: 'Alpha' },
  { key: 'trend_momentum', label: 'Trend Momentum' },
  { key: 'value_alpha_potential', label: 'Value Alpha Potential' },
  { key: 'diversification', label: 'Diversification' },
];

const TOTAL_STOCKS = 20; // MVP: assume universe of 20 stocks

function getQuartile(rank: number): 1 | 2 | 3 | 4 {
  const q = Math.ceil((rank / TOTAL_STOCKS) * 4);
  return Math.min(Math.max(q, 1), 4) as 1 | 2 | 3 | 4;
}

const QUARTILE_CLASSES: Record<1 | 2 | 3 | 4, string> = {
  1: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  2: 'bg-lime-100 text-lime-800 border-lime-200',
  3: 'bg-orange-100 text-orange-800 border-orange-200',
  4: 'bg-red-100 text-red-800 border-red-200',
};

const QUARTILE_LABELS: Record<1 | 2 | 3 | 4, string> = {
  1: 'Q1',
  2: 'Q2',
  3: 'Q3',
  4: 'Q4',
};

export function ModelRankCards({ perModelRanks }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {MODELS.map(({ key, label }) => {
        const rank = perModelRanks[key] ?? null;
        const quartile = rank !== null ? getQuartile(rank) : null;

        return (
          <Card key={key}>
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground leading-tight">
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              <div className="flex items-end justify-between gap-2">
                <span className="text-3xl font-bold tabular-nums">
                  {rank !== null ? rank : '—'}
                </span>
                {quartile !== null && (
                  <span
                    className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${QUARTILE_CLASSES[quartile]}`}
                  >
                    {QUARTILE_LABELS[quartile]}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run tests — verify they PASS**

```
cd frontend && npm test -- ModelRankCards
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/factsheet/ModelRankCards.tsx \
        frontend/components/factsheet/__tests__/ModelRankCards.test.tsx
git commit -m "feat(frontend): ModelRankCards with quartile colour badges"
```

---

## Task 9 — `PriceChart` component

**Files:**
- Create: `frontend/components/factsheet/PriceChart.tsx`

Note: Recharts uses canvas/SVG rendering which does not work in jsdom. We skip Vitest for this component (standard practice) and rely on visual verification.

- [ ] **Step 1: Create `frontend/components/factsheet/PriceChart.tsx`**

```typescript
'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { PricePoint } from '@/lib/api/stocks';

interface Props {
  ticker: string;
  prices: PricePoint[];
}

function formatDateShort(dateStr: string): string {
  // "2025-05-18" → "Mai 25"
  const d = new Date(dateStr);
  return d.toLocaleDateString('de-CH', { month: 'short', year: '2-digit' });
}

function formatPrice(value: number): string {
  return value.toFixed(2);
}

// Show only ~6 evenly-spaced tick labels to avoid crowding
function buildTickFormatter(prices: PricePoint[]) {
  const step = Math.max(1, Math.floor(prices.length / 6));
  const tickSet = new Set(prices.filter((_, i) => i % step === 0).map((p) => p.date));
  return (date: string) => (tickSet.has(date) ? formatDateShort(date) : '');
}

export function PriceChart({ ticker, prices }: Props) {
  if (prices.length === 0) return null;

  const tickFormatter = buildTickFormatter(prices);
  const minClose = Math.min(...prices.map((p) => p.close));
  const maxClose = Math.max(...prices.map((p) => p.close));
  const padding = (maxClose - minClose) * 0.05;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">
          Kursentwicklung — {ticker} (1 Jahr)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={prices} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="date"
              tickFormatter={tickFormatter}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              domain={[minClose - padding, maxClose + padding]}
              tickFormatter={formatPrice}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              formatter={(value: number) => [formatPrice(value), 'Kurs']}
              labelFormatter={(label: string) =>
                new Date(label).toLocaleDateString('de-CH', {
                  day: '2-digit',
                  month: 'short',
                  year: 'numeric',
                })
              }
            />
            <Line
              type="monotone"
              dataKey="close"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/factsheet/PriceChart.tsx
git commit -m "feat(frontend): PriceChart component using Recharts"
```

---

## Task 10 — `MemoPanel` component

**Files:**
- Create: `frontend/components/factsheet/MemoPanel.tsx`
- Create: `frontend/components/factsheet/__tests__/MemoPanel.test.tsx`

- [ ] **Step 1: Create `frontend/components/factsheet/__tests__/MemoPanel.test.tsx`**

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { MemoPanel } from '../MemoPanel';

describe('MemoPanel', () => {
  it('renders placeholder text', () => {
    render(<MemoPanel />);
    expect(screen.getByText(/KI-Memo/)).toBeDefined();
  });

  it('renders placeholder heading', () => {
    render(<MemoPanel />);
    expect(screen.getByText('Research Memo')).toBeDefined();
  });
});
```

- [ ] **Step 2: Run tests — verify they FAIL**

```
cd frontend && npm test -- MemoPanel
```

Expected: FAIL.

- [ ] **Step 3: Create `frontend/components/factsheet/MemoPanel.tsx`**

```typescript
import { FileText } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function MemoPanel() {
  return (
    <Card className="border-dashed bg-muted/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          Research Memo
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center justify-center py-8 gap-2 text-center text-muted-foreground">
          <FileText className="h-8 w-8 opacity-30" />
          <p className="text-sm">
            KI-Memo noch nicht verfügbar — Layer-1-Integration folgt.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Run tests — verify they PASS**

```
cd frontend && npm test -- MemoPanel
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/factsheet/MemoPanel.tsx \
        frontend/components/factsheet/__tests__/MemoPanel.test.tsx
git commit -m "feat(frontend): MemoPanel placeholder slot for Layer-1 AI memos"
```

---

## Task 11 — Factsheet page

**Files:**
- Create: `frontend/app/rankings/[runId]/stock/[ticker]/page.tsx`

- [ ] **Step 1: Create the directory and page file**

```
frontend/app/rankings/[runId]/stock/[ticker]/page.tsx
```

```typescript
import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

import { FactsheetView } from './factsheet-view';

interface PageProps {
  params: { runId: string; ticker: string };
}

export function generateMetadata({ params }: PageProps): Metadata {
  return {
    title: `${params.ticker.toUpperCase()} — PRISMA Factsheet`,
  };
}

export default function FactsheetPage({ params }: PageProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <Link
          href={`/rankings/${params.runId}`}
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Zurück zum Ranking
        </Link>
        <h1 className="text-2xl font-bold tracking-tight sr-only">
          {params.ticker.toUpperCase()} Factsheet
        </h1>
      </div>

      <FactsheetView runId={params.runId} ticker={params.ticker.toUpperCase()} />
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/app/rankings/[runId]/stock/[ticker]/factsheet-view.tsx`**

```typescript
'use client';

import { useQuery } from '@tanstack/react-query';
import { XCircle } from 'lucide-react';

import { getFactsheet, getPrices } from '@/lib/api/stocks';
import { ApiError } from '@/lib/api/client';
import { Card, CardContent } from '@/components/ui/card';
import { StockHeader } from '@/components/factsheet/StockHeader';
import { ModelRankCards } from '@/components/factsheet/ModelRankCards';
import { PriceChart } from '@/components/factsheet/PriceChart';
import { MemoPanel } from '@/components/factsheet/MemoPanel';

function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`h-32 rounded-lg bg-muted animate-pulse ${className}`} />
  );
}

interface Props {
  runId: string;
  ticker: string;
}

export function FactsheetView({ ticker }: Props) {
  const factsheetQuery = useQuery({
    queryKey: ['factsheet', ticker],
    queryFn: () => getFactsheet(ticker),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) return false;
      return failureCount < 2;
    },
  });

  const pricesQuery = useQuery({
    queryKey: ['prices', ticker],
    queryFn: () => getPrices(ticker),
    staleTime: 5 * 60 * 1000, // prices don't change between sessions
  });

  const is404 =
    factsheetQuery.error instanceof ApiError && factsheetQuery.error.status === 404;

  if (is404) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-lg font-medium">Stock nicht gefunden</p>
          <p className="text-sm text-muted-foreground mt-1">Ticker: {ticker}</p>
        </CardContent>
      </Card>
    );
  }

  if (factsheetQuery.isError) {
    return (
      <div className="flex items-center gap-2 text-destructive text-sm" role="alert">
        <XCircle className="h-4 w-4 shrink-0" />
        <span>
          Factsheet konnte nicht geladen werden:{' '}
          {factsheetQuery.error instanceof Error
            ? factsheetQuery.error.message
            : 'Unbekannter Fehler'}
        </span>
      </div>
    );
  }

  if (factsheetQuery.isLoading) {
    return (
      <div className="space-y-4">
        <SkeletonCard className="h-24" />
        <div className="grid grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <SkeletonCard key={i} className="h-28" />
          ))}
        </div>
        <SkeletonCard className="h-72" />
        <SkeletonCard className="h-32" />
      </div>
    );
  }

  const { stock, latest_ranking } = factsheetQuery.data!;

  return (
    <div className="space-y-4">
      <StockHeader stock={stock} ranking={latest_ranking} />

      {latest_ranking && (
        <ModelRankCards perModelRanks={latest_ranking.per_model_ranks} />
      )}

      {pricesQuery.data && (
        <PriceChart ticker={ticker} prices={pricesQuery.data.prices} />
      )}
      {pricesQuery.isLoading && <SkeletonCard className="h-72" />}

      <MemoPanel />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/rankings/[runId]/stock/
git commit -m "feat(frontend): Stock-Factsheet page (closes #48)"
```

---

## Task 12 — Final verification

- [ ] **Step 1: Run all backend tests**

```
cd backend && pytest --tb=short -q
```

Expected: All existing tests pass. New price endpoint tests pass.

- [ ] **Step 2: Run all frontend tests**

```
cd frontend && npm test
```

Expected: StockHeader (5), ModelRankCards (3), MemoPanel (2) all pass.

- [ ] **Step 3: Build frontend**

```
cd frontend && npm run build
```

Expected: Zero TypeScript errors, build succeeds.

- [ ] **Step 4: Manual smoke test**

Start backend:
```
uvicorn backend.interfaces.rest.app:app --reload
```

Verify endpoints:
```
curl http://localhost:8000/api/v1/stocks/AAPL/prices
# → {"ticker":"AAPL","prices":[{"date":"...","close":...}, ...]} (252 items)

curl http://localhost:8000/api/v1/stocks/INVALID/prices
# → 404

curl "http://localhost:8000/api/v1/stocks/AAPL/prices?days=999"
# → 422
```

Start frontend:
```
cd frontend && npm run dev
```

Navigate to `http://localhost:3000/rankings/some-run-id/stock/AAPL`:
- ✅ StockHeader shows AAPL, Apple Inc., Technology/US
- ✅ 5 ModelRankCards render (may show "—" if no ranking data)
- ✅ PriceChart renders with 252 data points
- ✅ MemoPanel placeholder visible

- [ ] **Step 5: Create PR**

```bash
gh pr create \
  --title "feat(frontend): Stock-Factsheet Page mit Recharts + Memo-Panel (closes #48)" \
  --body "$(cat <<'EOF'
## Summary
- Adds `GET /api/v1/stocks/{ticker}/prices?days=252` backend endpoint (TDD, 6 tests)
- Moves `StockNotFound` to `StockService` (cleaner ownership)
- Adds `StockHeader`, `ModelRankCards`, `PriceChart`, `MemoPanel` components
- Adds route `/rankings/[runId]/stock/[ticker]` with metadata + client view
- Makes rankings table rows clickable → factsheet link

## Test plan
- [ ] `pytest tests/integration/test_price_endpoint.py` — 6 tests pass
- [ ] `pytest tests/integration/test_factsheet_endpoint.py` — no regression
- [ ] `npm test` — all component tests pass
- [ ] `npm run build` — zero TS errors
- [ ] Manual: navigate to factsheet page and verify all sections render

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
