# Run-History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run-Historie auf `/rankings` + Side-by-Side-Vergleich auf `/rankings/compare?a=&b=`, mit Cross-Universe-Support (Schnittmenge + Counts-Banner).

**Architecture:** Backend erweitert `RunResponse` um `universe_name` (joinen via `UniverseRepository`). Frontend bekommt `<RunHistoryList/>` mit Checkbox-FIFO (max 2) und eine neue Page `/rankings/compare` mit `<CompareBanner/>` + `<CompareTable/>`. Pure Diff-Logik liegt in `lib/compare.ts`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, TanStack Query 5, Next.js 14 App-Router, Vitest + React-Testing-Library, Playwright.

**Spec:** `docs/specs/2026-05-29-run-history-design.md`

**Pre-Discovered Context** (verfiziert, nicht erneut explorieren):
- `backend/interfaces/rest/schemas/runs.py:36` — `RunResponse` mit `from_domain(run)`-Classmethod
- `backend/application/services/ranking_run_service.py:116` — `get_run(run_id) -> RankingRun`
- `backend/application/services/ranking_run_service.py:128` — `list_runs(limit, offset) -> list[RankingRun]`
- `backend/interfaces/rest/routers/runs.py` — 3 Stellen bauen `RunResponse.from_domain(...)`: Zeilen 25, 40, 53
- `backend/domain/repositories/universe_repository.py:9` — `UniverseRepository.get(id) -> Universe | None`
- `backend/infrastructure/persistence/repositories/ranking_run_repository.py:52` — `list_all` ordnet `created_at.desc()` ✓
- `backend/tests/integration/test_runs_endpoint.py` — Pattern mit InMemory-Repos, ASGITransport, ApiKey-Header
- `backend/tests/unit/interfaces/test_runs_schema.py` — Pattern für Schema-Unit-Tests
- `frontend/lib/api/runs.ts` — bereits `listRuns`, `getRankings`, `getRun`, `createRun`
- `frontend/app/rankings/page.tsx` — Server-Component, rendert `<RankingsForm/>` in Card
- `frontend/app/rankings/[runId]/page.tsx` — Pattern für `useQuery` + Skeletons + 404-Card
- `frontend/components/ui/` — `badge, button, card, input, popover, skeleton, table` verfügbar (kein StatusBadge — Inline-Badge mit Variant)
- `frontend/app/rankings/__tests__/rankings-form.test.tsx` — Vitest-Pattern mit `vi.mock('@/lib/api/runs')`, `QueryClientProvider`, `mockPush`

---

## File Structure

**Backend (modified):**
- `backend/interfaces/rest/schemas/runs.py` — `RunResponse` bekommt `universe_name`, `from_domain` neue Signatur
- `backend/interfaces/rest/routers/runs.py` — 3 Build-Sites nutzen neue Signatur, Service liefert Universe-Map
- `backend/application/services/ranking_run_service.py` — neue Helper `list_runs_with_universe_name()` und `get_run_with_universe_name()` (oder einfacher: bestehende Methoden bleiben, Router holt Universe-Name nach)

**Backend (new):**
- `backend/tests/unit/interfaces/test_runs_schema_universe_name.py` — Schema-Test für neues Feld
- `backend/tests/integration/test_runs_endpoint_universe_name.py` — Endpoint-Test für `universe_name` in Responses + Fallback

**Frontend (modified):**
- `frontend/lib/api/runs.ts` — `universe_name: string` zu `RunResponse` ergänzen
- `frontend/app/rankings/page.tsx` — `<RunHistoryList/>` einbinden

**Frontend (new):**
- `frontend/lib/compare.ts` — pure Diff-Logik (`buildCompareRows`, `buildCompareStats`)
- `frontend/lib/__tests__/compare.test.ts`
- `frontend/app/rankings/run-history-list.tsx`
- `frontend/app/rankings/__tests__/run-history-list.test.tsx`
- `frontend/app/rankings/compare/page.tsx`
- `frontend/app/rankings/compare/compare-client.tsx`
- `frontend/app/rankings/compare/compare-table.tsx`
- `frontend/app/rankings/compare/compare-banner.tsx`
- `frontend/app/rankings/compare/__tests__/compare-table.test.tsx`
- `frontend/app/rankings/compare/__tests__/compare-banner.test.tsx`
- `frontend/e2e/run-history.spec.ts`

---

## Task 1: Backend — `universe_name` in `RunResponse`

**Files:**
- Modify: `backend/interfaces/rest/schemas/runs.py:36-49`
- Modify: `backend/interfaces/rest/routers/runs.py` (3 Stellen, siehe unten)
- Create: `backend/tests/unit/interfaces/test_runs_schema_universe_name.py`
- Create: `backend/tests/integration/test_runs_endpoint_universe_name.py`

### Step 1.1: Schema-Test schreiben (failing)

- [ ] Erstelle `backend/tests/unit/interfaces/test_runs_schema_universe_name.py`:

```python
"""Schema-Tests für RunResponse.universe_name."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import WeightConfig
from backend.interfaces.rest.schemas.runs import RunResponse

pytestmark = pytest.mark.unit


class TestRunResponseUniverseName:
    def test_from_domain_includes_universe_name(self) -> None:
        run = RankingRun(
            id=uuid4(),
            created_at=datetime.now(tz=UTC),
            universe_id=uuid4(),
            weight_config=WeightConfig.equal(),
            status="completed",
        )

        response = RunResponse.from_domain(run, universe_name="Demo-US-5")

        assert response.universe_name == "Demo-US-5"
        assert response.id == run.id
        assert response.status == "completed"

    def test_from_domain_accepts_deleted_fallback(self) -> None:
        run = RankingRun(
            id=uuid4(),
            created_at=datetime.now(tz=UTC),
            universe_id=uuid4(),
            weight_config=WeightConfig.equal(),
            status="completed",
        )

        response = RunResponse.from_domain(run, universe_name="(deleted)")

        assert response.universe_name == "(deleted)"
```

### Step 1.2: Test laufen lassen → FAIL

- [ ] Run:

```bash
.venv/bin/pytest backend/tests/unit/interfaces/test_runs_schema_universe_name.py -v
```

Expected: FAIL — `TypeError: from_domain() got unexpected keyword argument 'universe_name'` oder `missing field universe_name`.

### Step 1.3: Schema anpassen

- [ ] Ersetze in `backend/interfaces/rest/schemas/runs.py` die `RunResponse`-Klasse (Zeilen 36–49):

```python
class RunResponse(BaseModel):
    id: UUID
    status: RankingRunStatus
    universe_id: UUID
    universe_name: str
    created_at: datetime

    @classmethod
    def from_domain(cls, run: RankingRun, universe_name: str) -> "RunResponse":
        return cls(
            id=run.id,
            status=run.status,
            universe_id=run.universe_id,
            universe_name=universe_name,
            created_at=run.created_at,
        )
```

### Step 1.4: Schema-Test grün

- [ ] Run:

```bash
.venv/bin/pytest backend/tests/unit/interfaces/test_runs_schema_universe_name.py -v
```

Expected: 2 passed.

