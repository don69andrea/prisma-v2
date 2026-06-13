# Rankings-Tooltips & Sweet-Spot-Explainer

**Status:** Draft
**Datum:** 2026-05-23
**Scope:** Frontend (Item 2 aus Frontend-Improvement-Backlog)
**Estimated effort:** 1–1.5 h

## Ziel

Bewertende der Demo verstehen ohne Vorerklärung, was die 5 Modell-Spalten (Quality, Diversification, Trend, Value, Alpha) bedeuten und was die Sweet-Spot-Auszeichnung qualifiziert. Reibung "was heißt das?" wird beseitigt, ohne den Tabellen-Layout zu überfrachten.

## Nicht-Ziele

- Keine vollständige Modell-Dokumentation im Frontend (dafür existieren die Specs).
- Keine interaktiven Drilldowns auf einzelne Kennzahlen pro Modell — das ist Sache der Stock-Factsheet.
- Keine A/B-Test-Infrastruktur für Tooltip-Texte.

## Architektur

### Neue Dateien

1. **`frontend/lib/model-info.ts`** — Daten-Modul, keine React-Imports.
   - Exportiert `MODEL_INFO: Record<ModelKey, { label: string; description: string }>` für alle 5 Modelle.
   - Exportiert `SWEET_SPOT_DEFINITION: string`.
   - Exportiert Helper `getSweetSpotModels(perModelRanks, totalStocks): ModelKey[]` — gibt die Modelle zurück, in denen der Ticker im Top-25 % liegt. Schwelle: `rank <= Math.ceil(totalStocks * 0.25)`. Das entspricht der Backend-Logik aus `test_top25_in_3_of_5_models_is_sweet_spot`.

2. **`frontend/components/ui/popover.tsx`** — shadcn-Popover, hinzugefügt via `npx shadcn-ui add popover` (zieht `@radix-ui/react-popover` als Dep).

3. **`frontend/components/InfoPopover.tsx`** — generischer Wrapper.
   - Props: `{ ariaLabel: string; children: React.ReactNode }`.
   - Rendert klickbaren `ⓘ`-Icon-Button als `PopoverTrigger`, der `children` als Popover-Content zeigt.
   - Icon: `lucide-react` `<Info className="h-3.5 w-3.5 opacity-60 hover:opacity-100" />`.
   - Tap-Target: `min-h-[24px] min-w-[24px]` Padding um das Icon.
   - Button hat `onClick={(e) => e.stopPropagation()}`, damit Klick aufs Icon nicht den Sort-Handler im Tabellen-Header triggert.

4. **`frontend/components/ModelInfoIcon.tsx`** — dünner Spezial-Wrapper.
   - Props: `{ modelKey: ModelKey }`.
   - Liest aus `MODEL_INFO[modelKey]` und rendert `InfoPopover` mit dem Description-Text.

### Angepasste Dateien

1. **`frontend/app/rankings/[runId]/rankings-table.tsx`**
   - Jeder Modell-Header bekommt `<ModelInfoIcon modelKey={col.key} />` rechts neben dem Label, vor dem Sort-Pfeil.
   - Layout: `Quality ⓘ ↕`.
   - Sweet-Spot-Header (aktuell `<TableHead>Sweet-Spot</TableHead>`) bekommt `<InfoPopover>` mit der generischen `SWEET_SPOT_DEFINITION` als Content.
   - Sweet-Spot-Badge in der Zeile wird zum Popover-Trigger: zeigt ticker-spezifischen Text `"{ticker} ist Top-25 % in {ModelA, ModelB, ModelC} ({n}/5 Modellen)."`. `n` und Modell-Liste kommen aus `getSweetSpotModels(item.per_model_ranks, items.length)`.

2. **`frontend/components/factsheet/ModelRankCards.tsx`**
   - `CardTitle` ergänzt um `<ModelInfoIcon modelKey={key} />` neben dem Label.

## Inhalt der Tooltip-Texte

| Key | Label | Tooltip-Text |
|---|---|---|
| `quality_classic` | Quality | "Fundamental gesund & günstig bewertet — Kombiniert 8 klassische Kennzahlen (Marge, Verschuldung, ROE, KGV …) zu einem Score." |
| `alpha` | Alpha | "Konsistent besser als der Index — Outperformance vs. Benchmark über mehrere Zeithorizonte, mit Sharpe gewichtet." |
| `trend_momentum` | Trend | "Aktuelles Momentum — Welche Aktien zuletzt stärker als der Markt liefen, jüngere Daten zählen mehr." |
| `value_alpha_potential` | Value | "Mean-Reversion-Kandidaten — Wie weit unter dem eigenen historischen Outperformance-Hoch der Titel steht." |
| `diversification` | Diversification | "Risiko-Diversifikatoren — Niedrige Eigenvolatilität und niedrige Korrelation zu anderen Titeln im Universum." |

**Sweet-Spot — Header (generisch):**

> "Sweet-Spot-Aktien liegen im Top-25 % in mindestens 3 von 5 Modellen — also auf mehreren unabhängigen Achsen überzeugend, nicht nur in einer Disziplin."

**Sweet-Spot — Badge (pro Ticker):**

