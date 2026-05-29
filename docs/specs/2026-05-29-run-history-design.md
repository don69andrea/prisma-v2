# Run-History — Design

**Datum:** 2026-05-29
**Status:** Draft, ready-for-plan
**Backlog-Item:** #6 (Run-History für Demo-Tiefe)
**Branch:** `feat/run-history` (von `origin/main`)

## Ziel

Vergangene Ranking-Läufe werden auf `/rankings` als Tabelle gelistet. Zwei Runs lassen sich auswählen und auf `/rankings/compare` Side-by-Side vergleichen, mit Fokus auf Stabilität der Top-Picks und Rank-Bewegungen.

**Demo-Story:** „Schauen Sie, der Top-Pick hat sich zwischen Run A und B nicht verändert — robust!" — bzw. das Gegenteil als Evidenz für Modell-Sensitivität.

## Scope

**In Scope**
- Run-Liste auf `/rankings` (max 10 neueste)
- Checkbox-Selection mit FIFO bei 3. Klick (immer max 2 ausgewählt)
- Vergleich-Page `/rankings/compare?a=<uuid>&b=<uuid>`
- Cross-Universe-Vergleich: Schnittmenge der Tickers + Banner mit Counts
- Backend-Erweiterung: `universe_name` in `RunResponse`

**Out of Scope**
- Pagination / "Show more" (YAGNI für Demo-DB)
- Mehr als 2 Runs gleichzeitig vergleichen
- Filterung der Liste nach Universe/Status
- Speichern von Vergleichs-Snapshots
- Export der Compare-Tabelle

## Backend

### Änderung: `RunResponse` um `universe_name` erweitern

**Datei:** `backend/interfaces/rest/schemas/runs.py`

```python
class RunResponse(BaseModel):
    id: UUID
    status: RankingRunStatus
    universe_id: UUID
    universe_name: str         # NEU
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

**Datei:** `backend/application/services/ranking_run_service.py`
- `list_runs()` und `get_run()` joinen Universe-Entity über `UniverseRepository.get(universe_id)`.
- Fallback bei gelöschtem Universe: `universe_name = "(deleted)"` — kein 500, sondern lesbarer String. Domain-Test stellt das sicher.

**Datei:** `backend/interfaces/rest/routers/runs.py`
- `RunResponse.from_domain(run, universe_name)` an den 3 Stellen, an denen `RunResponse` gebaut wird (POST, GET single, GET list).

**Migration:** Keine. Reines Pydantic-Schema + Service-Loader.

### Backend-Tests
- `backend/tests/interfaces/rest/test_runs_router.py`
  - GET /runs liefert `universe_name`
  - GET /runs/{id} liefert `universe_name`
  - POST /runs liefert `universe_name` direkt
- `backend/tests/application/test_ranking_run_service.py`
  - Service liefert `universe_name` aus Universe-Repo
  - Fallback "(deleted)" wenn Universe nicht mehr existiert

## Frontend

### Datei-Struktur

```
frontend/
  app/rankings/
    page.tsx                          # ERWEITERT: bindet <RunHistoryList/> ein
    run-history-list.tsx              # NEU
    __tests__/
      run-history-list.test.tsx       # NEU
    compare/
      page.tsx                        # NEU
      compare-client.tsx              # NEU (Suspense-Client mit useSearchParams)
      compare-table.tsx               # NEU
      compare-banner.tsx              # NEU
      __tests__/
        compare-table.test.tsx        # NEU
        compare-banner.test.tsx       # NEU
  lib/api/runs.ts                     # ERWEITERT: universe_name in RunResponse
  lib/compare.ts                      # NEU: pure Diff-Logik (Common-Set, Δ-Berechnung)
  lib/__tests__/compare.test.ts       # NEU
  e2e/
    run-history.spec.ts               # NEU
```

### `lib/api/runs.ts` — Type-Erweiterung

```typescript
export interface RunResponse {
  id: string;
  status: RankingRunStatus;
  universe_id: string;
  universe_name: string;     // NEU
  created_at: string;
}
```

### `lib/compare.ts` — Pure Diff-Logik

Reine Funktionen, kein React, gut testbar:

```typescript
export interface CompareRow {
  ticker: string;
  rankA: number;
  rankB: number;
  scoreA: number;
  scoreB: number;
  deltaRank: number;   // rankA - rankB; positiv = B besser
  deltaScore: number;  // scoreB - scoreA; positiv = B höher
}

export interface CompareStats {
  commonCount: number;
  onlyACount: number;
  onlyBCount: number;
}

export function buildCompareRows(
  rankingsA: RankingItem[],
  rankingsB: RankingItem[],
): CompareRow[];

export function buildCompareStats(
  rankingsA: RankingItem[],
  rankingsB: RankingItem[],
): CompareStats;
```

**Konventionen:**
- Items mit `total_rank === null` oder `weighted_avg === null` werden gefiltert (kein Bestandteil von Common-Stocks)
- `commonCount` = Anzahl Tickers in beiden Listen mit gültigem Rank
- Sortierung der Rows: nach `rankA` aufsteigend
- Δ-Vorzeichen: `deltaRank > 0` → Stock ist in Run B höher gerankt → grüner Pfeil ↑

### `<RunHistoryList/>` — Komponente

**Datei:** `frontend/app/rankings/run-history-list.tsx`

```typescript
'use client';