### Step 1.5: Endpoint-Integration-Test schreiben (failing)

- [ ] Erstelle `backend/tests/integration/test_runs_endpoint_universe_name.py`:

```python
"""Integrationstests: universe_name in RunResponse aus Endpoints."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.domain.entities.ranking_run import RankingRun
from backend.domain.entities.universe import Universe, WeightConfig
from backend.domain.ports.fundamentals_provider import FundamentalsProvider
from backend.domain.ports.market_data_provider import MarketDataProvider
from backend.domain.repositories.ranking_run_repository import RankingRunRepository
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.interfaces.rest.app import create_app
from backend.interfaces.rest.dependencies import (
    get_fundamentals_provider,
    get_market_data_provider,
    get_ranking_run_repository,
    get_universe_repository,
)

pytestmark = pytest.mark.integration


class InMemoryUniverseRepository(UniverseRepository):
    def __init__(self) -> None:
        self._data: dict[uuid.UUID, Universe] = {}

    async def get(self, universe_id: uuid.UUID) -> Universe | None:
        return self._data.get(universe_id)

    async def list(self) -> list[Universe]:
        return list(self._data.values())

    async def save(self, universe: Universe) -> None:
        self._data[universe.id] = universe


class InMemoryRankingRunRepository(RankingRunRepository):
    def __init__(self) -> None:
        self._runs: dict[uuid.UUID, RankingRun] = {}
        self._results: dict[uuid.UUID, list[dict[str, Any]]] = {}

    async def get(self, run_id: uuid.UUID) -> RankingRun | None:
        return self._runs.get(run_id)

    async def save(self, run: RankingRun) -> None:
        self._runs[run.id] = run

    async def list_by_universe(self, universe_id: uuid.UUID) -> list[RankingRun]:
        return [r for r in self._runs.values() if r.universe_id == universe_id]

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[RankingRun]:
        items = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
        return items[offset : offset + limit]

    async def save_results(self, run_id: uuid.UUID, results: list[dict[str, Any]]) -> None:
        self._results[run_id] = results

    async def get_results(self, run_id: uuid.UUID) -> list[dict[str, Any]] | None:
        return self._results.get(run_id)

    async def get_latest_ticker_result(self, ticker: str) -> dict[str, Any] | None:
        return None


class StubFundamentals(FundamentalsProvider):
    async def get_fundamentals(self, tickers: list[str]) -> Any:
        return pd.DataFrame()


class StubMarketData(MarketDataProvider):
    async def get_prices(self, tickers: list[str]) -> Any:
        return pd.DataFrame()


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncGenerator[tuple[AsyncClient, InMemoryUniverseRepository, InMemoryRankingRunRepository], None]:
    monkeypatch.setenv("PRISMA_API_KEY", "test-key")

    universe_repo = InMemoryUniverseRepository()
    run_repo = InMemoryRankingRunRepository()

    app = create_app()
    app.dependency_overrides[get_universe_repository] = lambda: universe_repo
    app.dependency_overrides[get_ranking_run_repository] = lambda: run_repo
    app.dependency_overrides[get_fundamentals_provider] = lambda: StubFundamentals()
    app.dependency_overrides[get_market_data_provider] = lambda: StubMarketData()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, universe_repo, run_repo


async def _seed_universe_and_run(
    universe_repo: InMemoryUniverseRepository,
    run_repo: InMemoryRankingRunRepository,
    *,
    universe_name: str = "Demo-US-5",
    status: str = "completed",
) -> tuple[uuid.UUID, uuid.UUID]:
    from datetime import UTC, datetime

    universe = Universe(
        id=uuid.uuid4(),
        name=universe_name,
        region="US",
        tickers=("AAPL", "MSFT"),
    )
    await universe_repo.save(universe)

    run = RankingRun(
        id=uuid.uuid4(),
        created_at=datetime.now(tz=UTC),
        universe_id=universe.id,
        weight_config=WeightConfig.equal(),
        status=status,  # type: ignore[arg-type]
    )
    await run_repo.save(run)
    return universe.id, run.id


@pytest.mark.asyncio
async def test_list_runs_returns_universe_name(client: tuple[AsyncClient, Any, Any]) -> None:
    c, urepo, rrepo = client
    _, run_id = await _seed_universe_and_run(urepo, rrepo, universe_name="Demo-US-5")

    response = await c.get("/api/v1/runs")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["universe_name"] == "Demo-US-5"
    assert payload[0]["id"] == str(run_id)


@pytest.mark.asyncio
async def test_get_run_returns_universe_name(client: tuple[AsyncClient, Any, Any]) -> None:
    c, urepo, rrepo = client
    _, run_id = await _seed_universe_and_run(urepo, rrepo, universe_name="Tech-Big-12")

    response = await c.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["universe_name"] == "Tech-Big-12"


@pytest.mark.asyncio
async def test_get_run_deleted_universe_fallback(client: tuple[AsyncClient, Any, Any]) -> None:
    c, urepo, rrepo = client
    universe_id, run_id = await _seed_universe_and_run(urepo, rrepo)

    # Universe nachträglich löschen
    urepo._data.pop(universe_id)

    response = await c.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200
    assert response.json()["universe_name"] == "(deleted)"


@pytest.mark.asyncio
async def test_list_runs_deleted_universe_fallback(client: tuple[AsyncClient, Any, Any]) -> None:
    c, urepo, rrepo = client
    universe_id, _ = await _seed_universe_and_run(urepo, rrepo)
    urepo._data.pop(universe_id)

    response = await c.get("/api/v1/runs")

    assert response.status_code == 200
    assert response.json()[0]["universe_name"] == "(deleted)"
```

### Step 1.6: Integration-Test laufen lassen → FAIL

- [ ] Run:

```bash
.venv/bin/pytest backend/tests/integration/test_runs_endpoint_universe_name.py -v
```

Expected: FAIL — Router ruft `RunResponse.from_domain(r)` ohne `universe_name`-Arg auf → TypeError.

### Step 1.7: Router anpassen

- [ ] In `backend/interfaces/rest/routers/runs.py` ersetze die 3 Build-Sites. Komplette neue Datei:

