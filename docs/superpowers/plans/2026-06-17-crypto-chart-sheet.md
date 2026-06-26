# CryptoChartSheet — Visuelle Chartanalyse im Pro Mode

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im Crypto Pro Mode erhält jede Tabellenzeile einen „📊 Chart"-Button, der ein Sheet mit Tab-Navigation öffnet: Preis/Score/RSI/Fear&Greed als Recharts-Chart im ersten Tab, bestehender CryptoAgentPanel im zweiten Tab.

**Architecture:** Zwei neue Komponenten (`CryptoHistoryChart`, `CryptoChartSheet`) werden in `CryptoProRow` eingehängt. `CryptoChartSheet` wraps Shadcn `Sheet` + `Tabs`. `CryptoHistoryChart` fetcht via existierendem `useCryptoHistory`-Hook und rendert zwei gestapelte `ComposedChart`-Instanzen (Recharts). Der bestehende `CryptoAgentPanel` wandert unverändert in Tab 2.

**Tech Stack:** Next.js 14, React 18, TypeScript, Recharts 2.12, Shadcn/UI (Sheet, Tabs), TanStack Query, Vitest + Testing Library

---

## Dateistruktur

| Aktion | Pfad | Verantwortung |
|---|---|---|
| Neu | `frontend/components/crypto/CryptoHistoryChart.tsx` | Recharts-Chart: Preis+Score oben, RSI+F&G unten, Zeitraum-Selector |
| Neu | `frontend/components/crypto/CryptoChartSheet.tsx` | Sheet-Wrapper mit Tabs (Chart / KI-Analyse), Button-Trigger |
| Neu | `frontend/components/crypto/__tests__/CryptoHistoryChart.test.tsx` | Unit-Tests CryptoHistoryChart |
| Neu | `frontend/components/crypto/__tests__/CryptoChartSheet.test.tsx` | Unit-Tests CryptoChartSheet |
| Neu | `frontend/components/ui/tabs.tsx` | Shadcn Tabs (via CLI installiert) |
| Ändern | `frontend/components/crypto/CryptoProRow.tsx` | Neuen `<td>` mit `CryptoChartSheet` am Zeilenende |
| Ändern | `frontend/app/crypto/crypto-client.tsx` | Neuen `<th>Chart</th>` im Tabellen-Header |

---

## Task 1: Feature Branch + Shadcn Tabs installieren

**Files:**
- Kein Code — Branch + Dependency

- [ ] **Step 1: Neuen Feature-Branch anlegen (von main)**

```bash
git checkout main && git pull
git checkout -b feat/crypto-chart-sheet
```

Erwartete Ausgabe: `Switched to a new branch 'feat/crypto-chart-sheet'`

- [ ] **Step 2: Shadcn Tabs installieren**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx shadcn-ui@latest add tabs
```

Bei der Frage nach dem Überschreiben existierender Dateien: `y` bestätigen.

- [ ] **Step 3: Prüfen, dass tabs.tsx erstellt wurde**

```bash
ls frontend/components/ui/tabs.tsx
```

Erwartete Ausgabe: Datei existiert (kein Fehler)

- [ ] **Step 4: Commit**

```bash
git add frontend/components/ui/tabs.tsx
git commit -m "chore: add shadcn tabs component"
```

---

## Task 2: CryptoHistoryChart — Test zuerst, dann Implementierung

**Files:**
- Create: `frontend/components/crypto/CryptoHistoryChart.tsx`
- Test: `frontend/components/crypto/__tests__/CryptoHistoryChart.test.tsx`

- [ ] **Step 1: Test-Datei schreiben**

Erstelle `frontend/components/crypto/__tests__/CryptoHistoryChart.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CryptoHistoryChart } from '../CryptoHistoryChart';
import type { CryptoHistoryPoint } from '@/lib/api/crypto';
import { useCryptoHistory } from '@/hooks/useCryptoHistory';

vi.mock('@/hooks/useCryptoHistory');

function point(overrides: Partial<CryptoHistoryPoint> = {}): CryptoHistoryPoint {
  return {
    date: '2026-06-15',
    signal: 'BUY',
    score: 70,
    price_chf: 82000,
    fear_greed_value: 50,
    rsi_14: 55,
    detected_patterns: [],
    pattern_score: 0,
    ...overrides,
  };
}

function renderChart(ticker = 'BTC') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CryptoHistoryChart ticker={ticker} />
    </QueryClientProvider>
  );
}

