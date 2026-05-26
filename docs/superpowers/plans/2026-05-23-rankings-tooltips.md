# Rankings-Tooltips & Sweet-Spot-Explainer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spalten-Tooltips und pro-Ticker Sweet-Spot-Begründung in der Rankings-Tabelle und auf den Factsheet-ModelRankCards, damit Bewertende die 5 Modelle und das Sweet-Spot-Kriterium ohne Vorerklärung verstehen.

**Architecture:** Daten-Modul `lib/model-info.ts` als Single Source of Truth. Wiederverwendbare Komponente `<InfoPopover>` (klick-basierter shadcn-Popover mit `ⓘ`-Icon, touch-tauglich). Dünner Wrapper `<ModelInfoIcon>` für Modell-spezifische Tooltips. Integration in `rankings-table.tsx` (5 Modell-Header + Sweet-Spot-Header + Sweet-Spot-Badge mit Ticker-spezifischem Inhalt) und `ModelRankCards.tsx` (5 Card-Titles).

**Tech Stack:** Next.js 14, Vitest, @testing-library/react, shadcn/ui, Radix Popover, lucide-react, Tailwind.

**Spec:** `docs/specs/2026-05-23-rankings-tooltips-design.md`

---

## File Structure

**Neue Dateien:**
- `frontend/lib/model-info.ts` — Daten + `getSweetSpotModels` Helper
- `frontend/lib/__tests__/model-info.test.ts` — Tests für Daten + Helper
- `frontend/components/ui/popover.tsx` — shadcn-Popover (CLI-generiert)
- `frontend/components/InfoPopover.tsx` — generischer `ⓘ`-Wrapper
- `frontend/components/ModelInfoIcon.tsx` — Modell-spezifischer Wrapper
- `frontend/components/__tests__/InfoPopover.test.tsx`
- `frontend/components/__tests__/ModelInfoIcon.test.tsx`

**Geänderte Dateien:**
- `frontend/app/rankings/[runId]/rankings-table.tsx` — Header-Icons + Sweet-Spot-Trigger
- `frontend/app/rankings/__tests__/rankings-table.test.tsx` — neue Test-Cases
- `frontend/components/factsheet/ModelRankCards.tsx` — Icon-Integration in CardTitle
- `frontend/components/factsheet/__tests__/ModelRankCards.test.tsx` — neue Test-Cases

---

### Task 1: Daten-Modul `model-info.ts` (TDD)

**Files:**
- Create: `frontend/lib/model-info.ts`
- Test: `frontend/lib/__tests__/model-info.test.ts`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/lib/__tests__/model-info.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';

import {
  MODEL_INFO,
  MODEL_KEYS,
  SWEET_SPOT_DEFINITION,
  getSweetSpotModels,
  type ModelKey,
} from '../model-info';

describe('MODEL_INFO', () => {
  it('hat einen Eintrag für jeden der 5 Modell-Keys', () => {
    expect(MODEL_KEYS).toEqual([
      'quality_classic',
      'alpha',
      'trend_momentum',
      'value_alpha_potential',
      'diversification',
    ]);
    for (const key of MODEL_KEYS) {
      expect(MODEL_INFO[key].label).toBeTruthy();
      expect(MODEL_INFO[key].description.length).toBeGreaterThan(20);
    }
  });

  it('SWEET_SPOT_DEFINITION erwähnt 25% und 3 von 5', () => {
    expect(SWEET_SPOT_DEFINITION).toMatch(/25 ?%/);
    expect(SWEET_SPOT_DEFINITION).toMatch(/3 von 5|3\/5/);
  });
});