```python
"""FastAPI-Router für /api/v1/runs."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.services.ranking_run_service import (
    RankingRunNotFound,
    RankingRunService,
    UniverseNotFound,
)
from backend.domain.repositories.universe_repository import UniverseRepository
from backend.interfaces.rest.dependencies import (
    get_ranking_run_service,
    get_universe_repository,
    require_api_key,
)
from backend.interfaces.rest.schemas.runs import PostRunRequest, RankingItem, RunResponse

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


async def _universe_name(
    universe_repo: UniverseRepository,
    universe_id: UUID,
) -> str:
    universe = await universe_repo.get(universe_id)
    return universe.name if universe is not None else "(deleted)"


@router.get("", response_model=list[RunResponse])
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: RankingRunService = Depends(get_ranking_run_service),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
) -> list[RunResponse]:
    runs = await service.list_runs(limit=limit, offset=offset)
    return [
        RunResponse.from_domain(r, await _universe_name(universe_repo, r.universe_id))
        for r in runs
    ]


@router.post("", status_code=201, response_model=RunResponse)
async def post_run(
    request: PostRunRequest,
    service: RankingRunService = Depends(get_ranking_run_service),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
    _auth: None = Depends(require_api_key),
) -> RunResponse:
    try:
        run = await service.create_and_execute_run(
            universe_id=request.universe_id,
            weight_config=request.to_weight_config(),
        )
    except UniverseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunResponse.from_domain(run, await _universe_name(universe_repo, run.universe_id))


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: UUID,
    service: RankingRunService = Depends(get_ranking_run_service),
    universe_repo: UniverseRepository = Depends(get_universe_repository),
) -> RunResponse:
    try:
        run = await service.get_run(run_id)
    except RankingRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RunResponse.from_domain(run, await _universe_name(universe_repo, run.universe_id))


@router.get("/{run_id}/rankings", response_model=list[RankingItem])
async def get_rankings(
    run_id: UUID,
    service: RankingRunService = Depends(get_ranking_run_service),
) -> list[RankingItem]:
    try:
        results = await service.get_rankings(run_id)
    except RankingRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [RankingItem.model_validate(r) for r in results]
```

### Step 1.8: Alle Backend-Tests laufen lassen

- [ ] Run:

```bash
.venv/bin/pytest backend/tests/ -v -k "runs or ranking_run"
```

Expected: alle grün. Falls bestehende Tests (`test_runs_endpoint.py`) wegen geänderter `from_domain`-Signatur fehlschlagen, anpassen — die `RunResponse.from_domain`-Calls darin durch `from_domain(run, universe_name="...")` ersetzen oder die Test-Assertions auf das neue Feld erweitern.

### Step 1.9: Pre-Push CI-Mirror

- [ ] Run:

```bash
.venv/bin/ruff check backend/
.venv/bin/ruff format --check backend/
.venv/bin/mypy backend/
.venv/bin/pytest backend/tests/ -q
```

Expected: alle grün.

### Step 1.10: Commit

- [ ] Run:

```bash
git add backend/interfaces/rest/schemas/runs.py backend/interfaces/rest/routers/runs.py backend/tests/unit/interfaces/test_runs_schema_universe_name.py backend/tests/integration/test_runs_endpoint_universe_name.py
git status  # check ob existierende test_runs_endpoint.py auch modifiziert wurde
# falls ja, ebenfalls stagen
git commit -m "$(cat <<'EOF'
feat(rest): universe_name in RunResponse — Run-Liste zeigt Universe-Namen

- RunResponse.from_domain bekommt universe_name-Arg
- Router joint UniverseRepository, Fallback '(deleted)' bei gelöschtem Universe
- Schema-Tests + Endpoint-Tests (Same + Deleted-Fallback)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Frontend — Type-Update + pure Compare-Logik

**Files:**
- Modify: `frontend/lib/api/runs.ts:5-10`
- Create: `frontend/lib/compare.ts`
- Create: `frontend/lib/__tests__/compare.test.ts`

### Step 2.1: Type-Update

- [ ] In `frontend/lib/api/runs.ts` ersetze das `RunResponse`-Interface (Zeilen 5–10):

```typescript
export interface RunResponse {
  id: string;
  status: RankingRunStatus;
  universe_id: string;
  universe_name: string;
  created_at: string;
}
```

### Step 2.2: Compare-Test schreiben (failing)

- [ ] Erstelle `frontend/lib/__tests__/compare.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

import { buildCompareRows, buildCompareStats, type CompareRow } from '@/lib/compare';
import type { RankingItem } from '@/lib/api/runs';

function item(ticker: string, rank: number, score: number): RankingItem {
  return {
    ticker,
    total_rank: rank,
    weighted_avg: score,
    is_sweet_spot: false,
    per_model_ranks: {},
  };
}

describe('buildCompareRows', () => {
  it('returns only stocks present in both runs', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.9), item('MSFT', 2, 0.8), item('TSLA', 3, 0.7)];
    const b: RankingItem[] = [item('AAPL', 2, 0.85), item('MSFT', 1, 0.92), item('NVDA', 3, 0.7)];

    const rows = buildCompareRows(a, b);

    expect(rows.map((r) => r.ticker)).toEqual(['AAPL', 'MSFT']);
  });

  it('sorts rows by rankA ascending', () => {
    const a: RankingItem[] = [item('MSFT', 2, 0.8), item('AAPL', 1, 0.9)];
    const b: RankingItem[] = [item('MSFT', 1, 0.92), item('AAPL', 2, 0.85)];

    const rows = buildCompareRows(a, b);

    expect(rows[0].ticker).toBe('AAPL');
    expect(rows[1].ticker).toBe('MSFT');
  });

  it('computes deltaRank as rankA - rankB (positive = B better)', () => {
    const a: RankingItem[] = [item('AAPL', 5, 0.5)];
    const b: RankingItem[] = [item('AAPL', 2, 0.7)];

    const [row] = buildCompareRows(a, b);

    expect(row.deltaRank).toBe(3); // 5 - 2 = 3, positive → B better
  });

  it('computes deltaScore as scoreB - scoreA (positive = B higher)', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.5)];
    const b: RankingItem[] = [item('AAPL', 1, 0.8)];

    const [row] = buildCompareRows(a, b);

    expect(row.deltaScore).toBeCloseTo(0.3, 5);
  });

  it('filters items with null rank or null score', () => {
    const a: RankingItem[] = [
      item('AAPL', 1, 0.9),
      { ticker: 'MSFT', total_rank: null, weighted_avg: 0.8, is_sweet_spot: false, per_model_ranks: {} },
    ];
    const b: RankingItem[] = [
      item('AAPL', 1, 0.9),
      item('MSFT', 2, 0.7),
    ];

    const rows = buildCompareRows(a, b);

    expect(rows.map((r) => r.ticker)).toEqual(['AAPL']);
  });
});

describe('buildCompareStats', () => {
  it('counts common, only-A, only-B', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.9), item('MSFT', 2, 0.8), item('TSLA', 3, 0.7)];
    const b: RankingItem[] = [item('AAPL', 2, 0.85), item('MSFT', 1, 0.92), item('NVDA', 3, 0.7)];

    const stats = buildCompareStats(a, b);

    expect(stats.commonCount).toBe(2);
    expect(stats.onlyACount).toBe(1);
    expect(stats.onlyBCount).toBe(1);
  });

  it('handles empty intersection', () => {
    const a: RankingItem[] = [item('AAPL', 1, 0.9)];
    const b: RankingItem[] = [item('MSFT', 1, 0.9)];

    const stats = buildCompareStats(a, b);

    expect(stats.commonCount).toBe(0);
    expect(stats.onlyACount).toBe(1);
    expect(stats.onlyBCount).toBe(1);
  });

  it('ignores items with null rank when counting stats', () => {
    const a: RankingItem[] = [
      item('AAPL', 1, 0.9),
      { ticker: 'PENDING', total_rank: null, weighted_avg: null, is_sweet_spot: false, per_model_ranks: {} },
    ];
    const b: RankingItem[] = [item('AAPL', 1, 0.9)];

    const stats = buildCompareStats(a, b);

    expect(stats.commonCount).toBe(1);
    expect(stats.onlyACount).toBe(0);
    expect(stats.onlyBCount).toBe(0);
  });
});
```

### Step 2.3: Test laufen lassen → FAIL

- [ ] Run:

```bash
cd frontend && npm test -- --run lib/__tests__/compare.test.ts
```

Expected: FAIL — `Cannot find module '@/lib/compare'`.

### Step 2.4: Compare-Modul implementieren

- [ ] Erstelle `frontend/lib/compare.ts`:

```typescript
import type { RankingItem } from '@/lib/api/runs';