export function RunHistoryList() {
  // useQuery: listRuns(10, 0)
  // useState<[string, string?] | []>: selected IDs (FIFO max 2)
  // useRouter: für Navigation zu /rankings/compare
}
```

**UI-Layout:**
- Card-Section unterhalb von `<RankingsForm/>`, Überschrift „Vergangene Runs"
- Sticky-Header in der Section: „Vergleichen"-Button (rechts), disabled bis `selected.length === 2`
- Tabelle:
  - Checkbox-Spalte (links) — disabled wenn `status !== 'completed'`
  - **Date** — `created_at` formatiert mit `Intl.DateTimeFormat('de-CH', {dateStyle: 'medium', timeStyle: 'short'})`
  - **Universe** — `universe_name`
  - **Status** — Badge (existierende `<StatusBadge/>` wiederverwenden, falls vorhanden; sonst inline-coloured Span)
  - **Action** — „Öffnen"-Link zu `/rankings/{id}`
- Neueste Runs zuerst (Backend liefert bereits desc by created_at)
- Loading-State: Skeleton-Rows
- Empty-State: „Noch keine Runs — starte deinen ersten oben."

**Checkbox-FIFO-Logik:**
```
onToggle(runId):
  if selected.includes(runId):
    remove it
  else if selected.length < 2:
    append it
  else:
    drop selected[0], append runId  // FIFO
```

**Vergleichen-Klick:**
```
router.push(`/rankings/compare?a=${selected[0]}&b=${selected[1]}`)
```

### `/rankings/compare` — Page

**Datei:** `frontend/app/rankings/compare/page.tsx`

```typescript
import { Suspense } from 'react';
import { CompareClient } from './compare-client';

