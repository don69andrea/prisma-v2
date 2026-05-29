# Dashboard-Stats — Design

**Datum:** 2026-05-28
**Issue:** Frontend-Backlog Priorität 5
**Status:** Draft — ready for review

## Ziel

Das aktuelle Dashboard (`/dashboard`, PR #124) zeigt nur eine Runs-Tabelle. Für die Capstone-Demo ist die Startseite, die Bewerter zuerst sehen, zu spartanisch. Vier Stats-Karten oben sollen sofort vermitteln, dass PRISMA echte Daten verwaltet:

1. **Letzter Run** — Datum + Status-Badge, Link zur Run-Detail-Page
2. **# Universen** — Anzahl angelegter Universen, Link zu `/universes`
3. **# Stocks im System** — Anzahl bekannter Stocks total
4. **Top-Pick** — Ticker des Rang-1-Stocks aus dem jüngsten `completed` Run, Sweet-Spot-Indikator wenn anwendbar, Link zum Factsheet

Die existierende Runs-Tabelle bleibt unter den Karten als Detail-Liste.

## Nicht-Ziele

- Neuer Backend-Stats-Endpoint — Frontend aggregiert aus bestehenden APIs
- Charts / Visualisierungen — nur numerische Karten in v1
- Real-time Updates — Tanstack-Default-Refetch reicht
- Auth-Gating — Dashboard bleibt unverändert öffentlich
- Mobile-spezifische Karten-Layouts — responsives Grid genügt

## Architektur

Reine Frontend-Änderung in `frontend/app/dashboard/dashboard-client.tsx` plus neue `StatsCards`-Komponente. Daten kommen aus 4 parallelen Tanstack-Queries:

```
DashboardClient
├── existing: runs (listRuns) — bereits da, wird auch für StatsCards genutzt
├── existing: universesData (listUniverses) — bereits da, wird auch für StatsCards genutzt
├── NEU: stocksTotal (listStocks limit=1) — nur `total` aus der List-Response
└── NEU: topPick (getRankings(latestCompletedRunId)) — conditional, nur wenn ein completed Run existiert
```

Für `topPick`: Aus der existierenden `runs`-Liste den jüngsten Run mit `status === 'completed'` finden. Wenn keiner: Top-Pick-Karte zeigt "—".

## Komponenten-Struktur

**`frontend/components/dashboard/StatsCards.tsx`** (neu):

Props:
```tsx
interface Props {
  latestRun: RunResponse | null;        // jüngster Run irgendeines Status, null wenn keine Runs
  universeCount: number;
  stockCount: number;
  topPick: { ticker: string; isSweetSpot: boolean; runId: string } | null;
}
```

Layout: 4-Karten-Grid via `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`. Jede Karte ist ein shadcn `<Card>` mit:
- Icon links oben (lucide-react: `Clock`, `Layers`, `TrendingUp`, `Star`)
- Label (klein, muted) oben rechts
- Value (groß, bold) zentriert
- Sub-Info / Link unten

**`DashboardClient.tsx`** (modify):

Vor der existierenden Tabelle einen `<StatsCards>`-Block einfügen. Loading-State: 4 Skeleton-Karten. Error-State pro Query separat — wenn `stocksTotal` failt, zeigt die Stock-Karte "—" statt komplette Page zu blocken.

## Daten-Fluss

```
DashboardClient (existing)
  ├─ useQuery(['runs']) → existing
  ├─ useQuery(['universes']) → existing
  ├─ NEW: useQuery(['stocks-total']) → listStocks(1, 0).total
  │
  ├─ derived: latestRun = runs?.[0] ?? null  // listRuns ist already sorted DESC by created_at
  ├─ derived: latestCompletedRunId = runs?.find(r => r.status === 'completed')?.id
  │
  ├─ NEW: useQuery(['rankings', latestCompletedRunId])
  │      enabled: latestCompletedRunId !== undefined
  │      → derived topPick: rankings?.find(r => r.total_rank === 1)
  │
  ├─ <StatsCards ... />  (NEW)
  └─ <RunsTable ... />   (existing)
```

## Edge Cases

- **Keine Runs vorhanden:** Latest-Run-Karte zeigt "—" + Link "Neuen Run erstellen". Top-Pick-Karte zeigt "—". Universen + Stocks zeigen ihre Counts.
- **Keine completed Runs (nur pending/running):** Top-Pick zeigt "—". Latest-Run zeigt die jüngste mit Status-Badge.
- **listStocks API failt:** Stocks-Karte zeigt "—". Andere Karten unaffected.
- **getRankings für latest completed failt:** Top-Pick zeigt "—".
- **Top-Pick existiert aber kein Sweet-Spot:** Karte zeigt Ticker ohne Sweet-Spot-Indikator.
- **Mobile (<sm):** Karten stacken untereinander (1-Spalte).

## Testing

**Unit-Tests (Vitest + Testing-Library):**

- `StatsCards.test.tsx`:
  - Rendert alle 4 Karten mit gegebenen Props
  - "—" statt Run-Datum wenn `latestRun === null`
  - "—" statt Ticker wenn `topPick === null`
  - Sweet-Spot-Indikator nur wenn `topPick.isSweetSpot === true`
  - Counts werden korrekt formatiert (z.B. `0`, `1`, `42`)

- `DashboardClient.test.tsx` (existiert vermutlich) erweitern:
  - StatsCards wird gerendert
  - Loading-Skeleton für StatsCards wenn Queries pending
  - Latest-completed-Run wird korrekt aus der runs-Liste abgeleitet (Test mit gemixten Status)

**Keine Backend-Tests** — kein Backend-Touch.

**Manual-Verification (vor PR):**

- Dashboard öffnen mit ≥1 completed Run → Top-Pick erscheint mit Ticker
- Karte "Letzter Run" zeigt Datum + Status-Badge
- Klick auf Top-Pick-Karte navigiert zum Factsheet
- Mobile-Viewport: Karten stacken sauber

## Build Sequence (für writing-plans)

1. Frontend: `StatsCards.tsx` neue Komponente + Tests
2. Frontend: `DashboardClient.tsx` erweitern (Imports, Queries, Derivations, Render-Block)
3. Frontend: Bestehender Dashboard-Test (`dashboard-client.test.tsx` falls existent) anpassen
4. Manual Test + PR

## Abgrenzung zu existierenden Specs

- **Visual-Identity-Polish-Spec (2026-05-23):** Karten verwenden bestehende `Card`-Komponente + die dort definierten Spektrum-Tokens (z.B. Pink für Sweet-Spot-Indikator). Keine neuen Design-Tokens.
- **Memo-Drilldown-Spec (2026-05-28):** Top-Pick-Link führt zur Factsheet-Page, die jetzt `MemoPanel` mit echtem Memo zeigt. Synergie: Bewerter klickt Top-Pick → sieht direkt das LLM-Memo der besten Stock.