export interface CompareRow {
  ticker: string;
  rankA: number;
  rankB: number;
  scoreA: number;
  scoreB: number;
  deltaRank: number;
  deltaScore: number;
}

export interface CompareStats {
  commonCount: number;
  onlyACount: number;
  onlyBCount: number;
}

function validItems(items: RankingItem[]): Map<string, { rank: number; score: number }> {
  const result = new Map<string, { rank: number; score: number }>();
  for (const item of items) {
    if (item.total_rank !== null && item.weighted_avg !== null) {
      result.set(item.ticker, { rank: item.total_rank, score: item.weighted_avg });
    }
  }
  return result;
}

export function buildCompareRows(
  rankingsA: RankingItem[],
  rankingsB: RankingItem[],
): CompareRow[] {
  const mapA = validItems(rankingsA);
  const mapB = validItems(rankingsB);
  const rows: CompareRow[] = [];

  for (const [ticker, a] of mapA) {
    const b = mapB.get(ticker);
    if (b === undefined) continue;
    rows.push({
      ticker,
      rankA: a.rank,
      rankB: b.rank,
      scoreA: a.score,
      scoreB: b.score,
      deltaRank: a.rank - b.rank,
      deltaScore: b.score - a.score,
    });
  }

  rows.sort((x, y) => x.rankA - y.rankA);
  return rows;
}

export function buildCompareStats(
  rankingsA: RankingItem[],
  rankingsB: RankingItem[],
): CompareStats {
  const mapA = validItems(rankingsA);
  const mapB = validItems(rankingsB);

  let common = 0;
  for (const ticker of mapA.keys()) {
    if (mapB.has(ticker)) common += 1;
  }

  return {
    commonCount: common,
    onlyACount: mapA.size - common,
    onlyBCount: mapB.size - common,
  };
}
```

### Step 2.5: Test laufen lassen → PASS

- [ ] Run:

```bash
cd frontend && npm test -- --run lib/__tests__/compare.test.ts
```

Expected: alle Cases grün.

### Step 2.6: Frontend-Typecheck + Lint

- [ ] Run:

```bash
cd frontend && npm run typecheck && npm run lint
```

Expected: keine Fehler.

### Step 2.7: Commit

- [ ] Run:

```bash
git add frontend/lib/api/runs.ts frontend/lib/compare.ts frontend/lib/__tests__/compare.test.ts
git commit -m "$(cat <<'EOF'
feat(frontend): pure Compare-Logik + universe_name im RunResponse-Type

- buildCompareRows: Schnittmenge + Δ-Berechnung (rankA-rankB, scoreB-scoreA)
- buildCompareStats: common/only-A/only-B Counts
- RankingItems mit null-Rank/Score werden gefiltert

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Frontend — `<RunHistoryList/>`-Komponente

**Files:**
- Create: `frontend/app/rankings/run-history-list.tsx`
- Create: `frontend/app/rankings/__tests__/run-history-list.test.tsx`

### Step 3.1: Test schreiben (failing)

- [ ] Erstelle `frontend/app/rankings/__tests__/run-history-list.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { RunHistoryList } from '../run-history-list';
import type { RunResponse } from '@/lib/api/runs';

const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockListRuns = vi.fn();
vi.mock('@/lib/api/runs', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api/runs')>('@/lib/api/runs');
  return {
    ...actual,
    listRuns: (limit?: number, offset?: number) => mockListRuns(limit, offset),
  };
});

function makeRun(id: string, status: RunResponse['status'], name = 'Demo-US-5'): RunResponse {
  return {
    id,
    status,
    universe_id: `u-${id}`,
    universe_name: name,
    created_at: '2026-05-29T12:00:00Z',
  };
}

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  mockListRuns.mockReset();
  mockPush.mockReset();
});

describe('<RunHistoryList />', () => {
  it('renders empty state when no runs', async () => {
    mockListRuns.mockResolvedValue([]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => {
      expect(screen.getByText(/noch keine Runs/i)).toBeInTheDocument();
    });
  });

  it('renders rows for completed runs', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed', 'Demo-US-5'),
      makeRun('r2', 'completed', 'Tech-Big-12'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => {
      expect(screen.getByText('Demo-US-5')).toBeInTheDocument();
      expect(screen.getByText('Tech-Big-12')).toBeInTheDocument();
    });
  });

  it('disables checkbox for non-completed runs', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'pending'),
      makeRun('r3', 'failed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => {
      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes).toHaveLength(3);
      expect(checkboxes[0]).not.toBeDisabled();
      expect(checkboxes[1]).toBeDisabled();
      expect(checkboxes[2]).toBeDisabled();
    });
  });

  it('compare button disabled until 2 selected', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'completed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => screen.getAllByRole('checkbox'));
    const button = screen.getByRole('button', { name: /vergleichen/i });
    expect(button).toBeDisabled();

    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    expect(button).toBeDisabled();

    fireEvent.click(screen.getAllByRole('checkbox')[1]);
    expect(button).not.toBeDisabled();
  });

  it('FIFO: third selection removes oldest', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'completed'),
      makeRun('r3', 'completed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => screen.getAllByRole('checkbox'));
    const cbs = screen.getAllByRole('checkbox');

    fireEvent.click(cbs[0]); // r1 selected
    fireEvent.click(cbs[1]); // r1, r2 selected
    fireEvent.click(cbs[2]); // FIFO: r2, r3 selected

    expect(cbs[0]).not.toBeChecked();
    expect(cbs[1]).toBeChecked();
    expect(cbs[2]).toBeChecked();
  });

  it('navigates to /rankings/compare with selected ids', async () => {
    mockListRuns.mockResolvedValue([
      makeRun('r1', 'completed'),
      makeRun('r2', 'completed'),
    ]);

    renderWithClient(<RunHistoryList />);

    await waitFor(() => screen.getAllByRole('checkbox'));
    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.click(screen.getAllByRole('checkbox')[1]);

    fireEvent.click(screen.getByRole('button', { name: /vergleichen/i }));

    expect(mockPush).toHaveBeenCalledWith('/rankings/compare?a=r1&b=r2');
  });
});
```

### Step 3.2: Test laufen lassen → FAIL

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings/__tests__/run-history-list.test.tsx
```

Expected: FAIL — `Cannot find module '../run-history-list'`.

### Step 3.3: Komponente implementieren

- [ ] Erstelle `frontend/app/rankings/run-history-list.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { listRuns, type RankingRunStatus, type RunResponse } from '@/lib/api/runs';

