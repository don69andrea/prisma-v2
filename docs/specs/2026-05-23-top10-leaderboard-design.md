# Top-10-Leaderboard auf Rankings-Detail-Page

**Status:** Draft
**Datum:** 2026-05-23
**Scope:** Frontend (Items 3 + 4 aus Frontend-Improvement-Backlog, kombiniert)
**Estimated effort:** 3–4 h

## Ziel

Bewertende erfassen die Top 10 einer Run-Auswertung in einer Sekunde — bevor sie überhaupt zur 9-Spalten-Tabelle scrollen. Kombiniert Item 3 (Top-10-Karten) und Item 4 (Bar-Chart Top-10) in einer kohärenten "Top-10-Spotlight"-Sektion: Karten oben für Ticker-Identifikation, Bars darunter für Score-Vergleich.

## Nicht-Ziele

- Kein Drilldown in einzelne Modell-Werte auf den Karten (das ist die Factsheet-Page).
- Keine Konfigurierbarkeit der Anzahl (fest Top 10, bei kleineren Universen entsprechend weniger).
- Keine Animationen beim ersten Render (Demo-Stabilität > Polish).
- Kein Vergleich mit historischen Runs.

## Architektur

### Neue Dateien

1. **`frontend/lib/top10.ts`** — reine Daten-Transform-Funktion, keine React-Imports.
   - Export `selectTopN(items: RankingItem[], n: number = 10): RankingItem[]` — sortiert nach `total_rank` aufsteigend (Nulls zuletzt), nimmt die ersten `n`.
   - Reine Funktion, deterministisch, test-first geschrieben.

2. **`frontend/components/rankings/TopTenLeaderboard.tsx`** — Container.
   - Props: `{ items: RankingItem[]; runId: string }`.
   - Bei `items.length === 0`: rendert `null` (kein "Leere Top 10"-Box).
   - Sonst: rendert Section-Header (`Top {min(10, items.length)}`), `<TopTenCards>`, `<TopTenBars>`.
   - Datentransform: `const topN = selectTopN(items, 10)` einmalig, an Children weitergegeben.

3. **`frontend/components/rankings/TopTenCards.tsx`** — Kartengrid.
   - Props: `{ items: RankingItem[]; runId: string }` (erwartet bereits sortierte/limitierte Liste).
   - Grid: `grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5`.
   - Pro Item: `<Link href={ROUTES.factsheet(runId, item.ticker)}>` ist Outermost Element.
   - Karten-Inhalt:
     - Top-Reihe: Rank-Badge links (`#{item.total_rank}`, `text-xs font-medium text-muted-foreground`), Sweet-Spot-Stern rechts (`<Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400">` aus `lucide-react`).
     - Ticker: `text-xl font-mono font-bold`, eigene Zeile.
   - Card-Padding: `p-3`.
   - Hover: `hover:bg-muted/50 transition-colors`.
   - Sweet-Spot-Karten zusätzlich: `border-amber-400 bg-amber-50/60 dark:border-amber-500 dark:bg-amber-950/30`.

4. **`frontend/components/rankings/TopTenBars.tsx`** — Recharts-BarChart.
   - Props: `{ items: RankingItem[]; runId: string }`.
   - Recharts: `<ResponsiveContainer width="100%" height={300}><BarChart layout="vertical" data={chartData}>…</BarChart></ResponsiveContainer>`.
   - `chartData`: `items.map(i => ({ ticker, weighted_avg, is_sweet_spot }))`.
   - X-Achse: numeric, `weighted_avg`-Domain `[min, max]`, mit `reversed` damit kleinere Werte (= bessere Ranks) längere Bars produzieren. Keine sichtbaren Ticks/Grid.
   - Y-Achse: `type="category"` mit `dataKey="ticker"`, `font-mono`, Tick-Labels in Amber-500 wenn das Item `is_sweet_spot=true` ist (via Custom-Tick).
   - Bar: `<Bar dataKey="weighted_avg">{chartData.map((entry, i) => <Cell key={i} fill={entry.is_sweet_spot ? '#f59e0b' : 'hsl(var(--primary))'} />)}</Bar>`.
   - Wert-Label am Bar-Ende: Custom `LabelList` zeigt `weighted_avg.toFixed(2)` plus Sweet-Spot-Stern bei Bedarf.
   - Custom-Tooltip-Komponente: `bg-popover text-popover-foreground border rounded p-2 text-sm`, Inhalt: `{ticker} — Avg {value.toFixed(2)}{is_sweet_spot ? ' • Sweet-Spot' : ''}`.
   - Klick-Verhalten: `onClick` Handler auf `<BarChart>` extrahiert den Ticker aus `state.activePayload?.[0]?.payload?.ticker`, fällt nicht — falls Recharts-Klick fummelig ist, Fallback `cursor-pointer` auf Y-Tick-Labels + Klick dort.
   - Bar-Höhe: ~24 px, `barCategoryGap={6}`.

