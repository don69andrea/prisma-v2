# Admin Dashboard — Full Backend UI

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `/admin` section into a complete backend operations dashboard covering all major subsystems: Stocks & Universes, Ranking Runs, Research Memos, Alerts, Audit Trail, and Backtests.

**Architecture:** Pure frontend extension — no new backend endpoints needed. All pages call existing REST APIs via the existing `lib/api/` wrappers (extended where functions are missing). Cards + Charts design matching the existing dashboard (Glassmorphism, Recharts).

**Branch:** `feat/admin-dashboard` (from `main`)

## Global Constraints

- Next.js 14 App Router, TypeScript strict, Tailwind CSS
- All pages are `'use client'` components using `@tanstack/react-query` for data fetching
- Admin-only: pages live under `/admin` which is already protected by `AdminLayout` (role check → redirect)
- Recharts for all charts: `BarChart`, `PieChart`, `LineChart` — match existing chart style
- No new backend endpoints — use existing `/api/v1/*` REST APIs
- `npx tsc --noEmit` must pass before each commit
- `npx eslint` must pass before each commit
- One commit per task

---

## File Map

**Modified files:**
- `frontend/app/admin/layout.tsx` — add 5 new nav links
- `frontend/app/admin/page.tsx` — improve cost overview with Recharts BarChart (by_model) + PieChart (by_feature)
- `frontend/lib/api/universes.ts` — add `updateUniverseTickers(id, tickers)` (POST /{id}/sync)
- `frontend/lib/api/memos.ts` — add `listMemosByRun(runId)` (GET /memos/{stock_id}/{run_id} looped per ticker)

**New files:**
- `frontend/lib/api/backtests.ts` — `runBacktest(body)`, `getBacktest(id)`
- `frontend/app/admin/stocks/page.tsx` — Stock list + Universe management
- `frontend/app/admin/runs/page.tsx` — Ranking runs list + trigger new run
- `frontend/app/admin/memos/page.tsx` — Generate memo + view memo by ticker+run
- `frontend/app/admin/alerts/page.tsx` — All alerts list + delete
- `frontend/app/admin/audit/page.tsx` — Decision audit trail by ticker (Recharts)
- `frontend/app/admin/backtests/page.tsx` — Run backtest form + results LineChart

---

### Task 1: Extend layout nav + improve cost page

**Files:**
- Modify: `frontend/app/admin/layout.tsx`
- Modify: `frontend/app/admin/page.tsx`

**Steps:**

- [ ] **1a: Update nav in layout.tsx**

  Add links for all new sections:

  ```tsx
  <nav className="flex flex-wrap gap-4 border-b border-border pb-4">
    <Link href="/admin" className="text-sm font-medium hover:text-primary">Übersicht</Link>
    <Link href="/admin/stocks" className="text-sm font-medium hover:text-primary">Stocks & Universen</Link>
    <Link href="/admin/runs" className="text-sm font-medium hover:text-primary">Ranking-Runs</Link>
    <Link href="/admin/memos" className="text-sm font-medium hover:text-primary">Memos</Link>
    <Link href="/admin/alerts" className="text-sm font-medium hover:text-primary">Alerts</Link>
    <Link href="/admin/audit" className="text-sm font-medium hover:text-primary">Audit</Link>
    <Link href="/admin/backtests" className="text-sm font-medium hover:text-primary">Backtests</Link>
    <Link href="/admin/users" className="text-sm font-medium hover:text-primary">User-Verwaltung</Link>
  </nav>
  ```

- [ ] **1b: Improve /admin cost page with Recharts**

  The existing `/admin/page.tsx` fetches `GET /api/v1/admin/costs` and shows raw data. Replace with:
  - KPI Cards row: Total Kosten, Anzahl Calls, Budget-Cap, Verbleibend
  - `BarChart` (Recharts): Kosten nach Modell (`by_model` array → `model` + `cost_usd`)
  - `PieChart` (Recharts): Kosten nach Feature (`by_feature` array → `feature` + `cost_usd`)
  - Table: letzte LLM-Calls (`last_calls`: created_at, model, feature, cost_usd)

  **Note on CostSummary shape** — the API returns:
  ```ts
  interface CostSummary {
    month: string;
    cap_usd: number;
    current_usd: number;
    remaining_usd: number;
    by_model: Array<{ model: string; calls: number; cost_usd: number }>;
    by_feature: Array<{ feature: string; calls: number; cost_usd: number }>;
    last_calls: Array<{ created_at: string; model: string; feature: string; cost_usd: number }>;
  }
  ```

- [ ] **1c: Commit**
  ```bash
  git add frontend/app/admin/layout.tsx frontend/app/admin/page.tsx
  git commit -m "feat(admin): extend nav + improve cost page with Recharts charts"
  ```

---

### Task 2: Stocks & Universes page

**Files:**
- Modify: `frontend/lib/api/universes.ts`
- New: `frontend/app/admin/stocks/page.tsx`