const DATE_FMT = new Intl.DateTimeFormat('de-CH', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

function statusBadgeVariant(status: RankingRunStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed':
      return 'default';
    case 'running':
    case 'pending':
      return 'secondary';
    case 'failed':
      return 'destructive';
  }
}

export function RunHistoryList() {
  const router = useRouter();
  const [selected, setSelected] = useState<string[]>([]);

  const runsQuery = useQuery({
    queryKey: ['runs', 'history'],
    queryFn: () => listRuns(10, 0),
  });

  function toggle(runId: string) {
    setSelected((prev) => {
      if (prev.includes(runId)) {
        return prev.filter((id) => id !== runId);
      }
      if (prev.length < 2) {
        return [...prev, runId];
      }
      return [prev[1], runId]; // FIFO: drop oldest
    });
  }

  function onCompare() {
    if (selected.length !== 2) return;
    router.push(`/rankings/compare?a=${selected[0]}&b=${selected[1]}`);
  }

  return (
    <Card>
      <CardHeader className="pb-3 flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium">Vergangene Runs</CardTitle>
        <Button
          size="sm"
          onClick={onCompare}
          disabled={selected.length !== 2}
          aria-label="Vergleichen"
        >
          Vergleichen
        </Button>
      </CardHeader>
      <CardContent>
        {runsQuery.isLoading && (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 rounded-md bg-muted animate-pulse" />
            ))}
          </div>
        )}

        {runsQuery.data && runsQuery.data.length === 0 && (
          <p className="text-sm text-muted-foreground py-4">
            Noch keine Runs — starte deinen ersten oben.
          </p>
        )}

        {runsQuery.data && runsQuery.data.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10"></TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Universe</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20 text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {runsQuery.data.map((run: RunResponse) => {
                const disabled = run.status !== 'completed';
                return (
                  <TableRow key={run.id}>
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={`Run ${run.id} auswählen`}
                        disabled={disabled}
                        checked={selected.includes(run.id)}
                        onChange={() => toggle(run.id)}
                        className="h-4 w-4 cursor-pointer disabled:cursor-not-allowed"
                      />
                    </TableCell>
                    <TableCell className="text-sm">
                      {DATE_FMT.format(new Date(run.created_at))}
                    </TableCell>
                    <TableCell className="text-sm font-medium">{run.universe_name}</TableCell>
                    <TableCell>
                      <Badge variant={statusBadgeVariant(run.status)}>{run.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Link
                        href={`/rankings/${run.id}`}
                        className="text-sm text-primary hover:underline"
                      >
                        Öffnen
                      </Link>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
```

### Step 3.4: Test laufen lassen → PASS

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings/__tests__/run-history-list.test.tsx
```

Expected: alle 6 Cases grün. Bei Failure: Output prüfen, ob z.B. `screen.getByRole('button', { name: /vergleichen/i })` mehrere Elemente findet — dann Selektor präzisieren.

### Step 3.5: Commit

- [ ] Run:

```bash
git add frontend/app/rankings/run-history-list.tsx frontend/app/rankings/__tests__/run-history-list.test.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): <RunHistoryList/> mit Checkbox-FIFO

- Letzte 10 Runs in Card-Section, neueste zuerst
- Checkbox disabled bei non-completed status
- FIFO bei 3. Klick (max 2 ausgewählt)
- Vergleichen-Button navigiert zu /rankings/compare?a=&b=

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Frontend — `<RunHistoryList/>` auf /rankings einbinden

**Files:**
- Modify: `frontend/app/rankings/page.tsx`

### Step 4.1: Page-Update

- [ ] Ersetze `frontend/app/rankings/page.tsx` komplett mit:

```tsx
import type { Metadata } from 'next';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { RankingsForm } from './rankings-form';
import { RunHistoryList } from './run-history-list';

export const metadata: Metadata = {
  title: 'Rankings',
};

export default function RankingsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
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

      <RunHistoryList />
    </div>
  );
}
```

> **Hinweis:** `max-w-lg` → `max-w-3xl` weil die Tabelle mehr Platz braucht.

### Step 4.2: Typecheck + Lint

- [ ] Run:

```bash
cd frontend && npm run typecheck && npm run lint
```

Expected: keine Fehler.

### Step 4.3: Bestehende Page-Tests prüfen

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings
```

Expected: alle grün. Falls existierende `rankings-form.test.tsx` durch das Page-Layout-Update fehlschlägt: anpassen (z.B. wenn ein Selektor `max-w-lg` referenziert — sehr unwahrscheinlich).

### Step 4.4: Commit

- [ ] Run:

```bash
git add frontend/app/rankings/page.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): /rankings rendert <RunHistoryList/> unter Form

Layout breiter (max-w-3xl) damit Tabelle Platz hat.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Frontend — `/rankings/compare` Page + Banner + Tabelle

**Files:**
- Create: `frontend/app/rankings/compare/page.tsx`
- Create: `frontend/app/rankings/compare/compare-client.tsx`
- Create: `frontend/app/rankings/compare/compare-banner.tsx`
- Create: `frontend/app/rankings/compare/compare-table.tsx`
- Create: `frontend/app/rankings/compare/__tests__/compare-banner.test.tsx`
- Create: `frontend/app/rankings/compare/__tests__/compare-table.test.tsx`

### Step 5.1: Banner-Test schreiben (failing)

- [ ] Erstelle `frontend/app/rankings/compare/__tests__/compare-banner.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CompareBanner } from '../compare-banner';
import type { RunResponse } from '@/lib/api/runs';

function makeRun(id: string, name: string): RunResponse {
  return {
    id,
    status: 'completed',
    universe_id: `u-${id}`,
    universe_name: name,
    created_at: '2026-05-29T12:00:00Z',
  };
}

describe('<CompareBanner />', () => {
  it('shows both run headers', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'Demo-US-5')}
        runB={makeRun('b', 'Demo-US-5')}
        stats={{ commonCount: 5, onlyACount: 0, onlyBCount: 0 }}
      />,
    );

    expect(screen.getByText(/Run A/i)).toBeInTheDocument();
    expect(screen.getByText(/Run B/i)).toBeInTheDocument();
    expect(screen.getAllByText('Demo-US-5')).toHaveLength(2);
  });

  it('shows only commonCount for same-universe comparison', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'Demo-US-5')}
        runB={makeRun('b', 'Demo-US-5')}
        stats={{ commonCount: 5, onlyACount: 0, onlyBCount: 0 }}
      />,
    );

    expect(screen.getByText(/5 gemeinsame Stocks/i)).toBeInTheDocument();
    expect(screen.queryByText(/nur in Run A/i)).not.toBeInTheDocument();
  });

  it('shows all three counts for cross-universe comparison', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'Demo-US-5')}
        runB={makeRun('b', 'Tech-Big-12')}
        stats={{ commonCount: 3, onlyACount: 2, onlyBCount: 9 }}
      />,
    );

    expect(screen.getByText(/3 gemeinsam/i)).toBeInTheDocument();
    expect(screen.getByText(/2 nur in Run A/i)).toBeInTheDocument();
    expect(screen.getByText(/9 nur in Run B/i)).toBeInTheDocument();
  });

  it('shows warning when commonCount is 0', () => {
    render(
      <CompareBanner
        runA={makeRun('a', 'X')}
        runB={makeRun('b', 'Y')}
        stats={{ commonCount: 0, onlyACount: 5, onlyBCount: 7 }}
      />,
    );

    expect(screen.getByText(/keine gemeinsamen Stocks/i)).toBeInTheDocument();
  });
});
```

### Step 5.2: Banner-Test laufen lassen → FAIL

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings/compare/__tests__/compare-banner.test.tsx
```

