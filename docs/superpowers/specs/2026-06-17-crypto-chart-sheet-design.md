# Design: CryptoChartSheet — Visuelle Chartanalyse im Pro Mode

**Datum:** 2026-06-17  
**Autor:** Andrea Petretta  
**Status:** Approved  

---

## IST-Zustand

### Was existiert

Die Krypto-Seite (`/crypto`) hat zwei Modi:

**Simple Mode:** Top-3 BUY-Signale als `CryptoSignalCard`-Grid.

**Pro Mode:** Vollständige Tabelle aller 10 unterstützten Assets (`CryptoProRow`) mit:
- Ticker, Signal-Badge, Score-Balken, Preis CHF, 24h/7d-Änderung, RSI, Volatilität, SMI-Korrelation
- 14-Tage-Sparkline (kleines SVG, Score-Verlauf) am Zeilenende
- Darunter für Top-5: `ScoreBreakdown` (Accordion) + `CryptoAgentPanel`

**`CryptoAgentPanel`** (die zentrale bestehende Komponente):
- Zeigt erkannte Chart-Patterns als farbige Badges (bullish = grün, bearish = rot)
- Streamt on-demand eine 2-Satz-KI-Analyse via SSE (`/api/v1/crypto/analyze/{ticker}`)
- Zeigt gecachten `agent_analysis`-Text aus dem letzten täglichen Snapshot
- Hat einen „Neu analysieren"-Button

### Datenlage (bereits vorhanden)

| Endpoint | Daten | Bereits in Frontend |
|---|---|---|
| `GET /api/v1/crypto/signals` | Alle 10 Signale inkl. `detected_patterns`, `agent_analysis` | ✅ |
| `GET /api/v1/crypto/history/{ticker}?days=N` | `date, signal, score, price_chf, fear_greed_value, rsi_14, detected_patterns, pattern_score` | ✅ via `useCryptoHistory` |
| `POST /api/v1/crypto/analyze/{ticker}` | SSE-Stream, KI-Analyse | ✅ via `useCryptoAgentAnalysis` |

### Schwachstelle

Die LLM-Textanalyse ist rein textuell. Die erkannten Patterns (z.B. `GOLDEN_CROSS`, `BULLISH_RSI_DIVERGENCE`) und der Score-Verlauf sind nur als Badges und winzige Sparkline sichtbar — kein interaktiver Chart mit Zeitachse, Preisline, Indikatoren und Pattern-Markern.

---

## SOLL-Zustand

### Ziel

Im Pro Mode erhält jede Tabellenzeile einen **„📊 Chart"-Button**, der ein **Shadcn Sheet** (Drawer) öffnet. Das Sheet zeigt Chart und KI-Analyse in **Tabs**, sodass es in Zukunft einfach um weitere Tabs erweiterbar ist.

### UI-Flow

```
Pro-Tabelle
  └── [Zeile: BTC · STRONG BUY · Score 84 · CHF 82'400 · …] [📊 Chart]
                                                                    │
                                                                    ▼
                                              Sheet öffnet sich (side on desktop, bottom on mobile)
                                              ┌─────────────────────────────────┐
                                              │ BTC  [STRONG BUY · 84]      [✕] │
                                              │─────────────────────────────────│
                                              │ [Chart]  [KI-Analyse]  [···]    │
                                              │─────────────────────────────────│
                                              │  ← Tab-Inhalt →                 │
                                              └─────────────────────────────────┘
```

### Tab-Struktur

| Tab | Inhalt | Datenquelle |
|---|---|---|
| **Chart** | `CryptoHistoryChart` (Preis+Score + RSI+F&G + Pattern-Marker) | `useCryptoHistory(ticker, 30)` |
| **KI-Analyse** | bestehender `CryptoAgentPanel` | `signal.detected_patterns`, `signal.agent_analysis`, SSE |
| **[Placeholder]** | Noch nicht implementiert — Tab disabled oder ausgeblendet | — |

