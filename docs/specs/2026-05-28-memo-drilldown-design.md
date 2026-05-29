# Memo-Drilldown — Design

**Datum:** 2026-05-28
**Issue:** Frontend-Backlog Priorität 1 (Killer-Feature)
**Status:** Draft — ready for review

## Ziel

Die wochenlange Narrative-Engine-Arbeit (LLM-Memos pro Stock) im Frontend sichtbar machen. Aktuell ist `MemoPanel.tsx` ein Stub mit "KI-Memo noch nicht verfügbar — Layer-1-Integration folgt." — die Backend-API ist seit PR #70 (Multi-Memo Batch) komplett, aber kein User sieht je ein Memo.

Nach diesem Feature kann ein Bewerter in der Rankings-Tabelle auf eine Stock-Zeile klicken und sieht in einem Slide-In-Sheet:

- One-Liner (Hero)
- Sweet-Spot-Erklärung (wenn anwendbar)
- Stärken & Risiken (Pro/Contra-Aufteilung)
- Widersprüche zwischen Modellen
- Ranking-Interpretation (Prosa)
- Confidence + Modell-Version

## Nicht-Ziele

- Multi-Memo-Batch-Trigger im UI ("Top-20 generieren"-Button) — kann in Folge-PR
- DE/EN Language-Toggle — v1 ist DE only (alle bestehenden Memos sind DE)
- Markdown-Rendering im `ranking_interpretation`-Block — Plain-Text bleibt
- Memo-Edit / Re-generate-with-modified-prompt
- Run-History-Vergleich von Memos über Zeit

## Architektur

Drei Layer, klar getrennt:

### Layer 1 — Backend (minimal touch)

**`backend/interfaces/rest/schemas/runs.py`:**

`RankingItem` Response-Schema um `stock_id: UUID | None` erweitern:

```python
class RankingItem(BaseModel):
    stock_id: UUID | None = None  # NEU — Optional für Backwards-Compat mit alten Runs
    ticker: str
    total_rank: int | None
    weighted_avg: float | None
    is_sweet_spot: bool
    per_model_ranks: dict[str, int | None]
```

`Optional` weil Rankings als JSONB-Snapshot in `ranking_runs.results` persistiert sind — alte Runs in der DB haben `stock_id` nicht im JSONB-Blob. Neue Runs (post-Merge) liefern es. Frontend muss `null` graceful behandeln (Sheet öffnet nicht / "Memo nicht verfügbar"-Tooltip).

**Service (`backend/application/services/ranking_run_service.py:87-101`):**

Beim Bauen des `results`-JSONB nach dem Run-Compute: für jeden `ticker` die `stock_id` via existing `StockService.get_by_ticker(ticker)` (oder direkter Repo-Call) auflösen und im dict einsetzen. Für eine typische Demo (5-30 Stocks) ist sequenzieller Lookup akzeptabel; Bulk-Lookup als Optimierung in Folge-PR.

**Memo-Endpoints bleiben unverändert** (`POST /memos/generate`, `GET /memos/{stock_id}/{run_id}` sind ausreichend).

### Layer 2 — Frontend API-Client

**`frontend/lib/api/memos.ts`:**

Vollständiges Memo-Schema (analog Backend `MemoResponse`):

```ts
// Spiegelt backend/domain/entities/research_memo.py:ContradictionItem
export interface ContradictionItem {
  model_a: string;       // z.B. "Quality"
  model_b: string;       // z.B. "Value"
  description: string;   // max 200 Zeichen — was ist der Widerspruch?
}

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

export function getMemo(stockId: string, runId: string): Promise<Memo | null>;
export function generateMemo(stockId: string, runId: string, language?: 'de' | 'en'): Promise<Memo>;
```

- `getMemo`: 404 → `null` (kein throw)
- `generateMemo`: behält POST `/api/v1/memos/generate`, default `language: 'de'`

**`ContradictionItem` Schema verifizieren:** Backend-Entity (`backend/domain/entities/research_memo.py`) hat das Feld — Field-Namen aus dem Backend übernehmen (kann von obigem Vorschlag abweichen).

### Layer 3 — Frontend Components

**`frontend/components/factsheet/MemoContent.tsx`** (neu, gemeinsame Render-Komponente):

```
┌────────────────────────────────────────────┐
│ "{one_liner}"                  [Confidence:│  ← Hero
│                                      high] │
├────────────────────────────────────────────┤
│ ★ Sweet-Spot                               │  ← nur wenn sweet_spot=true
│ {sweet_spot_explanation}                   │     Pink-Akzent (passt zu
│                                            │     Spektrum-Branding)
├────────────────────────────────────────────┤
│ ✓ Stärken          │  ⚠ Risiken            │  ← 2-Spalten
│ • strength 1       │  • risk 1             │
│ • strength 2       │  • risk 2             │
├────────────────────────────────────────────┤
│ ⚡ Widersprüche                            │  ← nur wenn contradictions.length > 0
│ {model_a} ↔ {model_b}                      │
│ {description}                              │
├────────────────────────────────────────────┤
│ Interpretation                             │
│ {ranking_interpretation}                   │
├────────────────────────────────────────────┤
│ Modell: {model_version}    {created_at}    │  ← Footer-Meta
└────────────────────────────────────────────┘
```