Expected: FAIL — `Cannot find module '../compare-banner'`.

### Step 5.3: Banner implementieren

- [ ] Erstelle `frontend/app/rankings/compare/compare-banner.tsx`:

```tsx
import { AlertTriangle } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import type { CompareStats } from '@/lib/compare';
import type { RunResponse } from '@/lib/api/runs';

const DATE_FMT = new Intl.DateTimeFormat('de-CH', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

interface Props {
  runA: RunResponse;
  runB: RunResponse;
  stats: CompareStats;
}

export function CompareBanner({ runA, runB, stats }: Props) {
  const sameUniverse = runA.universe_id === runB.universe_id;

  return (
    <Card>
      <CardContent className="py-4 space-y-3">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-muted-foreground text-xs">Run A</div>
            <div className="font-medium">{runA.universe_name}</div>
            <div className="text-muted-foreground text-xs">
              {DATE_FMT.format(new Date(runA.created_at))}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Run B</div>
            <div className="font-medium">{runB.universe_name}</div>
            <div className="text-muted-foreground text-xs">
              {DATE_FMT.format(new Date(runB.created_at))}
            </div>
          </div>
        </div>

        {stats.commonCount === 0 ? (
          <div className="flex items-center gap-2 rounded-md bg-amber-50 dark:bg-amber-950 px-3 py-2 text-sm text-amber-900 dark:text-amber-200">
            <AlertTriangle className="h-4 w-4" />
            <span>Keine gemeinsamen Stocks — Vergleich nicht möglich.</span>
          </div>
        ) : sameUniverse ? (
          <div className="text-sm text-muted-foreground">
            {stats.commonCount} gemeinsame Stocks verglichen
          </div>
        ) : (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span><strong className="text-foreground">{stats.commonCount}</strong> gemeinsam</span>
            <span><strong className="text-foreground">{stats.onlyACount}</strong> nur in Run A</span>
            <span><strong className="text-foreground">{stats.onlyBCount}</strong> nur in Run B</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

### Step 5.4: Banner-Test laufen lassen → PASS

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings/compare/__tests__/compare-banner.test.tsx
```

Expected: 4 passed.

### Step 5.5: Table-Test schreiben (failing)

- [ ] Erstelle `frontend/app/rankings/compare/__tests__/compare-table.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { CompareTable } from '../compare-table';
import type { CompareRow } from '@/lib/compare';

function row(overrides: Partial<CompareRow>): CompareRow {
  return {
    ticker: 'AAPL',
    rankA: 1,
    rankB: 1,
    scoreA: 0.9,
    scoreB: 0.9,
    deltaRank: 0,
    deltaScore: 0,
    ...overrides,
  };
}

describe('<CompareTable />', () => {
  it('renders one row per CompareRow', () => {
    render(<CompareTable rows={[row({ ticker: 'AAPL' }), row({ ticker: 'MSFT' })]} />);

    expect(screen.getByText('AAPL')).toBeInTheDocument();
    expect(screen.getByText('MSFT')).toBeInTheDocument();
  });

  it('shows green up indicator when deltaRank > 0 (B better)', () => {
    const { container } = render(<CompareTable rows={[row({ deltaRank: 3 })]} />);

    const deltaCell = container.querySelector('[data-testid="delta-rank-cell"]');
    expect(deltaCell?.textContent).toContain('+3');
    expect(deltaCell?.className).toMatch(/text-green/);
  });

  it('shows red down indicator when deltaRank < 0 (A better)', () => {
    const { container } = render(<CompareTable rows={[row({ deltaRank: -2 })]} />);

    const deltaCell = container.querySelector('[data-testid="delta-rank-cell"]');
    expect(deltaCell?.textContent).toContain('-2');
    expect(deltaCell?.className).toMatch(/text-red/);
  });

  it('shows muted dot when deltaRank === 0', () => {
    const { container } = render(<CompareTable rows={[row({ deltaRank: 0 })]} />);

    const deltaCell = container.querySelector('[data-testid="delta-rank-cell"]');
    expect(deltaCell?.textContent).toContain('0');
    expect(deltaCell?.className).toMatch(/text-muted/);
  });

  it('formats deltaScore with sign and two decimals', () => {
    const { container } = render(<CompareTable rows={[row({ deltaScore: 0.123 })]} />);

    const cell = container.querySelector('[data-testid="delta-score-cell"]');
    expect(cell?.textContent).toContain('+0.12');
  });
});
```

### Step 5.6: Table-Test laufen lassen → FAIL

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings/compare/__tests__/compare-table.test.tsx
```

Expected: FAIL — Modul fehlt.

### Step 5.7: Table implementieren

- [ ] Erstelle `frontend/app/rankings/compare/compare-table.tsx`:

```tsx
import { ArrowDown, ArrowUp, Minus } from 'lucide-react';

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import type { CompareRow } from '@/lib/compare';

interface Props {
  rows: CompareRow[];
}

function formatDeltaRank(delta: number): { text: string; className: string; icon: React.ReactNode } {
  if (delta > 0) {
    return {
      text: `+${delta}`,
      className: 'text-green-600 dark:text-green-400',
      icon: <ArrowUp className="inline h-3 w-3" />,
    };
  }
  if (delta < 0) {
    return {
      text: `${delta}`,
      className: 'text-red-600 dark:text-red-400',
      icon: <ArrowDown className="inline h-3 w-3" />,
    };
  }
  return {
    text: '0',
    className: 'text-muted-foreground',
    icon: <Minus className="inline h-3 w-3" />,
  };
}

function formatDeltaScore(delta: number): { text: string; className: string } {
  const sign = delta > 0 ? '+' : '';
  const formatted = `${sign}${delta.toFixed(2)}`;
  if (delta > 0) return { text: formatted, className: 'text-green-600 dark:text-green-400' };
  if (delta < 0) return { text: formatted, className: 'text-red-600 dark:text-red-400' };
  return { text: '0.00', className: 'text-muted-foreground' };
}