describe('CryptoHistoryChart', () => {
  beforeEach(() => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [], loading: false });
  });

  it('zeigt kein chart-testid während Ladezustand', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [], loading: true });
    renderChart();
    expect(screen.queryByTestId('crypto-history-chart')).not.toBeInTheDocument();
  });

  it('zeigt Platzhalter wenn weniger als 2 Datenpunkte vorhanden', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [point()], loading: false });
    renderChart();
    expect(screen.getByTestId('crypto-history-chart')).toBeInTheDocument();
    expect(screen.getByTestId('no-data-placeholder')).toBeInTheDocument();
  });

  it('zeigt Chart-Container wenn 2+ Datenpunkte vorhanden', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({
      data: [point(), point({ date: '2026-06-16', score: 84, price_chf: 85000 })],
      loading: false,
    });
    renderChart();
    expect(screen.getByTestId('crypto-history-chart')).toBeInTheDocument();
    expect(screen.queryByTestId('no-data-placeholder')).not.toBeInTheDocument();
  });

  it('übergibt neuen days-Wert an useCryptoHistory nach Klick auf Zeitraum-Button', () => {
    vi.mocked(useCryptoHistory).mockReturnValue({ data: [], loading: false });
    renderChart();
    fireEvent.click(screen.getByTestId('days-btn-90'));
    expect(vi.mocked(useCryptoHistory)).toHaveBeenCalledWith('BTC', 90);
  });

  it('default Zeitraum ist 30 Tage', () => {
    renderChart();
    expect(vi.mocked(useCryptoHistory)).toHaveBeenCalledWith('BTC', 30);
  });
});
```

- [ ] **Step 2: Tests ausführen — müssen FAIL sein**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/crypto/__tests__/CryptoHistoryChart.test.tsx
```

Erwartete Ausgabe: `FAIL` mit `Cannot find module '../CryptoHistoryChart'`

- [ ] **Step 3: CryptoHistoryChart implementieren**

Erstelle `frontend/components/crypto/CryptoHistoryChart.tsx`:

```tsx
'use client';

import { useState } from 'react';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { useCryptoHistory } from '@/hooks/useCryptoHistory';
import { Skeleton } from '@/components/ui/skeleton';
import type { CryptoHistoryPoint } from '@/lib/api/crypto';

const DAYS_OPTIONS = [7, 30, 90] as const;
type Days = (typeof DAYS_OPTIONS)[number];

interface CryptoHistoryChartProps {
  ticker: string;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('de-CH', { day: '2-digit', month: 'short' });
}

interface TooltipPayloadEntry {
  name: string;
  value: number | null;
  color: string;
}

function ChartTooltip({
  active,
  payload,
  label,
  data,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  data: CryptoHistoryPoint[];
}) {
  if (!active || !payload?.length) return null;
  const point = data.find((d) => d.date === label);
  return (
    <div className="rounded border border-border bg-popover p-2 text-xs shadow">
      <div className="font-medium mb-1">{formatDate(label ?? null)}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value != null ? Number(p.value).toFixed(1) : '—'}
        </div>
      ))}
      {point?.detected_patterns.length ? (
        <div className="mt-1 text-[10px] text-amber-400">
          {point.detected_patterns.join(', ')}
        </div>
      ) : null}
    </div>
  );
}

export function CryptoHistoryChart({ ticker }: CryptoHistoryChartProps) {
  const [days, setDays] = useState<Days>(30);
  const { data, loading } = useCryptoHistory(ticker, days);

  if (loading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-[200px] w-full" />
        <Skeleton className="h-[100px] w-full" />
      </div>
    );
  }

  const hasEnoughData = data.length >= 2;
  const patternDots = data.filter((d) => d.detected_patterns.length > 0);

  return (
    <div className="space-y-3" data-testid="crypto-history-chart">
      {/* Zeitraum-Selector */}
      <div className="flex gap-1 justify-end">
        {DAYS_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            data-testid={`days-btn-${d}`}
            className={`rounded px-2 py-0.5 text-xs transition-colors ${
              days === d
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {d}T
          </button>
        ))}
      </div>

      {!hasEnoughData ? (
        <p
          className="text-sm text-muted-foreground py-8 text-center"
          data-testid="no-data-placeholder"
        >
          Noch keine ausreichende Historie für diesen Ticker.
        </p>
      ) : (
        <div className="space-y-1">
          {/* Preis + Score */}
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={data} margin={{ top: 4, right: 48, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="price"
                orientation="left"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v: number) =>
                  v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v.toFixed(0)
                }
                width={44}
              />
              <YAxis
                yAxisId="score"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip
                content={(props) => (
                  <ChartTooltip
                    active={props.active}
                    payload={props.payload as TooltipPayloadEntry[]}
                    label={props.label as string}
                    data={data}
                  />
                )}
              />
              <Area
                yAxisId="price"
                type="monotone"
                dataKey="price_chf"
                name="Preis CHF"
                stroke="#7ee787"
                fill="#7ee78718"
                strokeWidth={2}
                dot={false}
                connectNulls={false}
              />
              <Line
                yAxisId="score"
                type="monotone"
                dataKey="score"
                name="Score"
                stroke="#58a6ff"
                strokeWidth={1.5}
                strokeDasharray="4 2"
                dot={false}
              />
              {patternDots.map((d, i) => (
                <ReferenceDot
                  key={i}
                  yAxisId="price"
                  x={d.date ?? undefined}
                  y={d.price_chf ?? undefined}
                  r={4}
                  fill="#ffa657"
                  stroke="none"
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>

          {/* RSI + Fear & Greed */}
          <ResponsiveContainer width="100%" height={100}>
            <ComposedChart data={data} margin={{ top: 4, right: 48, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="date" hide />
              <YAxis
                yAxisId="rsi"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <YAxis
                yAxisId="fg"
                orientation="right"
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip
                content={(props) => (
                  <ChartTooltip
                    active={props.active}
                    payload={props.payload as TooltipPayloadEntry[]}
                    label={props.label as string}
                    data={data}
                  />
                )}
              />
              <ReferenceLine
                yAxisId="rsi"
                y={70}
                stroke="#f85149"
                strokeDasharray="3 3"
                strokeOpacity={0.6}
              />
              <ReferenceLine
                yAxisId="rsi"
                y={30}
                stroke="#7ee787"
                strokeDasharray="3 3"
                strokeOpacity={0.6}
              />
              <Line
                yAxisId="rsi"
                type="monotone"
                dataKey="rsi_14"
                name="RSI"
                stroke="#bc8cff"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
              <Line
                yAxisId="fg"
                type="monotone"
                dataKey="fear_greed_value"
                name="Fear & Greed"
                stroke="#ffa657"
                strokeWidth={1.5}
                dot={false}
                connectNulls={false}
              />
            </ComposedChart>
          </ResponsiveContainer>

          {/* Legende */}
          <div className="flex flex-wrap gap-3 text-[10px] text-muted-foreground">
            <span><span className="text-[#7ee787]">—</span> Preis CHF</span>
            <span><span className="text-[#58a6ff]">- -</span> Score</span>
            <span><span className="text-[#bc8cff]">—</span> RSI</span>
            <span><span className="text-[#ffa657]">—</span> Fear &amp; Greed</span>
            <span><span className="text-[#ffa657]">●</span> Pattern erkannt</span>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Tests ausführen — müssen PASS sein**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/crypto/__tests__/CryptoHistoryChart.test.tsx
```

Erwartete Ausgabe: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/components/crypto/CryptoHistoryChart.tsx \
        frontend/components/crypto/__tests__/CryptoHistoryChart.test.tsx
git commit -m "feat(crypto): add CryptoHistoryChart with price/score/RSI/F&G panels"
```

---

## Task 3: CryptoChartSheet — Test zuerst, dann Implementierung

**Files:**
- Create: `frontend/components/crypto/CryptoChartSheet.tsx`
- Test: `frontend/components/crypto/__tests__/CryptoChartSheet.test.tsx`

- [ ] **Step 1: Test-Datei schreiben**

Erstelle `frontend/components/crypto/__tests__/CryptoChartSheet.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CryptoChartSheet } from '../CryptoChartSheet';
import type { CryptoSignal } from '@/lib/api/crypto';

vi.mock('../CryptoHistoryChart', () => ({
  CryptoHistoryChart: ({ ticker }: { ticker: string }) => (
    <div data-testid="mock-history-chart">{ticker}</div>
  ),
}));

vi.mock('../CryptoAgentPanel', () => ({
  CryptoAgentPanel: () => <div data-testid="mock-agent-panel" />,
}));

function makeSignal(overrides: Partial<CryptoSignal> = {}): CryptoSignal {
  return {
    ticker: 'BTC',
    name: 'Bitcoin',
    signal: 'STRONG_BUY',
    score: 84,
    score_components: { momentum: 25, trend: 20, sentiment: 15, markt: 12, risiko: 8 },
    signal_reason_de: 'Starke Aufwärtsdynamik',
    price_chf: 82400,
    market_cap_chf: null,
    price_change_24h_pct: 3.2,
    price_change_7d_pct: 8.1,
    ath_change_pct: -20,
    market_cap_rank: 1,
    rsi_14: 58.3,
    macd_signal: 'bullish',
    volatility_30d_pct: 42,
    correlation_smi_1y: 0.12,
    fear_greed_value: 65,
    fear_greed_label: 'Gier',
    has_six_etp: true,
    timestamp: '2026-06-17T10:00:00Z',
    detected_patterns: ['GOLDEN_CROSS'],
    pattern_score: 20,
    agent_analysis: 'Test-Analyse.',
    ...overrides,
  };
}

function renderSheet(signal = makeSignal()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CryptoChartSheet ticker={signal.ticker} signal={signal} />
    </QueryClientProvider>
  );
}

describe('CryptoChartSheet', () => {
  it('rendert Chart-Button mit korrektem data-testid', () => {
    renderSheet();
    expect(screen.getByTestId('chart-sheet-trigger-BTC')).toBeInTheDocument();
  });

  it('Sheet ist initial geschlossen — kein Chart-Inhalt sichtbar', () => {
    renderSheet();
    expect(screen.queryByTestId('mock-history-chart')).not.toBeInTheDocument();
  });

  it('Sheet öffnet sich beim Klick auf den Button', async () => {
    renderSheet();
    fireEvent.click(screen.getByTestId('chart-sheet-trigger-BTC'));
    expect(await screen.findByTestId('mock-history-chart')).toBeInTheDocument();
  });

  it('Chart-Tab zeigt CryptoHistoryChart mit korrektem Ticker', async () => {
    renderSheet();
    fireEvent.click(screen.getByTestId('chart-sheet-trigger-BTC'));
    const chart = await screen.findByTestId('mock-history-chart');
    expect(chart).toHaveTextContent('BTC');
  });

  it('KI-Analyse-Tab zeigt CryptoAgentPanel nach Tab-Wechsel', async () => {
    renderSheet();
    fireEvent.click(screen.getByTestId('chart-sheet-trigger-BTC'));
    await screen.findByTestId('mock-history-chart');
    fireEvent.click(screen.getByRole('tab', { name: /KI-Analyse/i }));
    expect(screen.getByTestId('mock-agent-panel')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Tests ausführen — müssen FAIL sein**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/crypto/__tests__/CryptoChartSheet.test.tsx
```

Erwartete Ausgabe: `FAIL` mit `Cannot find module '../CryptoChartSheet'`

- [ ] **Step 3: CryptoChartSheet implementieren**

Erstelle `frontend/components/crypto/CryptoChartSheet.tsx`:

```tsx
'use client';

import { useState } from 'react';
import { BarChart2 } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { CryptoHistoryChart } from './CryptoHistoryChart';
import { CryptoAgentPanel } from './CryptoAgentPanel';
import { type CryptoSignal, signalColor, signalLabel } from '@/lib/api/crypto';

interface CryptoChartSheetProps {
  ticker: string;
  signal: CryptoSignal;
}

export function CryptoChartSheet({ ticker, signal }: CryptoChartSheetProps) {
  const [open, setOpen] = useState(false);
  const color = signalColor(signal.signal);
  const label = signalLabel(signal.signal);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid={`chart-sheet-trigger-${ticker}`}
        className="flex items-center gap-1 rounded-md border border-border/50 px-2 py-1 text-[11px] text-muted-foreground hover:border-primary/50 hover:text-primary transition-colors"
      >
        <BarChart2 className="h-3 w-3" />
        Chart
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="right" className="sm:max-w-2xl overflow-y-auto">
          <SheetHeader className="mb-4">
            <SheetTitle className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-lg">{ticker}</span>
              <span
                className="text-xs font-semibold px-2 py-0.5 rounded-full border"
                style={{ color, borderColor: `${color}50`, backgroundColor: `${color}20` }}
              >
                {label}
              </span>
              <span className="text-sm text-muted-foreground font-normal">
                {signal.name}
              </span>
            </SheetTitle>
          </SheetHeader>

          <Tabs defaultValue="chart">
            <TabsList className="mb-4 w-full">
              <TabsTrigger value="chart" className="flex-1">
                📊 Chart
              </TabsTrigger>
              <TabsTrigger value="analysis" className="flex-1">
                ✦ KI-Analyse
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chart">
              <CryptoHistoryChart ticker={ticker} />
            </TabsContent>

            <TabsContent value="analysis">
              <CryptoAgentPanel
                ticker={ticker}
                detectedPatterns={signal.detected_patterns}
                cachedAnalysis={signal.agent_analysis}
              />
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
    </>
  );
}
```

- [ ] **Step 4: Tests ausführen — müssen PASS sein**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/crypto/__tests__/CryptoChartSheet.test.tsx
```

Erwartete Ausgabe: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add frontend/components/crypto/CryptoChartSheet.tsx \
        frontend/components/crypto/__tests__/CryptoChartSheet.test.tsx
git commit -m "feat(crypto): add CryptoChartSheet with tab navigation (Chart + KI-Analyse)"
```

---

## Task 4: CryptoProRow + Tabellen-Header verdrahten

**Files:**
- Modify: `frontend/components/crypto/CryptoProRow.tsx:34-79`
- Modify: `frontend/app/crypto/crypto-client.tsx:107-118`

- [ ] **Step 1: CryptoProRow — neuen `<td>` am Zeilenende hinzufügen**

In `frontend/components/crypto/CryptoProRow.tsx`:

Zeile 2: Import ergänzen:
```tsx
import { CryptoChartSheet } from '@/components/crypto/CryptoChartSheet';
```

Die letzte `<td>` (Sparkline, aktuell Zeile 76–79) bleibt. Danach eine neue `<td>` einfügen:

```tsx
      <td className="py-2 px-3">
        <SignalSparkline data={history} />
      </td>
      <td className="py-2 px-3">
        <CryptoChartSheet ticker={signal.ticker} signal={signal} />
      </td>
    </tr>
```

Das vollständig geänderte Return-Statement von `CryptoProRow`:

```tsx
  return (
    <tr className="border-b border-border/30 hover:bg-muted/20 transition-colors text-sm">
      <td className="py-2 px-3">
        <div className="font-mono font-bold">{signal.ticker}</div>
        <div className="text-[10px] text-muted-foreground">{signal.name}</div>
      </td>
      <td className="py-2 px-3">
        <span
          className="text-xs font-semibold px-2 py-0.5 rounded-full border whitespace-nowrap"
          style={{ color, borderColor: color + '50', backgroundColor: color + '20' }}
        >
          {label}
        </span>
      </td>
      <td className="py-2 px-3 tabular-nums">
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-12 rounded-full bg-[#21262d] overflow-hidden">
            <div
              className="h-full rounded-full"
              style={{ width: `${Math.round(signal.score)}%`, backgroundColor: color }}
            />
          </div>
          <span className="text-xs">{signal.score}</span>
        </div>
      </td>
      <td className="py-2 px-3 tabular-nums text-right">
        {signal.price_chf != null ? `CHF ${fmt(signal.price_chf)}` : '—'}
      </td>
      <td className={`py-2 px-3 tabular-nums text-right ${pctColor(signal.price_change_24h_pct)}`}>
        {fmtPct(signal.price_change_24h_pct)}
      </td>
      <td className={`py-2 px-3 tabular-nums text-right ${pctColor(signal.price_change_7d_pct)}`}>
        {fmtPct(signal.price_change_7d_pct)}
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.rsi_14.toFixed(1)}
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.volatility_30d_pct.toFixed(1)}%
      </td>
      <td className="py-2 px-3 tabular-nums text-right text-muted-foreground">
        {signal.correlation_smi_1y.toFixed(2)}
      </td>
      <td className="py-2 px-3">
        <SignalSparkline data={history} />
      </td>
      <td className="py-2 px-3">
        <CryptoChartSheet ticker={signal.ticker} signal={signal} />
      </td>
    </tr>
  );
```

- [ ] **Step 2: crypto-client.tsx — neuen `<th>` im Tabellen-Header ergänzen**

In `frontend/app/crypto/crypto-client.tsx` die `<thead>`-Zeile (aktuell Zeilen 107–118) anpassen. Den letzten `<th>` „14d Trend" belassen und danach einen neuen `<th>` hinzufügen:

```tsx
                  <tr className="border-b border-border/40 text-muted-foreground">
                    <th className="text-left py-2 px-3 font-medium">Asset</th>
                    <th className="text-left py-2 px-3 font-medium">Signal</th>
                    <th className="text-left py-2 px-3 font-medium">Score</th>
                    <th className="text-right py-2 px-3 font-medium">Preis</th>
                    <th className="text-right py-2 px-3 font-medium">24h</th>
                    <th className="text-right py-2 px-3 font-medium">7d</th>
                    <th className="text-right py-2 px-3 font-medium">RSI</th>
                    <th className="text-right py-2 px-3 font-medium">Vola</th>
                    <th className="text-right py-2 px-3 font-medium">SMI-Korr</th>
                    <th className="text-left py-2 px-3 font-medium">14d Trend</th>
                    <th className="text-left py-2 px-3 font-medium">Chart</th>
                  </tr>
```

- [ ] **Step 3: Bestehende CryptoProRow-Tests noch grün?**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/crypto/__tests__/CryptoProRow.test.tsx
```

Erwartete Ausgabe: `4 passed`

Falls Tests rot: Die `makeSignal`-Hilfsfunktion in `CryptoProRow.test.tsx` prüfen — `CryptoChartSheet` triggert einen `useCryptoHistory`-Query, der in Tests mit `retry: false` ohne Mock einfach leer bleibt und keinen Fehler wirft.

- [ ] **Step 4: Alle Crypto-Tests auf grün**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run components/crypto/
```

Erwartete Ausgabe: alle Tests bestanden (mind. 13 Tests: 4 CryptoProRow + 3 SignalSparkline + 4 CryptoAgentPanel + 5 CryptoHistoryChart + 5 CryptoChartSheet)

- [ ] **Step 5: Commit**

```bash
git add frontend/components/crypto/CryptoProRow.tsx \
        frontend/app/crypto/crypto-client.tsx
git commit -m "feat(crypto): wire CryptoChartSheet into pro-mode table"
```

---

## Task 5: Gesamttest + PR

**Files:** Keine neuen Dateien

- [ ] **Step 1: Komplette Vitest-Suite grün**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx vitest run
```

Erwartete Ausgabe: alle Tests bestanden, keine Fehler

- [ ] **Step 2: TypeScript-Check**

```bash
cd /Users/andreapetretta/prisma-v2/frontend
npx tsc --noEmit
```

Erwartete Ausgabe: keine Fehler

- [ ] **Step 3: Dev-Server starten + manuell prüfen**

```bash
# Terminal 1 — Backend
cd /Users/andreapetretta/prisma-v2
source .venv/bin/activate && uvicorn backend.interfaces.rest.app:app --reload

# Terminal 2 — Frontend
cd /Users/andreapetretta/prisma-v2/frontend
npm run dev
```

Checkliste im Browser (`http://localhost:3000/crypto`):
- [ ] Pro Mode zeigt neue „Chart"-Spalte in der Tabelle
- [ ] Klick auf Chart-Button öffnet Sheet von rechts
- [ ] Sheet-Header zeigt Ticker + Signal-Badge + Name
- [ ] „📊 Chart"-Tab ist aktiv: zwei gestapelte Charts (Preis/Score oben, RSI/F&G unten)
- [ ] Pattern-Marker (orange Punkte) sichtbar wenn `detected_patterns` vorhanden
- [ ] Zeitraum-Buttons 7T / 30T / 90T wechseln die Daten
- [ ] „✦ KI-Analyse"-Tab zeigt CryptoAgentPanel mit Patterns + Text + Button
- [ ] Sheet schliessbar via ✕ oder Klick daneben
- [ ] Simple Mode unverändert (keine Chart-Buttons)

- [ ] **Step 4: PR erstellen**

```bash
git push -u origin feat/crypto-chart-sheet
gh pr create \
  --base main \
  --title "feat(crypto): CryptoChartSheet — visuelle Chartanalyse im Pro Mode" \
  --body "$(cat <<'EOF'
## Summary
- Neues `CryptoChartSheet`: Sheet mit Tab-Navigation (Chart + KI-Analyse)
- Neues `CryptoHistoryChart`: Recharts mit Preis/Score/RSI/Fear&Greed + Pattern-Markern
- Shadcn Tabs installiert
- `CryptoProRow` und Tabellen-Header um Chart-Spalte erweitert

## Test plan
- [ ] `npx vitest run` — alle Tests grün
- [ ] `npx tsc --noEmit` — keine TypeScript-Fehler
- [ ] Manueller Test: Chart-Button öffnet Sheet, beide Tabs funktionieren, Zeitraum-Selector wechselt Daten

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