- Reine Präsentations-Komponente, props: `{ memo: Memo }`
- Keine Daten-Fetching-Logik
- Wird in `MemoSheet` UND `MemoPanel` verwendet

**`frontend/components/factsheet/MemoSheet.tsx`** (neu):

- Wrappt shadcn `Sheet` (slide-in von rechts, `side="right"`, `w-[640px]` auf Desktop, full-width auf Mobile)
- Props: `{ stockId: string; runId: string; ticker: string; open: boolean; onOpenChange: (v: boolean) => void }`
- Sheet-Header: Ticker + Stock-Name (wenn verfügbar)
- States:
  - **Loading** (initial fetch): Spinner mit "Memo wird geladen…"
  - **Empty** (404): EmptyState mit FileText-Icon + "Noch kein Memo für diesen Stock" + Button "Memo generieren"
  - **Generating** (nach Klick auf Generate-Button): Spinner mit "Memo wird generiert (5-15s)…" + abort-fähig? Nein, v1 = blocking
  - **Loaded** (200 + `is_error=false`): `<MemoContent memo={memo} />`
  - **Error-Memo** (200 + `is_error=true`): Warning-Card mit "Vorheriger Generate-Versuch fehlgeschlagen" + `error_message` + Button "Erneut generieren"
  - **Network-Error**: Error-Card + Retry-Button
- Footer: Link "Vollständiges Factsheet →" → `/rankings/{runId}/stock/{ticker}`

**`frontend/lib/hooks/useMemo.ts`** (neu — Custom Hook):

- Wrappt Tanstack Query (`useQuery` + `useMutation`)
- Query-Key: `['memo', stockId, runId]`
- `queryFn`: `getMemo(stockId, runId)` — gibt `Memo | null` zurück
- Mutation: `generateMemo` → `invalidateQueries` auf den Query-Key bei Success
- Returns: `{ memo, isLoading, isError, generate, isGenerating }`
- Caching: Tanstack-Default (5min staleTime ok, kein refetch on focus)

**Naming-Hinweis:** Da `useMemo` mit Reacts gleichnamigem Hook kollidiert, heißt der Hook **`useStockMemo`** in der Implementierung.

**`frontend/app/rankings/[runId]/rankings-table.tsx`** (modify):

- Row wird klickbar via `onClick` Handler auf `<TableRow>`
- Visual: `cursor-pointer` + `hover:bg-muted/50`
- State im Parent oder Local: `selectedStockId: {stockId, ticker} | null`
- Sheet wird mit `open={selectedStockId !== null}` gerendert
- Ticker-Link erhält `onClick={(e) => e.stopPropagation()}` — Klick auf Ticker führt weiterhin zur Factsheet-Page, Klick auf den Rest der Zeile öffnet Sheet
- Keyboard-A11y: `tabIndex={0}` + `onKeyDown` für Enter/Space

**`frontend/components/factsheet/MemoPanel.tsx`** (replace stub):

- Props erweitern: `{ stockId: string; runId: string }`
- Stub-Card ersetzen durch:
  ```tsx
  const { memo, isLoading, generate, isGenerating } = useStockMemo(stockId, runId);
  if (isLoading) return <MemoSkeleton />;
  if (!memo) return <MemoEmpty onGenerate={generate} isGenerating={isGenerating} />;
  if (memo.is_error) return <MemoErrorCard memo={memo} onRegenerate={generate} isGenerating={isGenerating} />;
  return <MemoContent memo={memo} />;
  ```
- Dieselbe `is_error`-Logik wie in `MemoSheet` — Sheet und Panel teilen sich `MemoContent`, `MemoEmpty`, `MemoErrorCard` als Sub-Komponenten
- Factsheet-Page (`frontend/app/rankings/[runId]/stock/[ticker]/factsheet-view.tsx`) muss `stockId` an `MemoPanel` reichen — kommt aus dem Stock-Lookup (vorhanden) oder aus dem `RankingItem` (jetzt mit `stock_id`)

## Data Flow

```
RankingsTable row click
  ↓ onClick({ stock_id, ticker })
MemoSheet (open=true)
  ↓ useStockMemo(stockId, runId)
GET /api/v1/memos/{stock_id}/{run_id}
  ├─ 200 + is_error=false → MemoContent
  ├─ 200 + is_error=true  → ErrorMemoCard (+ Regenerate-Button)
  ├─ 404                  → MemoEmpty (+ Generate-Button)
  │                         ↓ click
  │                       POST /api/v1/memos/generate { stock_id, model_run_id, language: 'de' }
  │                         ↓ pending (5-15s spinner)
  │                       invalidate ['memo', stockId, runId] → MemoContent
  └─ network error        → RetryCard
```

## Edge Cases & Decisions