export function CompareTable({ rows }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Ticker</TableHead>
          <TableHead className="text-right">Rank A</TableHead>
          <TableHead className="text-right">Rank B</TableHead>
          <TableHead className="text-right">Δ Rank</TableHead>
          <TableHead className="text-right">Δ Score</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const dr = formatDeltaRank(r.deltaRank);
          const ds = formatDeltaScore(r.deltaScore);
          return (
            <TableRow key={r.ticker}>
              <TableCell className="font-medium">{r.ticker}</TableCell>
              <TableCell className="text-right tabular-nums">{r.rankA}</TableCell>
              <TableCell className="text-right tabular-nums">{r.rankB}</TableCell>
              <TableCell
                data-testid="delta-rank-cell"
                className={`text-right tabular-nums ${dr.className}`}
              >
                <span className="inline-flex items-center gap-1">
                  {dr.icon}
                  {dr.text}
                </span>
              </TableCell>
              <TableCell
                data-testid="delta-score-cell"
                className={`text-right tabular-nums ${ds.className}`}
              >
                {ds.text}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
```

### Step 5.8: Table-Test laufen lassen → PASS

- [ ] Run:

```bash
cd frontend && npm test -- --run app/rankings/compare/__tests__/compare-table.test.tsx
```

Expected: 5 passed.

### Step 5.9: Compare-Client + Page implementieren

- [ ] Erstelle `frontend/app/rankings/compare/compare-client.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useQueries } from '@tanstack/react-query';
import { ArrowLeft, XCircle } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { getRankings, getRun, type RankingItem, type RunResponse } from '@/lib/api/runs';
import { buildCompareRows, buildCompareStats } from '@/lib/compare';
import { ApiError } from '@/lib/api/client';

import { CompareBanner } from './compare-banner';
import { CompareTable } from './compare-table';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function ErrorBox({ title, detail }: { title: string; detail?: string }) {
  return (
    <Card>
      <CardContent className="py-12 text-center space-y-2">
        <XCircle className="mx-auto h-8 w-8 text-destructive" />
        <p className="text-lg font-medium">{title}</p>
        {detail && <p className="text-sm text-muted-foreground">{detail}</p>}
        <Link
          href="/rankings"
          className="inline-flex items-center text-sm text-primary hover:underline mt-2"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Zurück zur Übersicht
        </Link>
      </CardContent>
    </Card>
  );
}

function Skeleton() {
  return (
    <div className="space-y-3">
      <div className="h-24 rounded-md bg-muted animate-pulse" />
      <div className="h-64 rounded-md bg-muted animate-pulse" />
    </div>
  );
}

export function CompareClient() {
  const params = useSearchParams();
  const a = params.get('a');
  const b = params.get('b');

  if (!a || !b) {
    return <ErrorBox title="Fehlende Run-IDs" detail="URL benötigt ?a=<runId>&b=<runId>" />;
  }
  if (!UUID_RE.test(a) || !UUID_RE.test(b)) {
    return <ErrorBox title="Ungültige Run-ID" />;
  }

  const queries = useQueries({
    queries: [
      { queryKey: ['run', a], queryFn: () => getRun(a), retry: (n: number, e: unknown) => !(e instanceof ApiError && e.status === 404) && n < 2 },
      { queryKey: ['run', b], queryFn: () => getRun(b), retry: (n: number, e: unknown) => !(e instanceof ApiError && e.status === 404) && n < 2 },
      { queryKey: ['rankings', a], queryFn: () => getRankings(a) },
      { queryKey: ['rankings', b], queryFn: () => getRankings(b) },
    ],
  });

  const [runAQ, runBQ, rankAQ, rankBQ] = queries;

  if (queries.some((q) => q.isLoading)) {
    return <Skeleton />;
  }

  const notFound = [runAQ.error, runBQ.error].find(
    (e) => e instanceof ApiError && e.status === 404,
  );
  if (notFound) {
    return <ErrorBox title="Run nicht gefunden" />;
  }

  const runA = runAQ.data as RunResponse | undefined;
  const runB = runBQ.data as RunResponse | undefined;
  if (!runA || !runB) {
    return <ErrorBox title="Run konnte nicht geladen werden" />;
  }

  if (runA.status !== 'completed' || runB.status !== 'completed') {
    return <ErrorBox title="Run noch nicht fertig" detail="Bitte warte bis beide Runs den Status 'completed' haben." />;
  }

  const rankingsA = (rankAQ.data ?? []) as RankingItem[];
  const rankingsB = (rankBQ.data ?? []) as RankingItem[];

  const stats = buildCompareStats(rankingsA, rankingsB);
  const rows = buildCompareRows(rankingsA, rankingsB);

  return (
    <div className="space-y-4">
      <CompareBanner runA={runA} runB={runB} stats={stats} />
      {stats.commonCount > 0 && <CompareTable rows={rows} />}
    </div>
  );
}
```

- [ ] Erstelle `frontend/app/rankings/compare/page.tsx`:

```tsx
import { Suspense } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import type { Metadata } from 'next';

import { CompareClient } from './compare-client';

export const metadata: Metadata = {
  title: 'Run-Vergleich',
};

function PageSkeleton() {
  return (
    <div className="space-y-3">
      <div className="h-24 rounded-md bg-muted animate-pulse" />
      <div className="h-64 rounded-md bg-muted animate-pulse" />
    </div>
  );
}

export default function ComparePage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="space-y-2">
        <Link
          href="/rankings"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Zurück
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Run-Vergleich</h1>
      </div>

      <Suspense fallback={<PageSkeleton />}>
        <CompareClient />
      </Suspense>
    </div>
  );
}
```

### Step 5.10: Typecheck + Lint + Tests

- [ ] Run:

```bash
cd frontend && npm run typecheck && npm run lint && npm test -- --run
```

Expected: alle grün.

### Step 5.11: Commit

- [ ] Run:

```bash
git add frontend/app/rankings/compare/
git commit -m "$(cat <<'EOF'
feat(frontend): /rankings/compare Page — Side-by-Side-Vergleich

- <CompareBanner/> mit Run-Headers und 1- oder 3-Counts-Display
- <CompareTable/> mit Δ Rank (↑/↓/·) und Δ Score (±0.NN)
- Error-States: missing/invalid UUID, 404, not-completed
- Skeleton beim parallelen Laden der 4 Endpoints
- Suspense-Boundary für useSearchParams

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: E2E-Spec

**Files:**
- Create: `frontend/e2e/run-history.spec.ts`

### Step 6.1: Existierendes E2E-Pattern prüfen

- [ ] Run:

```bash
ls frontend/e2e/
cat frontend/playwright.config.ts | head -30
```

Erwartung: Pattern erkennen — Base-URL, ob Backend automatisch hochgefahren wird oder lokal laufen muss. Wenn Backend lokal laufen muss: das Spec dokumentiert das in Kommentar.

### Step 6.2: Spec schreiben

- [ ] Erstelle `frontend/e2e/run-history.spec.ts`:

```typescript
import { test, expect } from '@playwright/test';

const API_KEY = process.env.PRISMA_API_KEY ?? 'demo-key';
const API_URL = process.env.E2E_API_URL ?? 'http://localhost:8000';

/**
 * Voraussetzung: Backend läuft auf localhost:8000 mit Postgres,
 * Demo-Universes existieren. Dieses Spec stellt sicher, dass es ≥2 completed Runs gibt.
 */
async function ensureTwoRuns(request: import('@playwright/test').APIRequestContext): Promise<string[]> {
  const universesRes = await request.get(`${API_URL}/api/v1/universes`);
  expect(universesRes.ok()).toBeTruthy();
  const universes = await universesRes.json();
  const universeId: string = universes.items[0].id;

  const runsRes = await request.get(`${API_URL}/api/v1/runs?limit=10`);
  const runs: Array<{ id: string; status: string }> = await runsRes.json();
  const completed = runs.filter((r) => r.status === 'completed');
  if (completed.length >= 2) {
    return [completed[0].id, completed[1].id];
  }

  // Fehlende Runs nachziehen
  const toCreate = 2 - completed.length;
  const newIds: string[] = [];
  for (let i = 0; i < toCreate; i += 1) {
    const res = await request.post(`${API_URL}/api/v1/runs`, {
      headers: { 'X-API-Key': API_KEY },
      data: { universe_id: universeId },
    });
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    newIds.push(body.id);
  }

  // Polling auf completed
  for (const id of newIds) {
    for (let attempt = 0; attempt < 30; attempt += 1) {
      const r = await request.get(`${API_URL}/api/v1/runs/${id}`);
      const data = await r.json();
      if (data.status === 'completed') break;
      if (data.status === 'failed') throw new Error(`Run ${id} failed`);
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  }

  return [...completed.map((r) => r.id), ...newIds].slice(0, 2);
}

test.describe('Run-History', () => {
  test('list, select two, compare', async ({ page, request }) => {
    await ensureTwoRuns(request);

    await page.goto('/rankings');
    await expect(page.getByText('Vergangene Runs')).toBeVisible();

    const checkboxes = page.locator('input[type="checkbox"]:not([disabled])');
    await expect(checkboxes.first()).toBeVisible();
    await checkboxes.nth(0).check();
    await checkboxes.nth(1).check();

    const compareBtn = page.getByRole('button', { name: /vergleichen/i });
    await expect(compareBtn).toBeEnabled();
    await compareBtn.click();

    await expect(page).toHaveURL(/\/rankings\/compare\?a=.+&b=.+/);
    await expect(page.getByText(/Run A/i)).toBeVisible();
    await expect(page.getByText(/Run B/i)).toBeVisible();

    // Mindestens eine Datenzeile in der Compare-Tabelle (Ticker = Großbuchstaben-Word)
    const tickerCell = page.locator('table tbody tr td').first();
    await expect(tickerCell).toBeVisible();
  });
});
```

### Step 6.3: E2E-Spec laufen lassen

- [ ] Voraussetzungen prüfen: Backend (Port 8000) und Frontend (Port 3000) laufen lokal.

- [ ] Run:

```bash
cd frontend && npx playwright test run-history --reporter=list
```

Expected: 1 passed. Bei Failure:
- Logs lesen — wenn Selektoren nicht matchen, präzisieren
- Wenn Polling-Timeout: Backend langsam → Timeout erhöhen oder weniger strenge Erwartung (nur prüfen dass Banner sichtbar wird, ohne Tabellen-Assertion)

### Step 6.4: Commit

- [ ] Run:

```bash
git add frontend/e2e/run-history.spec.ts
git commit -m "$(cat <<'EOF'
test(e2e): Run-History — Liste, 2 auswählen, Compare-Page

Beforehand-Helper stellt sicher dass ≥2 completed Runs in DB existieren.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Pre-Push CI-Mirror + Manual Smoke-Test

### Step 7.1: Backend Full-Check

- [ ] Run:

```bash
.venv/bin/ruff check backend/
.venv/bin/ruff format --check backend/
.venv/bin/mypy backend/
.venv/bin/pytest backend/tests/ -q
```

Expected: alle grün.

### Step 7.2: Frontend Full-Check

- [ ] Run:

```bash
cd frontend && npm run lint && npm run typecheck && npm test -- --run
```

Expected: alle grün.

### Step 7.3: Manueller Smoke-Test

- [ ] Backend starten:

```bash
DATABASE_URL=postgresql+asyncpg://prisma:prisma@localhost:5432/prisma .venv/bin/uvicorn backend.interfaces.rest.app:create_app --factory --reload --port 8000
```

- [ ] Frontend starten (anderes Terminal):

```bash
cd frontend && npm run dev
```

- [ ] Im Browser http://localhost:3000/rankings öffnen:
  - „Vergangene Runs"-Card sichtbar
  - Rows haben Universe-Namen (nicht UUIDs)
  - 2 Checkboxen klicken → Compare-Button enabled
  - Klick → /rankings/compare?a=&b=
  - Banner zeigt beide Universe-Namen + Counts
  - Tabelle zeigt Common-Stocks mit ±Δ-Werten

- [ ] Edge-Case manuell: `/rankings/compare?a=invalid&b=alsoinvalid` → Error-Box mit Zurück-Link.

### Step 7.4: Merge in demo/all-features

- [ ] Run:

```bash
git checkout demo/all-features
git merge --no-ff feat/run-history
git checkout feat/run-history
```

Optional: PR gegen `main` für Code-Review:

```bash
git push -u origin feat/run-history
gh pr create --title "feat: Run-History — Liste + Compare-Page" --body "$(cat <<'EOF'
## Summary
- Backend: universe_name in RunResponse (kein Migration-Touch)
- Frontend: <RunHistoryList/> mit Checkbox-FIFO + /rankings/compare-Page
- Spec: docs/specs/2026-05-29-run-history-design.md

## Test plan
- [x] Backend-Tests grün (Schema + Endpoint + Fallback)
- [x] Frontend Vitest grün (compare-Logik, RunHistoryList, Compare-Components)
- [x] E2E grün (Liste → 2 selected → Compare)
- [x] Manueller Smoke-Test im Browser

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec-Coverage:**
- ✓ Backend `universe_name` (Task 1)
- ✓ Schema + Service + Router angepasst (Task 1)
- ✓ Backend-Tests Schema + Endpoint + Fallback (Task 1)
- ✓ Pure Compare-Logik mit Tests (Task 2)
- ✓ `<RunHistoryList/>` mit FIFO + Tests (Task 3)
- ✓ /rankings-Page-Integration (Task 4)
- ✓ /rankings/compare Page + Banner + Table mit Tests (Task 5)
- ✓ Edge-Cases: missing params, invalid UUID, 404, not-completed, 0-common (Task 5)
- ✓ E2E (Task 6)
- ✓ Pre-Push CI-Mirror (Task 7)

**Placeholder-Scan:** keine TBD/TODO/„similar to". Alle Code-Blöcke vollständig.

**Type-Consistency:**
- `RunResponse` (mit `universe_name`) konsistent in `runs.ts`, Tests, Banner, Client
- `CompareRow` und `CompareStats` Properties konsistent zwischen `compare.ts`, Tests, Banner, Table
- `RankingItem` Felder (`total_rank`, `weighted_avg`) konsistent
- `from_domain(run, universe_name)` Signatur konsistent zwischen Schema-Definition und allen 3 Router-Call-Sites

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-run-history.md`. Empfehlung: **Subagent-Driven Development** — pro Task ein Implementer-Subagent mit Pre-Discovered-Context im Prompt, danach Reviewer-Subagent, dann Self-Review durch Orchestrator vor Commit. Tasks 1–6 sind voneinander abhängig (sequenziell), Task 7 ist Cleanup.
