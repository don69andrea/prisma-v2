# Spec: Rankings Detail-Page — Sortierung, Filter, CSV-Export

**Status: Draft**
**Datum: 2026-05-17**
**Issue: #21**
**Autor: Nicolas Lardinois / Claude Code**
**Bezieht sich auf:** `docs/specs/2026-05-17-ranking-ui-design.md` (Basis-Implementierung)

---

## Übersicht

Die bestehende `/rankings/[runId]`-Detail-Page (implementiert in PR #119) zeigt eine statische Tabelle. Issue #21 erweitert sie um drei interaktive Features:

1. **Sortierung** — click-to-sort auf jeder numerischen Spalte
2. **Ticker-Filter** — Texteingabe filtert die Tabellenzeilen nach Ticker-Symbol
3. **CSV-Export** — Button löst client-seitigen Download von `rankings.csv` aus

**Out of Scope:**
- Server-seitige Sortierung (Backend hat keinen Sort-Parameter)
- Pagination (Universes haben typisch ≤50 Titel — client-side reicht)
- Memo-Drilldown pro Ticker
- Spalten ein-/ausblenden

---

## Technischer Approach

Alle drei Features werden client-seitig in `rankings-table.tsx` implementiert:

- `'use client'` Directive (nötig für React Hooks)
- `useState` für Sort-State (Spalte + Richtung) und Filter-Text
- `useMemo` für die abgeleitete gefilterte + sortierte Liste
- Keine neuen npm-Packages (lucide-react und shadcn/ui Input/Button bereits vorhanden)

---

## Sortierung

**Sortierbare Spalten (numerisch):**
- `#` → `total_rank` (integer)
- `Avg` → `weighted_avg` (float)
- `Quality` → `per_model_ranks.quality_classic`
- `Diversification` → `per_model_ranks.diversification`
- `Trend` → `per_model_ranks.trend_momentum`
- `Value` → `per_model_ranks.value_alpha_potential`
- `Alpha` → `per_model_ranks.alpha`

**Nicht sortierbar:** `Ticker` (Text), `Sweet-Spot` (Boolean).

**Default:** Sortierung nach `total_rank` aufsteigend (entspricht der Backend-Reihenfolge).

**Null-Handling:** `null`-Werte landen bei aufsteigender Sortierung immer am Ende (`Infinity`), bei absteigender am Anfang (da `-Infinity` < alle reellen Zahlen, zieht man stattdessen `Infinity` vor und kehrt es nicht um — d.h. Nulls bleiben konsistent am Ende unabhängig von der Richtung).

**UI:**
- Sortierbare Header-Zellen: `cursor-pointer`, `select-none`
- Icon: `ArrowUpDown` (inactive), `ArrowUp` (asc), `ArrowDown` (desc) aus lucide-react
- `aria-sort="ascending"|"descending"|"none"` auf dem `<th>`-Element (Accessibility)
- Click auf aktive Spalte wechselt Richtung; Click auf neue Spalte setzt auf `asc`

---

## Ticker-Filter

- `<Input placeholder="Ticker suchen…" />` über der Tabelle
- Case-insensitive: `ticker.toLowerCase().includes(filter.toLowerCase())`
- Keine Debounce nötig (lokale Daten, kein API-Call)
- Empty-State bei keinen Treffern: "Keine Ergebnisse"

---

## CSV-Export

**Format:**
```
Ticker,Total Rank,Weighted Avg,Sweet Spot,Quality,Diversification,Trend,Value,Alpha
AAPL,1,2.10,true,1,3,2,2,1
MSFT,2,2.40,false,2,,4,1,3
```

- Komma-getrennt (kein Quote nötig — Ticker-Symbole enthalten keine Kommas)
- `null`-Werte → leeres Feld
- `weighted_avg` mit 2 Dezimalen
- Button-Label: "CSV" mit `Download`-Icon
- Download-Filename: `rankings.csv`

**Implementation:**
```typescript
const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'rankings.csv';
a.click();
URL.revokeObjectURL(url);
```

---

## UI-Layout

```
┌── Toolbar ─────────────────────────────────────────────────────────┐
│ [🔍 Ticker suchen…                    ]  [ ↓ CSV ]                 │
└───────────────────────────────────────────────────────────────────┘
┌── Tabelle ─────────────────────────────────────────────────────────┐
│ #↑ │ Ticker │ Avg↕ │ ★ │ Quality↕ │ Div↕ │ Trend↕ │ Val↕ │ Alpha↕ │
│  1 │ AAPL   │ 2.10 │ ★ │    1     │   3  │    2   │   2  │    1   │
│ ...                                                                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## Tests

### Vitest (neue Tests in `rankings-table.test.tsx`)

1. `klick auf #-Header wechselt aria-sort zu ascending` → zweiter Klick → `descending`
2. `filter 'AAPL' zeigt nur AAPL-Zeile` → MSFT nicht im DOM
3. `CSV-Export setzt korrekten Download-Filename` (mock `createObjectURL`)

### Playwright E2E (neuer Test 4 in `rankings.spec.ts`)

Ablauf:
1. Test-Universe erstellen, Run starten → auf `/rankings/[runId]` warten
2. Tabelle hat ≥1 Zeile
3. "Avg"-Header klicken → `aria-sort="ascending"` verifizieren
4. Nochmal klicken → `aria-sort="descending"`
5. CSV-Button klicken → `download`-Event mit Filename `rankings.csv`

---

## Definition of Done

- [ ] `rankings-table.tsx` hat Sortierung, Filter und CSV-Export
- [ ] Alle bestehenden Unit-Tests weiterhin grün
- [ ] 3 neue Unit-Tests grün
- [ ] E2E-Test 4 grün (mit laufendem Backend)
- [ ] TypeScript-Check sauber (`npx tsc --noEmit`)
- [ ] Manuelle Verifikation: CSV in Excel öffnen, Sortierung und Filter funktionieren