> "{ticker} ist Top-25 % in {ModelLabels} ({n}/5 Modellen)."

Beispiel: `"AAPL ist Top-25 % in Quality, Trend, Diversification (3/5 Modellen)."`

## Interaktion & A11y

- **Klick** auf das `ⓘ`-Icon öffnet das Popover, erneuter Klick / Außenklick / Escape schließt es — out-of-the-box durch Radix Popover. (Radix `Popover` ist klick-basiert; das `HoverCard`-Primitive wäre die Hover-Variante, brauchen wir hier aber nicht — sichtbares `ⓘ`-Icon ist universeller als Hover-and-pray.)
- **Touch:** identisches Verhalten wie Desktop — Klick aufs sichtbare Icon. Kein Long-Press-Pattern nötig.
- **Keyboard:** Tab fokussiert das Icon, Enter/Space öffnet, Escape schließt.
- **ARIA-Labels:**
  - Modell-Info-Icon: `aria-label="Info zu {label}"`
  - Sweet-Spot-Header-Icon: `aria-label="Sweet-Spot-Definition"`
  - Sweet-Spot-Badge: `aria-label="Sweet-Spot-Begründung für {ticker}"`
- **Klick-Konflikt mit Sort:** `stopPropagation` auf dem Icon-Button (im Header sitzt ein `onClick={sort}` auf dem `<TableHead>`).

## Testing

### TDD-pflichtig (Datenmodul + kritische Logik)

**`frontend/lib/__tests__/model-info.test.ts`** (neu):

- Alle 5 Keys haben gültige `label` + `description`.
- `getSweetSpotModels`:
  - 0/5 (alle Ranks > Quartil-Grenze) → `[]`
  - 3/5 mit gemischten Ranks → korrekte Liste von 3 Modellen
  - 5/5 (alle Top-25 %) → alle 5 Modelle
  - Edge Case `totalStocks = 4`, `rank = 1` → Top-25 %
  - Edge Case `totalStocks = 20`, `rank = 5` → Top-25 % (Schwelle: `ceil(20 * 0.25) = 5`)
  - Null-Rank wird ignoriert (nicht als Top-25 % gezählt)

### Komponenten-Tests (RTL + Vitest, post-implementation)

**`frontend/components/__tests__/InfoPopover.test.tsx`** (neu):

- Rendert Icon-Trigger, Popover initial geschlossen.
- Klick auf Icon öffnet Popover, Content sichtbar.
- Escape schließt Popover.
- `stopPropagation`: Klick auf Icon triggert keinen Parent-`onClick`-Handler (Mock).

**`frontend/app/rankings/__tests__/rankings-table.test.tsx`** (erweitern):

- Klick auf Info-Icon im Quality-Header sortiert nicht (Sort-Reihenfolge bleibt unverändert).
- Klick auf Sweet-Spot-Badge eines Tickers öffnet Popover mit ticker-spezifischer Modell-Liste.

**`frontend/components/factsheet/__tests__/ModelRankCards.test.tsx`** (erweitern):

- Jede der 5 Karten hat ein Info-Icon.
- Klick auf das Icon der Quality-Karte zeigt den Quality-Tooltip-Text.

### E2E (Playwright, optional)

Bestehenden Rankings-Detail-E2E-Test erweitern:

- Klick auf Info-Icon im Quality-Header → Tooltip-Inhalt enthält "8 klassische Kennzahlen".
- Klick auf Sweet-Spot-Badge des ersten Sweet-Spot-Tickers → Popover enthält "Top-25 %" und mindestens einen Modell-Namen.

## Risiken & offene Punkte

- **Layout-Drift:** `ⓘ` neben Sort-Pfeil macht Header in 5 Spalten leicht breiter. Falls Layout bricht, kleinere Icon-Variante (`h-3 w-3`) oder horizontaler Scroll.
- **Mobile-Spacing:** 24×24 Tap-Target kann auf sehr kleinen Screens (<360 px) eng wirken. Kein Demo-Stopper, aber bei Bedarf nachjustieren.
- **shadcn-Popover-Dep:** `npx shadcn-ui add popover` modifiziert ggf. `components.json`/`tsconfig.json`. Vor Implementation prüfen, was die CLI tatsächlich anfasst.

## Verifikation (vor "done")

Aus `Verifikation vor Abschluss`:

- [ ] `npm run lint` grün
- [ ] `npm run typecheck` grün
- [ ] `npm test` grün (alle neuen + bestehenden Tests)
- [ ] Bei Frontend-Änderungen: `npm run dev`, Rankings-Page öffnen, alle 6 Tooltips manuell aufrufen
- [ ] CI-Mirror-Pre-Push: mypy + ruff check + ruff format --check + pytest (Backend unverändert, sollte grün bleiben)

## Referenzen

- Memory: `project-frontend-improvement-backlog` (Item 2)
- Memory: `project-deadline` (Deadline 2026-05-31)
- Backend-Sweet-Spot-Definition: `backend/tests/unit/application/test_ranking_aggregator.py::test_top25_in_3_of_5_models_is_sweet_spot`
- Modell-Specs: `docs/specs/2026-04-28-quant-mvp-models.md`
- shadcn Popover: https://ui.shadcn.com/docs/components/popover