### Angepasste Datei

1. **`frontend/app/rankings/[runId]/page.tsx`** — `<TopTenLeaderboard items={rankingsQuery.data} runId={params.runId} />` zwischen Metadata-Card (Zeile 96) und `<RankingsTable>` (Zeile 117) einfügen, **nur wenn** `isCompleted && rankingsQuery.data`.

### Komponenten-Tree

```
RankingDetailPage
└── TopTenLeaderboard (items, runId)
    ├── selectTopN (items, 10) → topN
    ├── <h2>Top {n}</h2>
    ├── TopTenCards (items=topN, runId)
    │   └── Link[10] → Card
    └── TopTenBars (items=topN, runId)
        └── ResponsiveContainer → BarChart → Bars[10] (mit Cells)
```

## Visuelles Design

**Sweet-Spot-Akzent:**
- Farbe: Amber-400 / Amber-500 (`#fbbf24` / `#f59e0b`)
- Stern-Icon: `lucide-react` `<Star>` mit `fill-amber-400 text-amber-400`
- Karten: Border + dezenter Background-Tint
- Bars: Bar-Farbe in Amber, Y-Tick-Label in Amber, Stern hinter Wert

**Layout-Reihenfolge auf der Page:**
```
[Backlink]
[Titel]
[Run-Metadata-Card]
[TopTenLeaderboard]   ← NEU
  ├── Section-Header
  ├── 10 Karten (2/3/5 Cols responsive)
  └── BarChart (height=300px)
[RankingsTable]
```

## Daten-Transform

`selectTopN` sortiert nach `total_rank` aufsteigend mit folgender Logik:

```typescript
function selectTopN(items: RankingItem[], n = 10): RankingItem[] {
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

Konsistent mit der Sort-Logik in `rankings-table.tsx::getSortValue`.

## Testing

### TDD-pflichtig (Datentransform)

**`frontend/lib/__tests__/top10.test.ts`** (neu):

- `selectTopN([], 10)` → `[]`
- `selectTopN(itemsWithSortedRanks, 10)` → die ersten 10 in Rank-Reihenfolge
- `selectTopN(itemsWithUnsortedRanks, 10)` → sortiert korrekt
- Items mit `total_rank=null` landen am Ende
- `n` kann kleiner sein als items.length → genau n zurück
- `n` größer als items.length → alle items zurück
- Function ist non-mutating (original items-Array unverändert)

### Komponenten-Tests (post-implementation)

**`frontend/components/rankings/__tests__/TopTenLeaderboard.test.tsx`** (neu):

- rendert `null` bei `items=[]`
- Section-Header zeigt `Top 10` bei items.length ≥ 10
- Section-Header zeigt `Top 5` bei items.length=5
- Children-Komponenten (`TopTenCards`, `TopTenBars`) sind im DOM

**`frontend/components/rankings/__tests__/TopTenCards.test.tsx`** (neu):

- rendert eine Karte pro Item (max 10)
- jede Karte hat das `#{rank}` Badge und Ticker
- Sweet-Spot-Karten haben den Stern (`screen.getAllByLabelText('Sweet-Spot')` oder über Icon-aria)
- Sweet-Spot-Karten haben die Amber-Klasse (`expect(card).toHaveClass('border-amber-400')`)
- Karte ist `<a href="/rankings/{runId}/stock/{ticker}">` (Factsheet-Route)

**`frontend/components/rankings/__tests__/TopTenBars.test.tsx`** (neu):

- rendert eine Recharts-`BarChart` mit 10 Bars (10 `rect.recharts-bar-rectangle` Elemente, abhängig von Recharts-DOM)
- Sweet-Spot-Bars haben `fill="#f59e0b"` (via DOM-Inspection)
- Andere Bars haben Primary-Fill
- Klick auf eine Bar/Tick → `router.push` mit korrektem Pfad (mock `useRouter`)