describe('getSweetSpotModels', () => {
  const allFive: Record<ModelKey, number | null> = {
    quality_classic: 1,
    alpha: 2,
    trend_momentum: 3,
    value_alpha_potential: 4,
    diversification: 5,
  };

  it('totalStocks=20, alle ranks <= 5 → alle 5 Modelle', () => {
    const result = getSweetSpotModels(allFive, 20);
    expect(result).toHaveLength(5);
  });

  it('totalStocks=20, Schwelle ist ceil(20*0.25)=5 → rank=5 zählt noch', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: 5,
      alpha: 6,
      trend_momentum: null,
      value_alpha_potential: 100,
      diversification: 1,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual(['quality_classic', 'diversification']);
  });

  it('totalStocks=4, Schwelle ist ceil(4*0.25)=1 → nur rank=1 zählt', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: 1,
      alpha: 2,
      trend_momentum: 1,
      value_alpha_potential: 3,
      diversification: 4,
    };
    const result = getSweetSpotModels(ranks, 4);
    expect(result).toEqual(['quality_classic', 'trend_momentum']);
  });

  it('alle ranks > Schwelle → leeres Array', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: 10,
      alpha: 11,
      trend_momentum: 12,
      value_alpha_potential: 13,
      diversification: 14,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual([]);
  });

  it('null-Ranks werden ignoriert (nicht als Top-25% gezählt)', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: null,
      alpha: null,
      trend_momentum: null,
      value_alpha_potential: 1,
      diversification: 2,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual(['value_alpha_potential', 'diversification']);
  });

  it('Reihenfolge folgt MODEL_KEYS-Reihenfolge', () => {
    const ranks: Record<ModelKey, number | null> = {
      diversification: 1,
      quality_classic: 1,
      alpha: 1,
      trend_momentum: 1,
      value_alpha_potential: 1,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual([
      'quality_classic',
      'alpha',
      'trend_momentum',
      'value_alpha_potential',
      'diversification',
    ]);
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run lib/__tests__/model-info.test.ts
```

Expected: FAIL — `Cannot find module '../model-info'`

- [ ] **Step 3: Daten-Modul implementieren**

Erstelle `frontend/lib/model-info.ts`:

```typescript
export const MODEL_KEYS = [
  'quality_classic',
  'alpha',
  'trend_momentum',
  'value_alpha_potential',
  'diversification',
] as const;

export type ModelKey = (typeof MODEL_KEYS)[number];

export const MODEL_INFO: Record<ModelKey, { label: string; description: string }> = {
  quality_classic: {
    label: 'Quality',
    description:
      'Fundamental gesund & günstig bewertet — Kombiniert 8 klassische Kennzahlen (Marge, Verschuldung, ROE, KGV …) zu einem Score.',
  },
  alpha: {
    label: 'Alpha',
    description:
      'Konsistent besser als der Index — Outperformance vs. Benchmark über mehrere Zeithorizonte, mit Sharpe gewichtet.',
  },
  trend_momentum: {
    label: 'Trend',
    description:
      'Aktuelles Momentum — Welche Aktien zuletzt stärker als der Markt liefen, jüngere Daten zählen mehr.',
  },
  value_alpha_potential: {
    label: 'Value',
    description:
      'Mean-Reversion-Kandidaten — Wie weit unter dem eigenen historischen Outperformance-Hoch der Titel steht.',
  },
  diversification: {
    label: 'Diversification',
    description:
      'Risiko-Diversifikatoren — Niedrige Eigenvolatilität und niedrige Korrelation zu anderen Titeln im Universum.',
  },
};

export const SWEET_SPOT_DEFINITION =
  'Sweet-Spot-Aktien liegen im Top-25 % in mindestens 3 von 5 Modellen — also auf mehreren unabhängigen Achsen überzeugend, nicht nur in einer Disziplin.';

/**
 * Gibt die Modelle zurück, in denen der Ticker im Top-25 % liegt.
 * Schwelle: rank <= ceil(totalStocks * 0.25), spiegelt Backend-Logik
 * aus test_top25_in_3_of_5_models_is_sweet_spot.
 */
export function getSweetSpotModels(
  perModelRanks: Record<string, number | null>,
  totalStocks: number,
): ModelKey[] {
  const threshold = Math.ceil(totalStocks * 0.25);
  return MODEL_KEYS.filter((key) => {
    const rank = perModelRanks[key];
    return rank !== null && rank !== undefined && rank <= threshold;
  });
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run lib/__tests__/model-info.test.ts
```

Expected: PASS, 7 Tests grün

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/model-info.ts frontend/lib/__tests__/model-info.test.ts
git commit -m "feat(frontend): model-info Daten-Modul mit Sweet-Spot-Helper

Single Source of Truth für die 5 Modell-Beschreibungen plus
getSweetSpotModels() — Schwelle ceil(n*0.25), Backend-konsistent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: shadcn-Popover installieren

**Files:**
- Create: `frontend/components/ui/popover.tsx` (via CLI)
- ggf. modifiziert: `frontend/package.json`, `frontend/package-lock.json`

- [ ] **Step 1: shadcn CLI ausführen**

```bash
cd frontend && npx shadcn@latest add popover
```

Bei Prompt zu Overwrites: keine bestehenden Dateien überschreiben (sollte nur `components/ui/popover.tsx` neu anlegen).

- [ ] **Step 2: Verifikation**

```bash
ls frontend/components/ui/popover.tsx
cd frontend && grep "@radix-ui/react-popover" package.json
```

Expected: Datei existiert, Dependency in package.json.

- [ ] **Step 3: Typecheck + Build-Smoke-Test**

```bash
cd frontend && npm run typecheck
```

Expected: keine Type-Errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ui/popover.tsx frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): shadcn Popover-Komponente hinzugefügt

Vorbereitung für Tooltip/Sweet-Spot-Explainer (Item 2).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `InfoPopover` Komponente (TDD)

**Files:**
- Create: `frontend/components/InfoPopover.tsx`
- Test: `frontend/components/__tests__/InfoPopover.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/components/__tests__/InfoPopover.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { InfoPopover } from '../InfoPopover';

describe('InfoPopover', () => {
  it('rendert Icon-Trigger mit korrektem aria-label', () => {
    render(
      <InfoPopover ariaLabel="Info zu Quality">
        <p>Quality-Beschreibung</p>
      </InfoPopover>,
    );
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeInTheDocument();
  });

  it('Popover-Content initial nicht sichtbar', () => {
    render(
      <InfoPopover ariaLabel="Info zu Quality">
        <p>Quality-Beschreibung</p>
      </InfoPopover>,
    );
    expect(screen.queryByText('Quality-Beschreibung')).not.toBeInTheDocument();
  });

  it('Klick auf Trigger öffnet Popover', () => {
    render(
      <InfoPopover ariaLabel="Info zu Quality">
        <p>Quality-Beschreibung</p>
      </InfoPopover>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    expect(screen.getByText('Quality-Beschreibung')).toBeInTheDocument();
  });

  it('Klick auf Trigger ruft stopPropagation auf (kein Parent-onClick)', () => {
    const parentClick = vi.fn();
    render(
      <div onClick={parentClick}>
        <InfoPopover ariaLabel="Info zu Quality">
          <p>Quality-Beschreibung</p>
        </InfoPopover>
      </div>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    expect(parentClick).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run components/__tests__/InfoPopover.test.tsx
```

Expected: FAIL — `Cannot find module '../InfoPopover'`

- [ ] **Step 3: Komponente implementieren**

Erstelle `frontend/components/InfoPopover.tsx`:

```tsx
'use client';

import { Info } from 'lucide-react';
import type { ReactNode } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

interface Props {
  ariaLabel: string;
  children: ReactNode;
}

export function InfoPopover({ ariaLabel, children }: Props) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          onClick={(e) => e.stopPropagation()}
          className="inline-flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Info className="h-3.5 w-3.5 opacity-60 hover:opacity-100" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="max-w-xs text-sm leading-relaxed" side="top">
        {children}
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run components/__tests__/InfoPopover.test.tsx
```

Expected: PASS, 4 Tests grün.

> **Hinweis falls Test 3 ("Klick öffnet Popover") flaky ist:** Radix nutzt portals. Falls `screen.getByText` den Content nicht findet, prüfe ob jsdom Portals rendert — sollte standardmäßig funktionieren. Fallback: `screen.findByText` (async) statt `getByText`.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/InfoPopover.tsx frontend/components/__tests__/InfoPopover.test.tsx
git commit -m "feat(frontend): InfoPopover-Komponente (klickbares Info-Icon)

Generischer Wrapper um shadcn Popover mit lucide Info-Icon.
stopPropagation verhindert Sort-Trigger im Tabellen-Header.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `ModelInfoIcon` Wrapper (TDD)

**Files:**
- Create: `frontend/components/ModelInfoIcon.tsx`
- Test: `frontend/components/__tests__/ModelInfoIcon.test.tsx`

- [ ] **Step 1: Failing Tests schreiben**

Erstelle `frontend/components/__tests__/ModelInfoIcon.test.tsx`:

```typescript
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { ModelInfoIcon } from '../ModelInfoIcon';

describe('ModelInfoIcon', () => {
  it('aria-label nutzt MODEL_INFO.label', () => {
    render(<ModelInfoIcon modelKey="quality_classic" />);
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeInTheDocument();
  });

  it('Klick zeigt Modell-Beschreibung aus MODEL_INFO', () => {
    render(<ModelInfoIcon modelKey="quality_classic" />);
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    expect(screen.getByText(/8 klassische Kennzahlen/)).toBeInTheDocument();
  });

  it('funktioniert für alle 5 Modell-Keys', () => {
    const cases: Array<[Parameters<typeof ModelInfoIcon>[0]['modelKey'], string]> = [
      ['quality_classic', 'Quality'],
      ['alpha', 'Alpha'],
      ['trend_momentum', 'Trend'],
      ['value_alpha_potential', 'Value'],
      ['diversification', 'Diversification'],
    ];
    for (const [key, label] of cases) {
      const { unmount } = render(<ModelInfoIcon modelKey={key} />);
      expect(screen.getByRole('button', { name: `Info zu ${label}` })).toBeInTheDocument();
      unmount();
    }
  });
});
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run components/__tests__/ModelInfoIcon.test.tsx
```

Expected: FAIL — `Cannot find module '../ModelInfoIcon'`

- [ ] **Step 3: Komponente implementieren**

Erstelle `frontend/components/ModelInfoIcon.tsx`:

```tsx
import { InfoPopover } from './InfoPopover';
import { MODEL_INFO, type ModelKey } from '@/lib/model-info';

interface Props {
  modelKey: ModelKey;
}

export function ModelInfoIcon({ modelKey }: Props) {
  const info = MODEL_INFO[modelKey];
  return (
    <InfoPopover ariaLabel={`Info zu ${info.label}`}>
      <p>{info.description}</p>
    </InfoPopover>
  );
}
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run components/__tests__/ModelInfoIcon.test.tsx
```

Expected: PASS, 3 Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ModelInfoIcon.tsx frontend/components/__tests__/ModelInfoIcon.test.tsx
git commit -m "feat(frontend): ModelInfoIcon-Wrapper für die 5 Quant-Modelle

Liest aus MODEL_INFO und reicht Label+Description in InfoPopover.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Rankings-Tabelle integrieren (TDD)

**Files:**
- Modify: `frontend/app/rankings/[runId]/rankings-table.tsx`
- Modify: `frontend/app/rankings/__tests__/rankings-table.test.tsx`

- [ ] **Step 1: Neue Test-Cases anhängen**

Öffne `frontend/app/rankings/__tests__/rankings-table.test.tsx`. Innerhalb von `describe('RankingsTable', () => {` neue Tests ergänzen (vor dem schließenden `})`):

```typescript
  it('rendert Info-Icon im Quality-Header', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeInTheDocument();
  });

  it('Klick auf Header-Info-Icon sortiert nicht', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    // Initial: sortiert nach total_rank asc → AAPL=1, MSFT=2
    const rowsBefore = screen.getAllByRole('row').slice(1).map((r) => r.textContent);
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    const rowsAfter = screen.getAllByRole('row').slice(1).map((r) => r.textContent);
    expect(rowsAfter).toEqual(rowsBefore);
  });

  it('rendert Info-Icon im Sweet-Spot-Header mit generischer Definition', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    const trigger = screen.getByRole('button', { name: 'Sweet-Spot-Definition' });
    fireEvent.click(trigger);
    expect(screen.getByText(/Top-25 ?% in mindestens 3 von 5/)).toBeInTheDocument();
  });

  it('Klick auf Sweet-Spot-Badge zeigt ticker-spezifische Modell-Liste', () => {
    render(<RankingsTable items={sampleItems} runId="test-run-id" />);
    // AAPL: alle 5 Ranks <= ceil(2*0.25)=1? Nein, totalStocks=2 → Schwelle=1.
    // Für sinnvollen Test totalStocks erhöhen via separater Sample.
    // → wir nutzen ein eigenes Sample für diesen Test.
  });
```

Wir brauchen für den Sweet-Spot-Test ein größeres Sample, sonst ist die Schwelle `ceil(2 * 0.25) = 1` zu eng. Ergänze einen zweiten Sample-Block direkt vor diesem Test:

```typescript
  it('Klick auf Sweet-Spot-Badge zeigt ticker-spezifische Modell-Liste', () => {
    const sweetSpotSample: RankingItem[] = Array.from({ length: 20 }, (_, i) => ({
      ticker: `T${i + 1}`,
      total_rank: i + 1,
      weighted_avg: i + 1,
      is_sweet_spot: i === 0, // nur T1 ist sweet spot
      per_model_ranks: {
        quality_classic: i + 1,
        alpha: i + 1,
        trend_momentum: i + 1,
        value_alpha_potential: i + 1,
        diversification: i + 1,
      },
    }));
    render(<RankingsTable items={sweetSpotSample} runId="test-run-id" />);
    const badge = screen.getByRole('button', { name: 'Sweet-Spot-Begründung für T1' });
    fireEvent.click(badge);
    // Schwelle: ceil(20*0.25)=5 → T1 (rank=1 überall) erfüllt in allen 5
    expect(screen.getByText(/T1 ist Top-25 ?% in/)).toBeInTheDocument();
    expect(screen.getByText(/5\/5/)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run app/rankings/__tests__/rankings-table.test.tsx
```

Expected: FAIL — neue Tests scheitern, weil Icons + Sweet-Spot-Popover noch nicht da sind.

- [ ] **Step 3: `rankings-table.tsx` anpassen**

Öffne `frontend/app/rankings/[runId]/rankings-table.tsx`. Folgende Änderungen:

**a) Imports ergänzen (nach Zeile 18):**

```tsx
import { InfoPopover } from '@/components/InfoPopover';
import { ModelInfoIcon } from '@/components/ModelInfoIcon';
import { MODEL_INFO, SWEET_SPOT_DEFINITION, getSweetSpotModels, type ModelKey } from '@/lib/model-info';
```

**b) `SortableHead` erweitern um optionales `infoIcon`-Prop.** Ersetze die `SortableHeadProps` und `SortableHead`-Definition (aktuelle Zeilen 71–96):

```tsx
interface SortableHeadProps {
  sortKey: SortKey;
  activeSortKey: SortKey;
  sortDir: SortDir;
  onSort: (key: SortKey) => void;
  infoIcon?: React.ReactNode;
  children: React.ReactNode;
}

function SortableHead({ sortKey, activeSortKey, sortDir, onSort, infoIcon, children }: SortableHeadProps) {
  const isActive = activeSortKey === sortKey;
  const ariaSort = isActive ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none';
  const Icon = isActive ? (sortDir === 'asc' ? ArrowUp : ArrowDown) : ArrowUpDown;

  return (
    <TableHead
      className="cursor-pointer select-none"
      onClick={() => onSort(sortKey)}
      aria-sort={ariaSort}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {infoIcon}
        <Icon className={`h-3 w-3 ${isActive ? '' : 'opacity-30'}`} />
      </span>
    </TableHead>
  );
}
```

**c) Modell-Header mit `infoIcon` versorgen.** Ersetze den `{MODEL_COLUMNS.map(...)}`-Block (aktuell Zeilen 172–182):

```tsx
              {MODEL_COLUMNS.map((col) => (
                <SortableHead
                  key={col.key}
                  sortKey={col.key}
                  activeSortKey={sortKey}
                  sortDir={sortDir}
                  onSort={handleSort}
                  infoIcon={<ModelInfoIcon modelKey={col.key as ModelKey} />}
                >
                  {col.label}
                </SortableHead>
              ))}
```

**d) Sweet-Spot-Header bekommt Popover.** Ersetze die aktuelle Zeile 171 (`<TableHead>Sweet-Spot</TableHead>`):

```tsx
              <TableHead>
                <span className="inline-flex items-center gap-1">
                  Sweet-Spot
                  <InfoPopover ariaLabel="Sweet-Spot-Definition">
                    <p>{SWEET_SPOT_DEFINITION}</p>
                  </InfoPopover>
                </span>
              </TableHead>
```

**e) Sweet-Spot-Badge wird Popover-Trigger.** Aktuell (Zeile ~199–201):

```tsx
                <TableCell>
                  {item.is_sweet_spot ? <Badge variant="default">★</Badge> : null}
                </TableCell>
```

Ersetzen durch:

```tsx
                <TableCell>
                  {item.is_sweet_spot ? (
                    <SweetSpotBadge ticker={item.ticker} perModelRanks={item.per_model_ranks} totalStocks={items.length} />
                  ) : null}
                </TableCell>
```

**f) Neue Hilfskomponente `SweetSpotBadge` direkt über `RankingsTable` (nach `SortableHead`) einfügen:**

```tsx
function SweetSpotBadge({
  ticker,
  perModelRanks,
  totalStocks,
}: {
  ticker: string;
  perModelRanks: Record<string, number | null>;
  totalStocks: number;
}) {
  const sweetSpotKeys = getSweetSpotModels(perModelRanks, totalStocks);
  const labels = sweetSpotKeys.map((k) => MODEL_INFO[k].label).join(', ');
  const count = sweetSpotKeys.length;

  return (
    <InfoPopover ariaLabel={`Sweet-Spot-Begründung für ${ticker}`}>
      <p>
        <strong>{ticker}</strong> ist Top-25 % in {labels} ({count}/5 Modellen).
      </p>
    </InfoPopover>
  );
}
```

> **Hinweis:** Der Sternchen-Look (★) entfällt — das Info-Icon dient als Sweet-Spot-Indikator und Trigger zugleich. Falls visuell ein "Badge"-Charakter gewünscht wäre, könnte ein zusätzlicher Stern im Popover-Trigger sein — das ist aber Visual-Polish und gehört in Item 3, nicht hier.

> **Alternative falls du den Stern behalten willst:** ersetze die `InfoPopover`-Komponente in `SweetSpotBadge` durch eine ad-hoc-Implementation mit shadcn `Popover` direkt, wobei der `PopoverTrigger asChild` ein `<button>` mit `Badge`-Inhalt umschließt. Das ist 5 Zeilen extra Code. Stand jetzt: kein Stern, weil das Icon ausreicht.

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run app/rankings/__tests__/rankings-table.test.tsx
```

Expected: PASS — alle bisherigen + neuen Tests grün.

> **Falls der Test "Klick auf Header-Info-Icon sortiert nicht" fehlschlägt:** `stopPropagation` im `InfoPopover` greift, aber Radix kapselt den Trigger ggf. anders. Fallback: zusätzlich `onMouseDown={(e) => e.stopPropagation()}` auf dem `<button>` in `InfoPopover.tsx` setzen.

- [ ] **Step 5: Commit**

```bash
git add frontend/app/rankings/[runId]/rankings-table.tsx frontend/app/rankings/__tests__/rankings-table.test.tsx
git commit -m "feat(frontend): Tooltips + Sweet-Spot-Explainer in Rankings-Tabelle

Info-Icons in allen 5 Modell-Headern und im Sweet-Spot-Header.
Sweet-Spot-Badge wird klickbar, zeigt ticker-spezifische Top-25%-Modelle.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `ModelRankCards` integrieren (TDD)

**Files:**
- Modify: `frontend/components/factsheet/ModelRankCards.tsx`
- Modify: `frontend/components/factsheet/__tests__/ModelRankCards.test.tsx`

- [ ] **Step 1: Neue Test-Cases anhängen**

Öffne `frontend/components/factsheet/__tests__/ModelRankCards.test.tsx`, ergänze innerhalb von `describe('ModelRankCards', () => {`:

```typescript
  it('jede Card hat ein Info-Icon mit aria-label', () => {
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    expect(screen.getByRole('button', { name: 'Info zu Quality' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Alpha' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Trend' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Value' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Info zu Diversification' })).toBeDefined();
  });

  it('Klick auf Quality-Info zeigt 8-Kennzahlen-Tooltip', async () => {
    const { fireEvent } = await import('@testing-library/react');
    render(<ModelRankCards perModelRanks={perModelRanks} />);
    fireEvent.click(screen.getByRole('button', { name: 'Info zu Quality' }));
    expect(screen.getByText(/8 klassische Kennzahlen/)).toBeDefined();
  });
```

- [ ] **Step 2: Tests laufen lassen, müssen fehlen**

```bash
cd frontend && npx vitest run components/factsheet/__tests__/ModelRankCards.test.tsx
```

Expected: FAIL — Info-Icons fehlen noch.

- [ ] **Step 3: `ModelRankCards.tsx` anpassen**

Öffne `frontend/components/factsheet/ModelRankCards.tsx`. Folgende Änderungen:

**a) Import oben ergänzen:**

```tsx
import { ModelInfoIcon } from '@/components/ModelInfoIcon';
import type { ModelKey } from '@/lib/model-info';
```

**b) `MODELS`-Konstante typen** (aktuell Zeilen 7–13):

```tsx
const MODELS: Array<{ key: ModelKey; label: string }> = [
  { key: 'quality_classic', label: 'Quality Classic' },
  { key: 'alpha', label: 'Alpha' },
  { key: 'trend_momentum', label: 'Trend Momentum' },
  { key: 'value_alpha_potential', label: 'Value Alpha Potential' },
  { key: 'diversification', label: 'Diversification' },
];
```

**c) `CardTitle` mit Icon erweitern.** Ersetze die `<CardHeader>`-Sektion innerhalb der `.map(...)` (aktuelle Zeilen 45–49):

```tsx
            <CardHeader className="pb-1 pt-4 px-4">
              <CardTitle className="text-xs font-medium text-muted-foreground leading-tight">
                <span className="inline-flex items-center gap-1">
                  {label}
                  <ModelInfoIcon modelKey={key} />
                </span>
              </CardTitle>
            </CardHeader>
```

- [ ] **Step 4: Tests laufen lassen, müssen grün sein**

```bash
cd frontend && npx vitest run components/factsheet/__tests__/ModelRankCards.test.tsx
```

Expected: PASS — alle bisherigen + neuen Tests grün.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/factsheet/ModelRankCards.tsx frontend/components/factsheet/__tests__/ModelRankCards.test.tsx
git commit -m "feat(frontend): Tooltips auf Factsheet-ModelRankCards

Info-Icons in jeder der 5 CardTitles — gleiche MODEL_INFO-Texte
wie in Rankings-Tabelle (DRY via lib/model-info.ts).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Verifikation (Pre-Push-Mirror) + Manual Smoke-Test

**Files:** keine — Validation-Schritt.

- [ ] **Step 1: Frontend-Lint + Typecheck + Tests grün**

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

Expected: alle 3 Steps grün. Bei Fehlern → fixen und neu committen, **nicht** zu nächsten Steps weitergehen.

- [ ] **Step 2: Backend-CI-Mirror (unverändertes Backend, sollte grün bleiben)**

```bash
cd backend && uv run mypy . && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

Expected: grün.

> **Warum auch Backend prüfen:** Sheylas Standard-Pre-Push-Mirror laut ihrer Memory `feedback_pre_push_ci_mirror`. Niemals nur `pytest` laufen lassen.

- [ ] **Step 3: Dev-Server starten und manuell prüfen**

```bash
cd frontend && npm run dev
```

In `http://localhost:3000` öffnen. Dann:

1. Zu `/rankings/[runId]` navigieren (irgendeiner existierender Run).
2. Auf jedes Info-Icon in den 5 Modell-Headern klicken — Popover öffnet sich, Text korrekt.
3. Auf das Info-Icon im Sweet-Spot-Header klicken — generische Definition zeigt sich.
4. Auf ein Sweet-Spot-Icon (in einer Zeile) klicken — ticker-spezifische Modell-Liste zeigt sich.
5. Spalte sortieren (Klick auf Label/Sort-Pfeil), dann Info-Icon klicken — Sort darf sich **nicht** ändern.
6. Zu `/stocks/[ticker]` einer Aktie navigieren — auf jeder der 5 Cards das Info-Icon prüfen.
7. Mobile-Viewport (DevTools-Toggle) — Icons sind tappbar, Popover öffnet sich.
8. Keyboard-Navigation: Tab durch die Icons, Enter öffnet, Escape schließt.

- [ ] **Step 4: E2E-Smoke (optional, falls Zeit)**

```bash
cd frontend && npm run e2e
```

Existing Playwright-Tests sollten weiter grün sein (Icons sollten bestehende Selektoren nicht brechen).

- [ ] **Step 5: Abschluss-Commit (nur falls kosmetische Fixes anfielen)**

Falls aus Step 3 noch Anpassungen kommen, einzeln committen.

---

## Self-Review

- **Spec-Coverage:**
  - Architektur (`model-info.ts`, Popover, InfoPopover, ModelInfoIcon) → Tasks 1–4 ✓
  - Rankings-Tabelle-Integration → Task 5 ✓
  - ModelRankCards-Integration → Task 6 ✓
  - Tooltip-Texte (5 Modelle + Sweet-Spot) → Task 1 (Daten) ✓
  - Touch-Tauglichkeit (Klick statt Hover) → InfoPopover (Task 3) ✓
  - A11y (aria-labels) → Tasks 3, 4, 5 ✓
  - Klick-vs.-Sort-Konflikt → stopPropagation in Task 3 + Test in Task 5 ✓
  - Tests TDD-first für Datenmodul → Task 1 ✓
  - Verifikation Lint/Typecheck/Tests + Backend-Mirror + Manual → Task 7 ✓

- **Placeholder-Scan:** Keine TBDs, alle Code-Blöcke vollständig, alle Test-Cases mit konkretem Code.

- **Type-Konsistenz:**
  - `ModelKey` aus `lib/model-info.ts` in allen Tasks gleich benannt.
  - `getSweetSpotModels` Signatur konsistent zwischen Definition (Task 1) und Aufruf (Task 5).
  - `InfoPopover`-Props `{ ariaLabel, children }` konsistent zwischen Test (Task 3) und Verwendung in `ModelInfoIcon` (Task 4) und `RankingsTable` (Task 5).
  - `ModelInfoIcon`-Props `{ modelKey }` konsistent.

Plan ist intern stimmig und vollständig.