**Steps:**

- [ ] **2a: Add `updateUniverseTickers` to universes.ts**

  The backend has `POST /api/v1/universes/{universe_id}/sync` which takes a full ticker list and syncs:

  ```ts
  export interface UniverseSyncResponse {
    added: string[];
    removed: string[];
    unchanged: string[];
  }

  export async function updateUniverseTickers(
    universeId: string,
    tickers: string[],
  ): Promise<UniverseSyncResponse> {
    return apiFetch<UniverseSyncResponse>(`/api/v1/universes/${universeId}/sync`, {
      method: 'POST',
      body: JSON.stringify({ tickers }),
    });
  }
  ```

- [ ] **2b: Build /admin/stocks/page.tsx**

  Two-panel layout:
  - **Left panel — Stock-Liste:** Table with columns: Ticker, Name, Sektor, Land, Währung. Data from `listStocks(200)`. Search-Filter (client-side `filter()` on ticker/name). Card with total count KPI.
  - **Right panel — Universe-Verwaltung:** For each universe (from `listUniverses()`): show name, ticker count, expandable ticker list. Action: "Ticker hinzufügen" text input → calls `updateUniverseTickers(id, [...existing, newTicker])`. "Ticker entfernen" button per ticker → calls `updateUniverseTickers(id, remaining)`.

  Use `useMutation` from `@tanstack/react-query` for the sync action with `onSuccess` invalidating `['universes']`.

- [ ] **2c: Commit**
  ```bash
  git add frontend/lib/api/universes.ts frontend/app/admin/stocks/page.tsx
  git commit -m "feat(admin): stocks & universe management page"
  ```

---

### Task 3: Ranking Runs page

**Files:**
- New: `frontend/app/admin/runs/page.tsx`

**Steps:**

- [ ] **3a: Build /admin/runs/page.tsx**

  - **Top section — Neuer Run:** Form with universe selector (dropdown from `listUniverses()`). Button "Run starten" → calls `createRun(universeId)` → shows success toast / redirect to run detail.
  - **Runs-Liste:** Table with columns: ID (first 8 chars), Universe, Status (badge: grün=completed, gelb=running, grau=pending, rot=failed), Erstellt am. Data from `listRuns(50)`. Clicking a row expands to show rankings table (from `getRankings(runId)`): Rank, Ticker, Score, Sweet Spot.
  - KPI Cards: Anzahl Runs, Letzter Run (date), Completed vs. Failed count.

  Use `statusLabel()` from `runs.ts` for status text. Use `useQuery` for both list and rankings (lazy: only fetch rankings when row is expanded). Use `useMutation` for `createRun`.

- [ ] **3b: Commit**
  ```bash
  git add frontend/app/admin/runs/page.tsx
  git commit -m "feat(admin): ranking runs page with trigger + rankings detail"
  ```

---

### Task 4: Research Memos page

**Files:**
- New: `frontend/app/admin/memos/page.tsx`

**Steps:**

- [ ] **4a: Build /admin/memos/page.tsx**

  Two sections:
  - **Memo generieren:** Form with Ticker input (text), Run selector (dropdown from `listRuns(20)`), Language toggle (de/en). Button "Generieren" → calls `generateMemo(stockId, runId, language)`. Shows result memo card: one_liner, confidence badge, key_strengths list, key_risks list, contradictions. Uses `useMutation`.
  - **Memo abrufen:** Same inputs (Ticker + Run) → "Abrufen" button calls `getMemo(stockId, runId)`. Shows same card. 404 shows "Kein Memo vorhanden".

  **Note:** `generateMemo` needs `stock_id` (UUID), not ticker. Fetch `listStocks()` to resolve ticker → id lookup client-side.

- [ ] **4b: Commit**
  ```bash
  git add frontend/app/admin/memos/page.tsx
  git commit -m "feat(admin): research memos page — generate + retrieve"
  ```

---

### Task 5: Alerts page

**Files:**
- New: `frontend/app/admin/alerts/page.tsx`

**Steps:**

- [ ] **5a: Build /admin/alerts/page.tsx**

  - KPI Card: Total aktive Alerts, Total Alerts.
  - Table: Ticker, Typ (PRICE_CHANGE / SIGNAL_CHANGE), Schwellenwert, Kanal, Ziel, Aktiv (badge), Erstellt, Zuletzt ausgelöst. Data from `listAlerts()`.
  - Delete button per row → calls `deleteAlert(id)` → `useMutation` with `onSuccess` invalidating `['alerts']`. Confirm before delete (window.confirm or inline confirm state).
  - Filter: Aktiv/Alle toggle (client-side filter on `is_active`).

- [ ] **5b: Commit**
  ```bash
  git add frontend/app/admin/alerts/page.tsx
  git commit -m "feat(admin): alerts management page"
  ```

---

### Task 6: Audit Trail page

**Files:**
- New: `frontend/app/admin/audit/page.tsx`