> **Hinweis zu Recharts in jsdom:** Recharts rendert SVG. jsdom unterstützt SVG-Querying, aber Recharts braucht manchmal explizite Dimensionen, weil `ResponsiveContainer` im Test-Renderer 0×0 ist. Lösung: Test wraps `<TopTenBars>` in einem `<div style={{ width: 600, height: 300 }}>`, oder mock `ResponsiveContainer` mit einer Fixed-Size-Variante.

### E2E (Playwright, optional)

Bestehenden Rankings-Detail-E2E-Test erweitern:
- `Top-10-Sektion ist sichtbar`
- `Klick auf erste Karte navigiert zur Factsheet-Page`
- `Bars sind sichtbar mit korrekter Anzahl`

## A11y

- Karten sind `<a>`-Elemente → tabbar, screenreader-konform
- Sweet-Spot-Stern hat `aria-label="Sweet-Spot"` oder ist visuell ergänzt mit `<span class="sr-only">Sweet-Spot</span>`
- Bars: Recharts-Default-A11y ist begrenzt. Y-Tick-Labels sollten Ticker als Text enthalten — bei Bedarf zusätzlich `<title>`-Elemente in SVG für Screenreader.
- Farbe ist nicht der einzige Indikator — Sweet-Spot hat Farbe **und** Stern (WCAG 1.4.1).

## Edge Cases

| Fall | Verhalten |
|---|---|
| `items.length === 0` | `TopTenLeaderboard` rendert `null` (keine Box) |
| `items.length === 1` | "Top 1" — eine Karte, eine Bar |
| `items.length === 5` | "Top 5" — 5 Karten, 5 Bars |
| `items.length > 10` | "Top 10" — exakt 10 |
| Alle `total_rank === null` | Items werden in Original-Reihenfolge gezeigt (Sort-Stabilität) |
| `weighted_avg === null` für Top-Item | Bar bekommt Wert `0` (Recharts erwartet number); im Tooltip wird `—` angezeigt |

## Risiken & offene Punkte

- **Recharts-Klick:** Klick-Handler auf der `<Bar>` selbst ist in Recharts manchmal unzuverlässig. Wenn das in der Implementation Probleme macht, Fallback: `cursor-pointer` auf den Y-Tick-Labels rendern + Klick dort handhaben. Beide Pfade führen zur Factsheet, das ist redundant aber robust.
- **jsdom + ResponsiveContainer:** Tests müssen ggf. Dimensionen mocken (siehe Hinweis oben).
- **Layout-Verschiebung:** Die neue Sektion fügt ~400–500 px zum Page-Layout hinzu. Bewertende, die direkt zur Tabelle wollen, müssen scrollen. Falls das nervt: später Collapse-Button — aber YAGNI für jetzt.
- **Dark-Mode:** Das Projekt hat Tailwind dark variants, aber selten genutzt. Sweet-Spot-Amber im Dark-Mode prüfen, ggf. anpassen.
- **`weighted_avg` reversed axis:** Recharts braucht `domain={[max, min]}` oder `reversed` auf der X-Achse. Welche Variante in Recharts v2.12 sauber funktioniert, in der Implementation klären.

## Verifikation (vor "done")

- [ ] `npm run lint` grün
- [ ] `npx tsc --noEmit` grün
- [ ] `npm test` grün (alle neuen + bestehenden Tests)
- [ ] Manuell: `npm run dev`, Rankings-Detail-Page öffnen, Top-10-Sektion erscheint zwischen Metadata und Tabelle
- [ ] Manuell: Sweet-Spot-Karten haben Amber-Border, Sweet-Spot-Bars sind Amber statt Primary
- [ ] Manuell: Klick auf Karte navigiert zur Factsheet
- [ ] Manuell: Klick auf Bar oder Y-Label navigiert zur Factsheet
- [ ] Manuell: Mobile (DevTools-Viewport) — Karten 2 Cols, Bars responsiv
- [ ] CI-Mirror Pre-Push: mypy + ruff check + ruff format --check + pytest unit (Backend unverändert, sollte grün bleiben)

## Referenzen

- Memory: `project-frontend-improvement-backlog` (Items 3 + 4)
- Memory: `project-capstone-deadline`
- Existierende Recharts-Nutzung: `frontend/components/factsheet/PriceChart.tsx`
- Konsistenter Grid-Layout: `frontend/components/factsheet/ModelRankCards.tsx`
- Sort-Logik-Vorbild: `frontend/app/rankings/[runId]/rankings-table.tsx::getSortValue`
- Factsheet-Route: `frontend/lib/routes.ts::ROUTES.factsheet`
- Recharts Docs: https://recharts.org/en-US/api/BarChart
