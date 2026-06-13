# Spec: Ranking-UI — Run-Runner + Detail-Page + E2E

**Status: Draft**
**Datum: 2026-05-17**
**Autor: Sheyla Sampietro / Claude Code**
**Bezieht sich auf**: `docs/specs/2026-04-21-prisma-v2-design.md` §7 (Frontend), `docs/specs/2026-05-09-ranking-service-multi-model.md` (Backend-API)

---

## Übersicht

Die Seite `/rankings` ist aktuell ein "Kommt bald"-Platzhalter (`frontend/app/rankings/page.tsx`, 14 Zeilen). Das ist riskant für die Demo, weil "Ranking" das Kernprodukt benennt. Diese Spec schließt die Lücke mit einer minimalen, demo-tauglichen UI:

1. **`/rankings`** — Form mit Universe-Dropdown + "Run starten"-Button.
2. **`/rankings/[runId]`** — Detail-Page mit Ergebnis-Tabelle (9 Spalten: Rank, Ticker, Avg, Sweet-Spot, + 5 Modell-Ranks).
3. **Vitest Unit-Tests** für Form und Tabelle.
4. **Playwright E2E-Suite** mit 3 Tests (Smoke, Universe-Flow, Ranking-Flow), in CI integriert.

**Hintergrund:** Codex-Review vom 2026-05-17 identifizierte fünf Lücken für die Abgabe. Diese Spec schließt zwei davon (Punkt #1 E2E, Punkt #5 Ranking-UI). Die übrigen drei (Release-Workflow, CD-Workflow, README-Tabelle) bleiben Folge-PRs.

**Out of Scope** (bewusst weggelassen — YAGNI):

- Custom-Weight-Editor (Backend nutzt Equal-Weight als Default; Editor wäre Demo-Nice-To-Have, aber +3h Validation-Code).
- Run-History-Liste (Backend hat keinen `GET /api/v1/runs`-Endpoint; Erweiterung wäre eigene Spec).
- Memo-Drilldown pro Ticker (Narrative-Engine ist separate Domäne, eigener PR).
- Real-Time-Progress / Cancel-Button (Backend hat keine Events-API und kein Cancel-Endpoint).
- Charts/Visualisierungen über die Tabelle hinaus.
- API-Key-Authentifizierung im Frontend (Backend ist opt-in; Dev und Demo laufen ohne `TOOL_API_KEY`).

---

## Architektur

Pattern-konsistent mit `/universes` und `/universes/new` (beide `'use client'`, `apiFetch`, `useQuery`/`useMutation`). Keine Server Actions, keine Backend-Änderungen.

```
frontend/
  app/rankings/
    page.tsx                          (ersetzt Platzhalter — Form-Wrapper)
    rankings-form.tsx                 (NEU — Universe-Select + Submit)
    [runId]/
      page.tsx                        (NEU — Detail mit Run + Rankings)
      rankings-table.tsx              (NEU — 9-Spalten-Tabelle)
    __tests__/
      rankings-form.test.tsx          (NEU — Vitest)
      rankings-table.test.tsx         (NEU — Vitest)
  lib/api/
    runs.ts                           (NEU — createRun/getRun/getRankings)
  e2e/                                (NEU — Playwright)
    rankings.spec.ts                  (NEU — 3 E2E-Tests)
  playwright.config.ts                (NEU)
  package.json                        (modifiziert — @playwright/test, e2e Script)

.github/workflows/
  ci.yml                              (modifiziert — neuer Job frontend-e2e)
```

---

## API-Layer (`frontend/lib/api/runs.ts`)

Dünner Wrapper um `apiFetch`, analog zu `lib/api/universes.ts`. Verwendet `snake_case` für Request/Response-Felder (Backend-Konvention).

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

**Hinweise:**
- Kein `weight_config` im `createRun`-Body — Backend nutzt Equal-Weight als Default.
- `RankingRunStatus`-Union matched die Backend-Enum (`backend/domain/entities/ranking_run.py`).
- Timeout: `createRun` setzt `AbortController` mit 120s, weil Browser-`fetch` keinen default-Timeout hat und ein Run je nach Universe-Größe 30–60s dauern kann.

---

## Page 1: `/rankings` (Form)

### Layout

```
┌────────────────────────────────────────────┐
│ Ranking starten                            │
│ Wähle ein Universum und starte einen Run.  │
├────────────────────────────────────────────┤
│ ┌── Card ──────────────────────────────┐   │
│ │ Universe                              │   │
│ │ [▼ Tech-Big-5                      ]  │   │
│ │                                       │   │
│ │ [ Run starten           ]             │   │
│ └───────────────────────────────────────┘   │
└────────────────────────────────────────────┘
```

### Komponenten

- **`page.tsx`** — Server-Component-Wrapper, importiert `RankingsForm`. Header + Card-Hülle, analog `/universes/page.tsx`.
- **`rankings-form.tsx`** (`'use client'`) — kapselt Form-State und Submit.

### State & Verhalten

| State | Behandlung |
|---|---|
| Universes laden | `useQuery(['universes'], listUniverses)` — wiederverwendet existing API |
| Universe gewählt | lokaler `useState<string \| null>(null)` |
| Submit | `useMutation({ mutationFn: createRun })` |
| isPending | Button: Spinner + "Run läuft (~30-60s)…", Select disabled |
| Success | `router.push(\`/rankings/\${data.id}\`)` |
| Error | Banner über Form mit `ApiError.message`, Form re-enabled |

### Accessibility

- Select-Label sichtbar (kein `placeholder`-only).
- Button hat `aria-busy` während Pending.
- Error-Banner mit `role="alert"`.

---

## Page 2: `/rankings/[runId]` (Detail)

### Layout

```
┌────────────────────────────────────────────────────────────────┐
│ Ranking-Ergebnis                                               │
│ ← Neuer Run                                                    │
├────────────────────────────────────────────────────────────────┤
│ ┌── Meta-Card ─────────────────────────────────────────────┐   │
│ │ Universe: Tech-Big-5   [✓ Completed]   2026-05-17 14:32  │   │
│ └──────────────────────────────────────────────────────────┘   │
│                                                                │
│ ┌── Tabelle ───────────────────────────────────────────────┐   │
│ │ # │ Ticker │ Avg │ ★ │ Quality │ Div │ Trend │ Val │ Alpha │
│ │ 1 │ AAPL   │ 2.1 │ ★ │  1      │ 3   │  2    │ 2   │  1    │
│ │ 2 │ MSFT   │ 2.4 │   │  2      │ 1   │  4    │ 1   │  3    │
│ │ ...                                                        │
│ └──────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### Komponenten

- **`page.tsx`** (`'use client'`) — extrahiert `runId` aus URL-Params, orchestriert Queries, rendert Layout.
- **`rankings-table.tsx`** — pure Tabellen-Komponente, akzeptiert `items: RankingItem[]`, rendert via `components/ui/table.tsx`.

### Daten-Flow

```
mount
  ├─ useQuery(['run', runId], () => getRun(runId))
  └─ useQuery(['rankings', runId], () => getRankings(runId), { enabled: run?.status === 'completed' })
       ↓
  if both loading → <TableSkeleton />
  if run.status === 'completed' && rankings → <RankingsTable items={rankings} universeName={...} />
  if run.status === 'running'     → Info-Banner + setInterval refetch (5s)
  if run.status === 'failed'      → Error-Card "Run fehlgeschlagen"
  if 404                          → notFound()
```

**Universe-Name auflösen:** `run.universe_id` → `getUniverse(id)` via existing API, gepaarter Query. Falls fehlend, zeigt die Meta-Card nur die UUID (Fallback).

### Tabelle: Spalten und Rendering

| # | Spalte | Quelle | Rendering |
|---|---|---|---|
| 1 | Rank | `total_rank` | Zahl, `null` → "—" |
| 2 | Ticker | `ticker` | Monospace |
| 3 | Avg | `weighted_avg` | 2 Dezimalen, `null` → "—" |
| 4 | Sweet-Spot | `is_sweet_spot` | Grünes Badge "★" wenn `true`, sonst leer |
| 5 | Quality | `per_model_ranks.quality_classic` | Zahl oder "—" |
| 6 | Diversification | `per_model_ranks.diversification` | Zahl oder "—" |
| 7 | Trend | `per_model_ranks.trend_momentum` | Zahl oder "—" |
| 8 | Value | `per_model_ranks.value_alpha_potential` | Zahl oder "—" |
| 9 | Alpha | `per_model_ranks.alpha` | Zahl oder "—" |

Modell-Spalten-Reihenfolge ist **fix konstant** (kein dynamisches Iterieren über Object-Keys), damit Spalten-Reihenfolge bei verschiedenen Runs stabil bleibt.

---

## Error- & Loading-States — Vollständige Tabelle

| Wo | Trigger | UI |
|---|---|---|
| `/rankings` | Universes laden | Skeleton im Select-Bereich |
| `/rankings` | `listUniverses` failt | rote `XCircle` + Message (Pattern aus `universes/page.tsx`) |
| `/rankings` | Submit Pending | Button-Spinner + "Run läuft (~30-60s)…", Form disabled |
| `/rankings` | `createRun` 4xx/5xx | Banner über Form mit `ApiError.message`, Form re-enabled |
| `/rankings` | `createRun` Timeout (>120s) | Banner: "Run dauerte zu lange. Prüfe Backend-Logs." |
| `/rankings/[runId]` | Initial-Load | Tabellen-Skeleton (3 Zeilen `animate-pulse`) |
| `/rankings/[runId]` | `getRun` 404 | Next.js `notFound()` |
| `/rankings/[runId]` | `run.status === 'failed'` | Error-Card statt Tabelle |
| `/rankings/[runId]` | `run.status === 'running'` | Info-Banner + Refetch-Polling alle 5s (max 24 Versuche = 2min) |
| `/rankings/[runId]` | `getRankings` leer (`[]`) | Empty-State: "Keine Ergebnisse" |

---

## Tests

### Vitest Unit-Tests

**`__tests__/rankings-form.test.tsx`** (~4 Tests):
1. Rendert Universe-Optionen aus mock `listUniverses`.
2. Button disabled solange kein Universe gewählt.
3. Submit ruft `createRun` mit korrekter `universeId` auf und triggered `router.push('/rankings/<id>')`.
4. API-Error zeigt Error-Banner und re-enabled die Form.

**`__tests__/rankings-table.test.tsx`** (~4 Tests):
1. Rendert N Zeilen für N Items.
2. Sweet-Spot-Badge nur wenn `is_sweet_spot=true`.
3. `null`-Werte zeigen "—".
4. Per-Model-Spalten-Reihenfolge ist konstant (quality_classic, diversification, trend_momentum, value_alpha_potential, alpha).

**Mocks:** `vi.mock('@/lib/api/runs')`, `vi.mock('@/lib/api/universes')`, `vi.mock('next/navigation')` für `useRouter`.

### Playwright E2E

**Setup:**
- Devdep: `@playwright/test@^1.48`.
- `frontend/playwright.config.ts` mit `webServer`-Konfig: startet `next start` auf Port 3000 (Build-Output muss vorher generiert sein via `npm run build`).
- `frontend/e2e/`-Verzeichnis für Specs.
- Neue Scripts in `package.json`: `"e2e": "playwright test"`, `"e2e:install": "playwright install --with-deps chromium"`.

**`e2e/rankings.spec.ts`** — 3 Tests:

1. **Smoke** — `/` lädt, Health-Status-Badge sichtbar (testet App-Boot + Backend-Verbindung).
2. **Universe-Flow** — `/universes` → "Neues Universum" → Name + Region + 2 Tickers ausfüllen → Submit → Eintrag in Liste sichtbar. Test räumt im `afterAll` via Backend-API auf (oder akzeptiert Drift in lokalem Test-DB-State).
3. **Ranking-Flow** — Test erzeugt Test-Universe via API-Setup im `beforeAll`. Dann: `/rankings` → Universe-Option wählen → "Run starten" → Wait für Redirect auf `/rankings/[runId]` (Timeout 90s) → Tabelle mit ≥1 Datenzeile sichtbar → Sweet-Spot-Badge in min. 0 Zeilen vorhanden (kann 0 sein, je nach Daten).

**Test-Isolation:** Jeder Test legt seine Test-Universe via API-Setup an (kein Cross-Test-State-Sharing). Naming-Konvention: `e2e-test-{timestamp}` für Cleanup-Erkennbarkeit.

### CI-Integration

Neuer Job in `.github/workflows/ci.yml`:

```yaml
frontend-e2e:
  name: Frontend E2E (Playwright)
  runs-on: ubuntu-latest
  needs: [frontend-build]                # nur wenn Build grün
  services:
    postgres:
      image: postgres:16
      env:
        POSTGRES_PASSWORD: postgres
        POSTGRES_DB: prisma_test
      ports: ['5432:5432']
      options: --health-cmd pg_isready --health-interval 10s
  steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - name: Install uv + Backend deps
      run: |
        pip install uv
        uv sync
    - name: Run Alembic migrations
      env:
        DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/prisma_test
      run: uv run alembic upgrade head
    - name: Start Backend (background)
      env:
        DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/prisma_test
      run: uv run uvicorn backend.interfaces.rest.main:app --host 0.0.0.0 --port 8000 &
    - name: Wait for Backend
      run: |
        for i in {1..30}; do curl -sf http://localhost:8000/health && break || sleep 2; done
    - name: Set up Node
      uses: actions/setup-node@v4
      with:
        node-version: "20"
        cache: "npm"
        cache-dependency-path: frontend/package-lock.json
    - name: Install frontend deps
      working-directory: frontend
      run: npm ci
    - name: Install Playwright browsers
      working-directory: frontend
      run: npx playwright install --with-deps chromium
    - name: Build frontend
      working-directory: frontend
      env:
        NEXT_PUBLIC_API_URL: http://localhost:8000
      run: npm run build
    - name: Run Playwright tests
      working-directory: frontend
      env:
        NEXT_PUBLIC_API_URL: http://localhost:8000
      run: npm run e2e
    - name: Upload Playwright report on failure
      if: failure()
      uses: actions/upload-artifact@v4
      with:
        name: playwright-report
        path: frontend/playwright-report
        retention-days: 7
```

**Hinweise:**
- Der exakte Backend-Entry-Point (`backend.interfaces.rest.main:app`) ist während Implementation zu verifizieren.
- Backend nutzt **StubFundamentalsProvider** und **StubMarketDataProvider** in CI (keine yfinance/finnhub-Calls) — sonst sind die Tests flaky und brauchen API-Keys.
- Stub-Provider werden via Settings/ENV gesteuert (zu verifizieren im Implementation-Plan).

---

## Verifikation & Done-Definition

- [ ] `cd frontend && npm ci && npm test && npm run build` grün (lokal + CI)
- [ ] `cd frontend && npm run e2e` grün (lokal mit laufendem Backend)
- [ ] CI-Job `frontend-e2e` grün auf PR
- [ ] Manueller Demo-Flow im Browser:
  - `/rankings` zeigt Universe-Dropdown
  - "Run starten" → Redirect auf `/rankings/[runId]`
  - Tabelle zeigt 9 Spalten mit echten Daten
- [ ] Vitest-Coverage für neue Komponenten ≥ 80%
- [ ] Spec-Status auf "Final" gesetzt nach Merge

---

## Risiken & Annahmen

| Punkt | Risiko | Mitigation |
|---|---|---|
| Backend-Run-Dauer in CI | yfinance/finnhub-Rate-Limits machen E2E flaky | Stub-Provider in CI (ENV-gesteuert) |
| Backend-Entry-Point-Pfad | Aktueller Pfad `backend.interfaces.rest.main:app` ist Annahme | Im Implementation-Plan vor CI-Setup verifizieren |
| Stub-Daten in CI | Stub liefert deterministische Fundamentals/Prices, sodass Sweet-Spot-Logik testbar ist | Annahme: Stubs sind bereits "demo-tauglich" — wenn nicht, im Implementation-Plan ergänzen |
| Playwright in macOS-Dev | Browser-Install dauert ~2min beim ersten Mal | Einmaliger Cost, dokumentiert in `frontend/README.md` |
| Universe ohne Tickers | Backend lehnt Universe-Creation mit leeren Tickers ab | Frontend prüft nicht zusätzlich (Backend-Guard reicht) |

---

## Open Questions

Alle während Brainstorming + Self-Review aufgelöst:

1. **Backend-Entry-Point:** `backend.interfaces.rest.main:app` verifiziert in `backend/interfaces/rest/main.py:5`.
2. **Stub-Provider-Aktivierung:** Backend nutzt aktuell **immer** Stubs (hardcoded in `backend/interfaces/rest/dependencies.py:132-137`). Keine ENV-Variable nötig — CI braucht nur Backend starten. *(Side-Note, nicht Teil dieser Spec: Production hat ebenfalls keine echten Data-Provider — separates Issue.)*
3. **Universe-Name auf Detail-Page:** `getUniverse(run.universe_id)` parallel via `useQuery`, kein Backend-Change.