export default function ComparePage() {
  return (
    <Suspense fallback={<ComparePageSkeleton />}>
      <CompareClient />
    </Suspense>
  );
}
```

**Datei:** `frontend/app/rankings/compare/compare-client.tsx`
- `useSearchParams()` liest `a` und `b`
- Parallel `Promise.all([getRun(a), getRun(b), getRankings(a), getRankings(b)])` via `useQueries`
- Bei fehlenden Params oder UUID-Format-Fehler: Error-Box mit Link zurück zu /rankings
- Bei `status !== 'completed'` für einen der Runs: Error-Box „Run noch nicht fertig — bitte später erneut versuchen"
- Bei erfolgreichem Load: `<CompareBanner/>` + `<CompareTable/>`

### `<CompareBanner/>` — Komponente

**Datei:** `frontend/app/rankings/compare/compare-banner.tsx`

Banner oben auf der Page. Zeigt:
- Run-Headers: „**Run A:** {universe_name} · {date}" und „**Run B:** {universe_name} · {date}"
- Stats-Zeile:
  - Same-Universe: „N gemeinsame Stocks verglichen"
  - Cross-Universe: „X gemeinsam · Y nur in Run A · Z nur in Run B" — Counts mit dezenten Badges
- Bei `commonCount === 0`: Banner zeigt Warnhinweis „Keine gemeinsamen Stocks — Vergleich nicht möglich", Tabelle wird nicht gerendert

### `<CompareTable/>` — Komponente

**Datei:** `frontend/app/rankings/compare/compare-table.tsx`

Spalten:
- **Ticker** — sortierbar nicht nötig (sortiert ist nach rankA)
- **Rank A** — Zahl
- **Rank B** — Zahl
- **Δ Rank** — `±N` mit Pfeil-Icon:
  - `> 0` → grüner ↑ („+3" mit text-green-600)
  - `< 0` → roter ↓ („-2" mit text-red-600)
  - `=== 0` → grauer · („0" mit text-muted-foreground)
- **Δ Score** — `±N.NN` mit gleicher Farb-Konvention

Volle Liste aller Common-Stocks. Bei >50 Rows ist Standard-CSS-Scroll OK (kein Virtual-Scrolling).

### Tests (Frontend)

**Vitest:**
- `lib/__tests__/compare.test.ts`
  - `buildCompareRows` mit Same-Universe-Input → alle Stocks
  - mit Cross-Universe → nur Schnittmenge
  - mit `null`-Ranks gefiltert
  - Δ-Berechnung-Vorzeichen korrekt
  - Sortierung nach `rankA` aufsteigend
  - `buildCompareStats` zählt commonCount/onlyACount/onlyBCount
- `app/rankings/__tests__/run-history-list.test.tsx`
  - Liste rendert Rows
  - Checkbox bei pending/failed disabled
  - FIFO bei 3. Klick: oldest wird entfernt
  - „Vergleichen"-Button bei 0/1 selected disabled, bei 2 enabled
  - Klick navigiert mit korrekter Query-String
  - Empty-State bei 0 Runs
- `app/rankings/compare/__tests__/compare-table.test.tsx`
  - Renders Rows mit korrekten Δ-Werten
  - Δ > 0 → grünes ↑-Icon
  - Δ < 0 → rotes ↓-Icon
  - Δ === 0 → grauer Dot
- `app/rankings/compare/__tests__/compare-banner.test.tsx`
  - Same-Universe-Stats: nur commonCount
  - Cross-Universe-Stats: alle 3 Counts
  - `commonCount === 0` → Warnhinweis sichtbar

**Playwright E2E** (`frontend/e2e/run-history.spec.ts`):
- Voraussetzung: Demo-Seed-Skript hat 2+ completed Runs (siehe „Test-Daten")
- Navigate zu /rankings
- 2 Run-Checkboxen klicken
- „Vergleichen" klicken
- Erwarte: URL enthält `/rankings/compare?a=...&b=...`
- Erwarte: Banner sichtbar mit Universe-Namen
- Erwarte: ≥1 Row in Compare-Tabelle mit gültigem Δ

## Test-Daten

Demo-DB hat aktuell mind. 1 completed Run. Für E2E reproduzierbar:
- Falls noch nicht vorhanden: 2. Run programmatisch via API erzeugen (Same-Universe OK)
- E2E-Spec hat eine `beforeAll`-Hook die 2 Runs sicherstellt (POST /api/v1/runs falls nötig, wartet via Polling auf `status === 'completed'`)

## Edge Cases — verbindlich

| Fall | Verhalten |
|---|---|
| 0 Runs in DB | Empty-State in `<RunHistoryList/>`, Button nicht sichtbar |
| 1 Run in DB | Single Row, Compare-Button disabled |
| Run mit `status !== 'completed'` | Checkbox disabled, Row sichtbar |
| `/compare` ohne `a` oder `b` Param | Error-Box mit Link zu /rankings |
| `/compare` mit ungültiger UUID | Error-Box „Run nicht gefunden" |
| `/compare` mit pending/failed Run | Error-Box „Run noch nicht fertig" |
| Same-Universe-Vergleich | Banner zeigt nur commonCount |
| Cross-Universe-Vergleich, ≥1 common | Banner zeigt alle 3 Counts, Tabelle rendert |
| Cross-Universe-Vergleich, 0 common | Banner zeigt Warnhinweis, Tabelle wird nicht gerendert |
| Gelöschtes Universe (referenziert in Run) | `universe_name = "(deleted)"`, alles funktioniert weiter |

## Akzeptanzkriterien

1. **Backend:** `GET /api/v1/runs` und `GET /api/v1/runs/{id}` liefern `universe_name` im JSON-Response.
2. **Backend-Tests:** Alle bestehenden Run-Router-Tests grün + neue Tests für `universe_name` + Fallback.
3. **Frontend `/rankings`:** Run-Liste rendert die letzten 10 Runs in absteigender Datums-Reihenfolge.
4. **Frontend Checkbox-FIFO:** Maximal 2 Runs gleichzeitig auswählbar; 3. Klick entfernt den ältesten.
5. **Frontend Compare-Button:** Disabled bei <2 ausgewählt, enabled bei genau 2.
6. **Frontend `/rankings/compare`:** Lädt 2 Runs parallel, zeigt Banner + Tabelle mit allen Common-Stocks.
7. **Frontend Δ-Visuals:** Grüner ↑ bei B-besser, roter ↓ bei A-besser, grauer · bei Gleichstand.
8. **Cross-Universe:** Banner zeigt 3 Counts, Tabelle nur Schnittmenge.
9. **Tests:** Alle neuen Vitest-Suites grün, E2E-Spec grün.
10. **Pre-Push CI-Mirror:** `ruff check`, `ruff format --check`, `mypy backend`, `pytest backend/tests`, `npm run lint`, `npm run typecheck`, `npm test` — alle grün.

## Risiken & Mitigation

- **Risiko:** Universe-Join in `list_runs()` macht N+1 Queries für `limit=50`.
  **Mitigation:** Für Demo (limit=10) irrelevant. Falls Profile zeigt, dass es weh tut: einmaliger `IN`-Query für alle universe_ids und Dict-Lookup. Nicht im Initial-Scope.

- **Risiko:** Compare-Page lädt 4 API-Calls parallel — bei langsamem Backend lange Wartezeit.
  **Mitigation:** `useQueries` + Suspense + Skeleton-Loader. Akzeptabel für Demo.

- **Risiko:** E2E ist flaky weil Run-Erstellung asynchron.
  **Mitigation:** Polling-Helper mit Timeout (max 30s) in `beforeAll`. Falls instabil: E2E auf Same-Universe-Vergleich reduzieren mit gemockter zweiter Run.

## Integration

Nach Implementation auf `feat/run-history`:
1. PR gegen `main` (für Code-Review, optional je nach Zeit)
2. Lokaler Merge in `demo/all-features` für integriertes Demo-Testing