---

## Architektur

### Komponentenbaum

```
CryptoProRow (bestehend — minimale Änderung)
  ├── [bestehender Tabelleninhalt]
  └── CryptoChartSheet ticker={signal.ticker} signal={signal}   ← NEU (Button + Sheet)
        └── Sheet (shadcn/ui)
              ├── SheetHeader
              │     ├── Ticker + Name
              │     └── Signal-Badge + Score
              └── Tabs (shadcn/ui)
                    ├── Tab "Chart"
                    │     └── CryptoHistoryChart ticker={ticker}   ← NEU
                    │           ├── Recharts ComposedChart         (Preis + Score)
                    │           └── Recharts LineChart             (RSI + Fear & Greed)
                    ├── Tab "KI-Analyse"
                    │     └── CryptoAgentPanel (bestehend, unverändert)
                    │           ticker={ticker}
                    │           detectedPatterns={signal.detected_patterns}
                    │           cachedAnalysis={signal.agent_analysis}
                    └── Tab "···" (disabled / ausgeblendet, Placeholder)
```

### Neue Dateien

```
frontend/components/crypto/
  ├── CryptoChartSheet.tsx   ← Sheet-Wrapper mit Tabs, Button-Trigger
  └── CryptoHistoryChart.tsx ← Recharts-Chart-Komponente
```

### Geänderte Dateien

```
frontend/components/crypto/
  └── CryptoProRow.tsx       ← „📊 Chart"-Button hinzufügen, CryptoChartSheet einbinden
```

### Keine Änderungen an

- `CryptoAgentPanel.tsx` — wird unverändert in den Sheet-Tab eingebettet
- `crypto-client.tsx` — keine Änderung
- `CryptoSignalCard.tsx`, `ScoreBreakdown.tsx`, `FearGreedGauge.tsx` — keine Änderung
- Backend — alle Endpoints existieren, null neue Routen

---

## CryptoChartSheet — Spezifikation

### Props

```typescript
interface CryptoChartSheetProps {
  ticker: string;
  signal: CryptoSignal;  // bereits in CryptoProRow vorhanden
}
```

### Verhalten

- Button `📊 Chart` am rechten Ende der Tabellenzeile (nach der Sparkline-Spalte)
- Öffnet Shadcn `Sheet` mit `side="right"` (auf allen Breakpoints — Shadcn Sheet hat kein automatisches Bottom-Drawer auf Mobile)
- Sheet-Breite: `sm:max-w-2xl` (640px auf Desktop) — gibt dem Chart genug Platz
- Tabs: Shadcn `Tabs` mit `defaultValue="chart"`
- Sheet verwaltet eigenen `open`-State intern (`useState`)

---

## CryptoHistoryChart — Spezifikation

### Props

```typescript
interface CryptoHistoryChartProps {
  ticker: string;
}
```

### Daten

Fetcht `useCryptoHistory(ticker, 30)` — liefert `CryptoHistoryPoint[]`:

```typescript
interface CryptoHistoryPoint {
  date: string | null;
  signal: string;           // für Farbe der Marker
  score: number;
  price_chf: number | null;
  fear_greed_value: number | null;
  rsi_14: number | null;
  detected_patterns: string[];
  pattern_score: number | null;
}
```

### Chart-Aufbau (zwei gestapelte Recharts-Instanzen)

**Oberes Chart — Preis + Score (`ComposedChart`, Höhe 200px):**

| Element | Recharts-Typ | Daten | Farbe |
|---|---|---|---|
| Preisverlauf CHF | `Area` | `price_chf` | `#7ee787` (grün) |
| Score-Verlauf | `Line` (dashed) | `score` | `#58a6ff` (blau), sekundäre Y-Achse rechts |
| Pattern-Marker | `ReferenceDot` pro Eintrag mit `detected_patterns.length > 0` | — | `#ffa657` (orange) |