**Steps:**

- [ ] **6a: Build /admin/audit/page.tsx**

  - **Decision Audit Trail:** Ticker-Suchfeld (text input). On submit: calls `getAuditTrail(ticker)`. Shows:
    - Recharts `BarChart`: weighted_score über Zeit (x=snapshot_date, y=weighted_score, color by signal BUY/HOLD/SELL)
    - Table: Datum, Signal (Badge), Score, Quant/ML/Makro Scores, 3a (checkmark), Erklärung (truncated, expandable)
  - **LLM-Call-Log:** Uses the existing `/api/v1/admin/costs?last=100` endpoint. Shows `last_calls` as a table: Zeitpunkt, Modell, Feature, Kosten (CHF). No separate endpoint needed.

  Data fetching: `getAuditTrail` via `useQuery` (enabled when ticker is set). Admin costs via separate `useQuery`.

- [ ] **6b: Commit**
  ```bash
  git add frontend/app/admin/audit/page.tsx
  git commit -m "feat(admin): audit trail page — decision log + LLM call log"
  ```

---

### Task 7: Backtests page

**Files:**
- New: `frontend/lib/api/backtests.ts`
- New: `frontend/app/admin/backtests/page.tsx`

**Steps:**

- [ ] **7a: Create backtests.ts API wrapper**

  ```ts
  import { apiFetch } from './client';

  export interface RunBacktestRequest {
    model_run_id: string;
    start_date: string;   // YYYY-MM-DD
    end_date: string;
    top_n?: number;
    benchmark_ticker?: string;
    mode?: 'quant_only' | 'quant_ml' | 'full';
  }

  export interface PortfolioMetrics {
    total_return: number;
    cagr: number;
    annual_vol: number;
    sharpe: number;
    max_drawdown: number;
  }

  export interface BacktestResultResponse {
    id: string;
    model_run_id: string;
    start_date: string;
    end_date: string;
    top_n: number;
    benchmark_ticker: string;
    mode: string;
    prisma_metrics: PortfolioMetrics;
    universe_metrics: PortfolioMetrics;
    benchmark_metrics: PortfolioMetrics;
    series: {
      dates: string[];
      prisma: number[];
      universe: number[];
      benchmark: number[];
    };
    created_at: string;
  }

  export async function runBacktest(body: RunBacktestRequest): Promise<BacktestResultResponse> {
    return apiFetch<BacktestResultResponse>('/api/v1/backtests', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  export async function getBacktest(id: string): Promise<BacktestResultResponse> {
    return apiFetch<BacktestResultResponse>(`/api/v1/backtests/${id}`);
  }
  ```

- [ ] **7b: Build /admin/backtests/page.tsx**

  - **Backtest-Formular:** 
    - Run-Selector: dropdown from `listRuns(50)` (only `completed` runs)
    - Start-/End-Datum: date inputs (default: 1 Jahr zurück bis heute)
    - Top-N: number input (default: 3)
    - Benchmark: text input (default: `^SSMI`)
    - Mode: select (quant_only / quant_ml / full)
    - Button "Backtest starten" → `useMutation` → shows result below
  - **Backtest-Ergebnis:**
    - KPI Cards: PRISMA Return, PRISMA Sharpe, Max Drawdown (vs. benchmark)
    - Recharts `LineChart`: Performance-Verlauf (x=dates, 3 lines: PRISMA / Universe / Benchmark), gestrichelte Benchmark-Linie
    - Metrics-Tabelle: Total Return / CAGR / Vol / Sharpe / Max DD für alle 3 Portfolios

- [ ] **7c: Commit**
  ```bash
  git add frontend/lib/api/backtests.ts frontend/app/admin/backtests/page.tsx
  git commit -m "feat(admin): backtests page — run form + LineChart results"
  ```

---

## Post-Implementation Checklist

- [ ] `cd frontend && npx tsc --noEmit` — kein Fehler
- [ ] `cd frontend && npx eslint app/admin lib/api/backtests.ts lib/api/universes.ts --max-warnings 0`
- [ ] PR erstellen: `gh pr create --base main --title "feat(admin): full backend operations dashboard"`
- [ ] CI grün abwarten
- [ ] Manuell testen:
  - [ ] `/admin` — Kostenübersicht mit Charts sichtbar
  - [ ] `/admin/stocks` — Aktien-Liste lädt, Universe-Verwaltung: Ticker hinzufügen/entfernen
  - [ ] `/admin/runs` — Run-Liste sichtbar, neuen Run triggern
  - [ ] `/admin/memos` — Memo generieren für existierenden Ticker + Run
  - [ ] `/admin/alerts` — Alert-Liste sichtbar, löschen funktioniert
  - [ ] `/admin/audit` — Audit Trail für "NESN" oder "AAPL" lädt, LLM-Log sichtbar
  - [ ] `/admin/backtests` — Formular ausfüllen, Backtest starten, LineChart erscheint