- **Sprache:** Hardcoded `'de'` in v1. Wenn EN benötigt, eigener Folge-PR.
- **`is_error=true`:** Wird als separater State angezeigt, NICHT stillschweigend wie 404 behandelt — User muss wissen, dass es bereits einen Versuch gab.
- **`stock_id` für Factsheet-Page:** Die Factsheet-Page ruft heute Stock-Daten via `getFactsheet(ticker)` ab. Die Response-Schema `StockFactsheet` enthält bereits `id` — also bereits verfügbar, keine extra Query nötig.
- **Concurrency:** Wenn User mehrfach klickt während Generate läuft: Tanstack `useMutation` ist standardmäßig parallel-safe — wir nutzen `isGenerating` als Disable-Guard auf dem Button.
- **Sheet-Schließen während Generate:** Mutation läuft im Hintergrund fort, Cache wird invalidiert. Beim nächsten Öffnen ist Memo da. Kein Abort nötig.
- **Mobile:** Sheet wird auf kleinen Viewports zu Full-Screen (shadcn-Default mit responsive `w-` Klassen).
- **Sweet-Spot-Pink:** Die Spektrum-Pink (`--ring-pink-accent` o.ä. aus Visual-Identity-Polish-Spec) wird für die Sweet-Spot-Card verwendet — konsistent mit `TopTenBars`/`TopTenCards`/`ModelRankCards`.

## Testing

**Unit-Tests (Jest + Testing-Library):**

- `MemoContent.test.tsx`:
  - Rendert `one_liner`, alle `key_strengths`, alle `key_risks`
  - Sweet-Spot-Card nur wenn `sweet_spot=true`
  - Contradictions-Section nur wenn Array nicht leer
  - Confidence-Badge zeigt richtige Farbe pro Level
- `MemoSheet.test.tsx`:
  - Empty-State rendert wenn `getMemo` → null
  - Generate-Button-Click triggert mutation
  - Loading-Spinner während `isLoading`
  - Error-Memo-State zeigt `error_message` + Regenerate-Button
- `useStockMemo.test.ts`:
  - 404 → returns `null`, kein throw
  - Generate-Success invalidiert Query
- `rankings-table.test.tsx` (ergänzen):
  - Row-Click setzt selected state + öffnet Sheet
  - Ticker-Link funktioniert weiterhin als Page-Link (stopPropagation)
  - Keyboard-A11y: Enter auf Row öffnet Sheet

**Backend-Tests:**

- `test_runs_endpoint.py` (ergänzen):
  - `stock_id` ist in der `RankingItem` Response enthalten und entspricht dem Stock in der DB

**Manual Verification (vor Demo):**

- Echtes Memo für mindestens 1 Top-10-Stock vorab via `POST /memos/generate` oder Batch erzeugen
- Sheet öffnen, alle Sections sichtbar
- Stock ohne Memo → Generate-Button → Memo erscheint
- `is_error=true` Memo (manuell DB-modifizieren oder via Stub-Trigger) → Error-State korrekt

## Open Questions (kein Blocker)

- **Confidence-Badge-Farben:** Vorschlag `low=grau`, `medium=blau`, `high=grün` — soll mit Visual-Identity-Tokens abgestimmt werden, falls dort Status-Farben definiert sind
- **Generate-Loading-Skeleton:** Detailliertes Skeleton statt nur Spinner würde Demo-Feel verbessern, aber v1 reicht ein Spinner

## Abgrenzung zu existierenden Specs

- **Single-Memo-Spec (`2026-05-04-narrative-engine-single-memo.md`):** definiert Backend-API + Memo-Entity. Diese Spec setzt darauf auf, ändert Backend nur minimal (`RankingItem` Schema).
- **Multi-Memo-Batch-Spec (`2026-05-08`):** Batch-Endpoint wird in v1 NICHT genutzt — kann Folge-PR sein, wenn "Top-N pre-generate"-Button gewünscht.
- **Visual-Identity-Polish-Spec (`2026-05-23`):** Diese Spec verwendet die dort definierten Spektrum-Tokens (Pink für Sweet-Spot, etc.) — keine neuen Design-Tokens.

## Build Sequence (für writing-plans)

1. Backend: `RankingItem.stock_id` (Optional) ergänzen + Test
2. Backend: `stock_id` in `ranking_run_service.py` JSONB-Build ergänzen + Test
3. Frontend: shadcn `Sheet` installieren (`npx shadcn@latest add sheet`)
4. Frontend API: `memos.ts` erweitern (vollständiges Memo-Schema, `getMemo`)
5. Frontend Hook: `useStockMemo` + Test
6. Frontend Component: `MemoContent` (Präsentation) + Test
7. Frontend Components: `MemoEmpty` + `MemoErrorCard` (Sub-States) + Test
8. Frontend Component: `MemoSheet` (Wrapper + State-Machine) + Test
9. Frontend Integration: `RankingsTable` Row-Click + Sheet-State + Test-Update
10. Frontend Integration: `MemoPanel` Stub ersetzen + `factsheet-view.tsx` stock_id durchreichen + Test
11. Manual Test: Demo-Run mit ≥1 vorgeneriertem Memo