- Linke Y-Achse: Preis CHF
- Rechte Y-Achse: Score 0–100
- X-Achse: `date` (formatiert `dd.MM`)
- `Tooltip` zeigt: Datum, Preis CHF, Score, Signal, erkannte Patterns

**Unteres Chart — RSI + Fear & Greed (`ComposedChart`, Höhe 100px):**

| Element | Recharts-Typ | Daten | Farbe |
|---|---|---|---|
| RSI (14) | `Line` | `rsi_14` | `#bc8cff` (lila) |
| Fear & Greed | `Line` | `fear_greed_value` | `#ffa657` (orange), sekundäre Y-Achse |
| Overbought-Zone (70) | `ReferenceLine` | `y=70` | rot, gestrichelt |
| Oversold-Zone (30) | `ReferenceLine` | `y=30` | grün, gestrichelt |

- Y-Achse: 0–100 (beide Indikatoren gleiche Skala)
- Kein eigenes Tooltip, wird vom oberen Chart synchronisiert

**Zeitraum-Selector:** Drei Buttons `7T / 30T / 90T` über dem Chart (steuert `days`-Prop von `useCryptoHistory`). Default: 30T.

### Edge Cases

- Weniger als 2 Datenpunkte → Placeholder-Text: „Noch keine ausreichende Historie für diesen Ticker."
- `price_chf` ist `null` für einzelne Punkte → Recharts `connectNulls={false}` (Lücke im Chart)
- Ladestate: Shadcn `Skeleton` mit gleicher Höhe wie der Chart

---

## CryptoProRow — Änderung

Minimale Änderung: Neuer Button am Ende der Zeile + Sheet einbinden.

```tsx
// Neue letzte Spalte in der Tabellenzeile:
<td className="py-2 px-3">
  <CryptoChartSheet ticker={signal.ticker} signal={signal} />
</td>
```

Entsprechend neue `<th>` im Header in `crypto-client.tsx`:
```tsx
<th className="text-left py-2 px-3 font-medium">Chart</th>
```

---

## Bestehender ScoreBreakdown + CryptoAgentPanel im Pro Mode

Die bestehende Sektion (Score-Aufschlüsselung + KI-Agent-Panel unterhalb der Tabelle, aktuell für Top-5) **bleibt vorerst erhalten**. Sie ist redundant zum neuen Sheet-Tab, aber eine spätere Aufräumung ist ein separater Task. Kein Breaking Change.

---

## Tests

**Unit-Tests (Vitest + Testing Library):**

| Datei | Was getestet |
|---|---|
| `CryptoChartSheet.test.tsx` | Button rendert, Sheet öffnet/schliesst, Tabs vorhanden |
| `CryptoHistoryChart.test.tsx` | Rendert Skeleton bei leerem Array, rendert Chart bei Daten, Zeitraum-Buttons wechseln `days` |

Beide Tests mocken `useCryptoHistory` (Query-Mock via `@tanstack/react-query`), kein echter API-Call.

**Kein Backend-Test nötig** — History-Endpoint existiert und ist bereits getestet (`test_crypto_endpoints.py`).

---

## Nicht im Scope

- On-Chain-Daten oder weitere Indikatoren (späterer Placeholder-Tab)
- Candlestick-Chart (Kurs-OHLCV — nicht in `CryptoHistoryPoint` vorhanden)
- Animierter Chart-Aufbau
- Chart-Export als PNG
- Entfernung der bestehenden `ScoreBreakdown` + `CryptoAgentPanel`-Sektion unterhalb der Tabelle

---

## Abhängigkeiten

- `recharts ^2.12.0` — bereits installiert, bereits in `PriceChart.tsx` genutzt
- `shadcn/ui Sheet` — bereits in Projekt vorhanden (`components/ui/sheet.tsx`)
- `shadcn/ui Tabs` — **nicht vorhanden**, muss installiert werden: `npx shadcn-ui@latest add tabs`
