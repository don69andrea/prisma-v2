# PRISMA V4 — Projektplan: Erklärbares Krypto-Signal-System mit Agentic AI

**Autor:** Andrea Petretta · **Modul:** FHNW BI FS 2026 (Dozent: Renold) · **Repo:** `don69andrea/prisma-v2`
**Stand:** 2026-06-21 · **Schwester-Dokument:** `PRISMA_V4_AGENTS.md` (Agent-Orchestrierung)
**Grundlage:** `PRISMA_V35_MASTERPLAN.md` (Vision + Machbarkeitsbeweis), `PRISMA_V3_*` (Negativbefund-Doku)

> ⚠️ **Disclaimer:** Kein Finanzrat, keine Profit-Garantie. PRISMA ist ein erklärbares
> Entscheidungs**unterstützungs**-System, kein automatischer Trade-Executor. Alle Backtests sind
> *Evidenz für die Methodik*, kein Versprechen zukünftiger Renditen. Vor realem Einsatz: Paper-Trading
> über mindestens einen vollen Marktzyklus.

---

## 0 · Projekt-Status & Kontext (für künftige Sessions — statt privatem Gedächtnis)

> Dieser Block ersetzt eine „Projekt-Notiz". Er hält den aktuellen Stand fest, damit jede neue Session (oder
> jeder Coding-Agent) den Kontext aus dem Repo lädt — nicht aus jemandes Erinnerung.

**Wo wir stehen (Juni 2026):** V3 hat sauber bewiesen, dass direkte Return-Vorhersage keinen robusten Edge
liefert (In-Sample-Optimismus als Kernlehre). **V4 ist der Pivot:** weg vom Return-Raten, hin zu einem
erklärbaren 3-Schichten-Signal-System (WAS/WANN/WIEVIEL) auf **Krypto-Spot** als Kern-Universum.

**Bewusste Kehrtwenden ggü. V2 (begründet, falls der Dozent fragt):**
- „nie SELL" → **SELL erlaubt** (= raus/cash, **kein** Shorting).
- „kein Spot-Krypto" (galt für 3a-Eligibility) → **Spot-Krypto ist jetzt das Kern-Universum**; SMI/3a bleibt
  separates Anzeige-Universum.

**Belegte Machbarkeit (eigene Backtests, `prisma_v35_poc/`):** Vol ist lernbar (OOS-R² BTC 52 %); Indikator-
Konsens (2-von-3 MA+MACD+RSI) schlägt die exposure-matched Baseline (BTC Sharpe 1.50/Calmar 1.38) — der Test,
an dem V3-ML scheiterte.

**Nächster Bau-Schritt:** Phase V4-1 (Daten + Signal-Engine) — Detailplan in
`PRISMA_V4-1_PHASENPLAN_Signal-Engine.md`.

**Doku-Standorte:** Pläne → `docs/`; PoC-Skripte → `docs/research/` (oder `research/`); Agent-Brief
`PRISMA_V4_AGENTS.md` wird zusätzlich an GSD/Claude Code übergeben.

---

## 1 · Worum es geht (Executive Summary)

V3 hat sauber bewiesen: **Returns direkt vorhersagen funktioniert nicht.** V4 dreht die Logik um. Statt den
Kurs zu erraten, baut PRISMA ein **transparentes, dreischichtiges Signal-System**, das genau das tut, was gute
Trader tun — nur regelbasiert, kombiniert und ehrlich nachgerechnet:

1. **WAS** handeln → Faktoren/Kandidaten-Ranking (cross-sectional Momentum, On-Chain-Health)
2. **WANN** rein/raus → **Chart-Indikatoren im Konsens** (MA + MACD + RSI), Meta-Labeling filtert schlechte Trades
3. **WIE VIEL** → **Volatilitäts-Prognose** steuert die Positionsgrösse (Vol-Targeting)

Darüber liegt eine **Agentic-AI-Schicht** (im Schwester-MD detailliert): spezialisierte LLM-Agenten, die die
Zahlen der Signal-Engine *interpretieren, gegeneinander debattieren und erklären* — nach dem Vorbild des
**TradingAgents**-Frameworks (Analyst-Team → Bull/Bear-Research → Trader → Risk-Team).

**Das Ergebnis sind erklärbare BUY / HOLD / SELL-Signale** (SELL = raus/cash, kein Shorting), jeweils mit
Begründung pro Schicht — exakt die Erklärbarkeit, die das BI-Modul (STRESSS/AI-in-the-Loop) belohnt.

**Universum-Entscheidung V4:** **Krypto-Spot als Kern** (BTC/ETH + Top-10). Dies *revidiert bewusst* die
V2-Entscheidung „Spot-Krypto: Nein" — begründet durch: deutlich mehr Daten (24/7 seit 2017), stärkeres
Momentum/Vol (besser lernbar), beste Gratis-Datenlage, kein Fundamental-Daten-Engpass. Die bestehende
SMI/3a-Funktionalität bleibt als sekundäres Anzeige-Universum erhalten (kein Rückbau).

---

## 2 · Was die Daten sagen (Evidenz, auf der V4 steht)

Alle Zahlen auf echten Gratis-Daten (yfinance, BTC/ETH täglich ~9.5 J., netto 0.1 % Kosten, Signale
1 Tag verzögert, **keine Parameter-Optimierung**). Skripte: `prisma_v35_poc/`.

**(A) Volatilität ist lernbar** — OOS-R² gegen konstante Baseline: **BTC +52 %, ETH +31 %**. Das erste
*positive* ML-Ziel des Projekts (Sizing-Baustein).

**(B) Trend + Vol-Targeting schlägt die harte Baseline** — BTC Calmar **1.31** vs exposure-matched 0.60 vs
Buy&Hold 0.66; Drawdown −83 % → −49 %. Robust über 9/10 Trend-Fenster (kein Cherry-Picking). Genau der Test,
an dem das alte Return-ML zerbrach (V3 Durchlauf 4: 0.35 < 0.66).

**(C) Welche Chart-Indikatoren wirklich helfen** (long/flat, netto, Ø-Investitionsquote ~50–55 %):

| Indikator (BTC) | Sharpe | Calmar | MaxDD | schlägt Exposure-Matched? |
|---|---|---|---|---|
| **COMBO_VOTE (2 v. 3: MA+MACD+RSI)** | **1.50** | **1.38** | −57.9 % | **JA** |
| RSI>50 | 1.42 | 1.13 | −65.8 % | JA |
| MA(100) | 1.29 | 1.10 | −61.4 % | JA |
| MACD | 1.23 | 1.15 | −51.3 % | JA |
| Bollinger (Mittelband) | 1.27 | 0.95 | −64.6 % | JA |
| Buy & Hold | 0.99 | 0.66 | −83.4 % | — |

Auf ETH dasselbe Bild (Bollinger dort am stärksten, Sharpe 0.98). **Kernlehre, deckt sich mit der Forschung:**
Kein Einzelindikator trägt allein zuverlässig — **die Kombination (Konsens-Voting) gewinnt**. Genau diese
Konsens-Logik bilden wir später mit den Agenten ab.

> Ehrliche Grenzen: Tagesdaten, je 1 Asset, fixe Parameter, long/flat. Krypto's grosser Bull-Trend schmeichelt
> Trend-Folge. Das ist **gerichtete Evidenz, kein Zukunftsbeweis** — deshalb der strenge Walk-Forward in V4.

---

## 3 · Mapping auf die Modulvorgaben (Renold)

V4 erfüllt jede Vorgabe — und zwar *stärker* als V3, weil jetzt auch ein **positiver** ML-Befund dabei ist.

| Modulvorgabe | Umsetzung in V4 | Nachweis fürs Begleitdokument |
|---|---|---|
| **ML-basiert** | (1) Vol-Prognose-Modell (positiv, OOS-R² 52 %) → Sizing. (2) Meta-Labeling-Klassifikator (López de Prado): „funktioniert das Trend-Signal jetzt?". (3) Dokumentierter, ehrlicher Negativbefund zu Returns. | Walk-Forward-Reports, Baselines, In-Sample-Optimismus-Lehre |
| **Agentic AI** | Multi-Agent-System (Director + Analyst-/Research-/Risk-Agenten) nach TradingAgents-Vorbild; LLM-Tool-Use, Bull/Bear-Debatte, Checkpoint-HITL, Memory/Trust-Scores. | `PRISMA_V4_AGENTS.md`, Audit-Trail im UI |
| **RAG** | News-/Sentiment-RAG fliesst als **Feature/Veto** in Schicht 2 (nicht nur Anzeige): Sentiment-Score je Coin/Tag steuert mit. | RAG→Feature→Signal-Pfad, messbarer Einfluss |
| **Datensatz (hist. + live)** | Krypto-OHLCV seit 2017 (Tag→Minute), On-Chain (Coin Metrics), Makro (FRED), Fear&Greed; live via yfinance/Exchange-REST. | Coverage-Gate, PIT-Garantie |
| **Erklärbarkeit / AI-in-the-Loop (STRESSS)** | Jedes Signal zeigt Begründung pro Schicht + Agent-Reasoning-Kette + Konfidenz + Audit-Trail; Checkpoint-Pattern für Human-in-the-Loop. | Dashboard-Explainability-Panel |

---

## 4 · Zielarchitektur V4 (Daten → Signal → Agenten → UI)

```
┌──────────────────────────────────────────────────────────────────────┐
│ DATEN-LAYER (deterministisch, point-in-time)                          │
│  OHLCV (yfinance/CryptoDataDownload/Kraken) · On-Chain (Coin Metrics) │
│  · Makro (FRED) · Fear&Greed · News-Korpus (pgvector)                 │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ SIGNAL-ENGINE (deterministisch, getestet — KEINE LLM-Zahlen!)         │
│  Schicht 1 WAS : Faktor-Ranking (X-sect. Momentum, On-Chain)          │
│  Schicht 2 WANN: Indikator-Konsens (MA+MACD+RSI Vote) + Meta-Label-ML │
│  Schicht 3 WIEVIEL: Vol-Forecast-ML → Vol-Targeting, DD-Bremse        │
│  → roher Signal-Vektor je Coin: {direction, size, sub-scores}         │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ AGENTIC-LAYER (LLM — interpretiert/erklärt/debattiert, rechnet NICHT) │
│  Technical/Sentiment/OnChain/Macro-Analyst → Bull vs Bear Research     │
│  → Signal-Director (Synthese) → Risk-Agent (Veto/Sizing-Cap)          │
│  → strukturierter, Pydantic-validierter Output                        │
└───────────────┬──────────────────────────────────────────────────────┘
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│ UI / DASHBOARD                                                        │
│  BUY/HOLD/SELL je Coin · Größe · Begründung pro Schicht · Konfidenz   │
│  · Chart mit Indikatoren · Backtest-Equity · Audit-Trail              │
└──────────────────────────────────────────────────────────────────────┘
```

**Das Wichtigste an dieser Trennung (aus der Forschung gelernt):** LLM-Agenten **halluzinieren** Finanzzahlen.
Deshalb gilt eiserne Regel: *Alle Zahlen kommen aus der deterministischen Signal-Engine bzw. aus Tools.* Die
Agenten **interpretieren und begründen** nur — sie erfinden nie einen Score, einen Preis oder eine Position.
Das deckt sich exakt mit eurer bestehenden Regel „kein LLM-Freitext ins Frontend, alles Pydantic".

---

## 5 · Was neu gebaut werden muss (Komponenten)

### 5.1 Daten (erweitern, nicht neu)
- **Krypto-Universum Top-10** (BTC, ETH, SOL, BNB, XRP, ADA, AVAX, DOGE, LINK, DOT) in `crypto_price_history`.
- **On-Chain-Adapter (Coin Metrics Community)** breiter: MVRV-Z, Realized Cap, aktive Adressen, Tx-Volumen.
- **Fear&Greed-Adapter** (alternative.me, historisch) — als Feature & Sentiment-Anker.
- **Minuten-Daten-Option** (Kraken-Archive/CryptoDataDownload) für robustere Vol-Schätzung (später).

### 5.2 Signal-Engine (Kern-Neubau) — `backend/application/signals/`
- **`indicators.py`** — MA/MACD/RSI/Bollinger/ATR, vektorisiert, getestet (Referenz: bestehende Werte).
- **`consensus.py`** — Konsens-Voting (2-von-3) + konfigurierbare Gewichte → Schicht-2-Roh-Signal.
- **`vol_forecast.py`** — Vol-Modell (HAR-Baseline → LightGBM), Walk-Forward, liefert Sizing-Faktor.
- **`meta_label.py`** — Triple-Barrier/Trend-Scanning-Labels + Klassifikator „Trade ja/nein".
- **`sizing.py`** — Vol-Targeting, Position-Caps, Drawdown-Bremse → Schicht 3.
- **`signal_service.py`** — orchestriert Schicht 1–3, gibt `SignalVector` (Pydantic) je Coin aus.

### 5.3 Backtest-Engine (härten) — `backend/application/backtest/`
- Strikter **Expanding-Window Walk-Forward**, **exposure-matched Baseline**, Netto-Kosten, Slippage-Modell.
- Pflicht-Outputs: Equity-Kurve, Sharpe/Calmar/MaxDD, Trade-Liste, Per-Fold-Tabelle, Konfidenzintervalle.
- **Look-Ahead-Guard** als Test (Signal darf nie t-Daten verwenden).

### 5.4 Agentic-Layer (Schwester-MD) — `backend/application/agents/`
- Neue Signal-Analyst-Agenten + Bull/Bear-Research + Risk-Agent; Anpassung von Director, Macro, Crypto, Report.

### 5.5 UI (anpassen) — `frontend/`
- Krypto-Signal-Dashboard, Indikator-Charts, Explainability-Panel, Backtest-View, Audit-Trail (Details §7).

---

## 6 · Tests, die wir machen müssen (Qualitäts-Gate)

Die methodische Strenge ist euer Markenzeichen — sie bleibt der Kern.

**A. Unit-Tests (Korrektheit)**
- Indikatoren gegen Referenzwerte (z. B. RSI/MACD vs. `ta`-Lib auf Sample) — Abweichung < 1e-6.
- Look-Ahead-Guard: jeder Feature/Signal-Wert an t nutzt nur Daten ≤ t−1 (automatischer Shift-Check).
- Pydantic-Schema-Validierung aller Agent-Outputs (kein Freitext).

**B. Statistische ML-Tests (Ehrlichkeit)**
- **Strikter Walk-Forward** (Expanding Window) für Vol-Modell & Meta-Label — die finale Aussage.
- **Pflicht-Baselines**: Buy&Hold, Mehrheitsklasse, Momentum-only, **Exposure-Matched**.
- **Netto nach Kosten** (Krypto ~0.1–0.5 % RT) + Slippage-Sensitivität.
- **Parameter-Robustheit** (mehrere Fenster) statt Einzel-Cherry-Pick — wie im PoC gezeigt.
- **Konfidenzintervalle / Anzahl unabhängiger Trades** explizit ausweisen (N-Power-Ehrlichkeit).

**C. Agent-Tests (Verlässlichkeit, aus der LLM-Agent-Forschung)**
- **Halluzinations-Guard**: Agent-Output-Zahlen müssen exakt den Engine-Zahlen entsprechen (Diff-Test).
- **Portfolio-State-Test**: Position kommt aus Tool/Store, nie aus LLM-Memory (epistemische Halluzination).
- **Konsens-Bias-Test**: Bull/Bear-Debatte darf korrekte Minderheitsmeinung nicht systematisch unterdrücken.
- **Fallback-Test**: LLM-Ausfall → deterministisches Engine-Signal bleibt gültig.

**D. Integration / E2E**
- Daten → Signal → Agent → UI Durchstich; Playwright-Smoke fürs Dashboard.
- Coverage-Gate ≥ 80 % (bestehende Regel).

---

## 7 · UI-Anpassungen (konkret)

Bestehendes Dashboard war SMI/3a (BUY/HOLD/WATCH, „nie SELL"). V4 erweitert auf Krypto mit echtem SELL
(= raus/cash, **kein** Shorting — klar im UI kommuniziert).

**Neue/angepasste Views:**

1. **Signal-Übersicht (Krypto-Watchlist)** — Tabelle je Coin: Signal-Badge (🟢 BUY / ⚪ HOLD / 🔴 SELL),
   empfohlene Größe (z. B. „0.8× Vol-Target"), Konfidenz, Mini-Sparkline. Sortierbar nach Stärke.
2. **Coin-Detail mit Explainability-Panel** — *die Kernansicht fürs Modul*. Pro Schicht eine Zeile:
   - Schicht 1 (WAS): „Momentum-Rang 2/10, On-Chain MVRV neutral"
   - Schicht 2 (WANN): „Konsens 3/3 (MA✓ MACD✓ RSI✓), Meta-Label: Trade OK"
   - Schicht 3 (WIEVIEL): „Vol erwartet 55 % → Größe 0.8×"
   - **Agent-Reasoning-Kette** (Bull-/Bear-Argumente, Risk-Veto) als aufklappbarer Audit-Trail.
3. **Chart-View mit Indikatoren** — Candlesticks + MA/MACD/RSI/Bollinger overlay; Signal-Marker (Ein-/Ausstieg)
   direkt im Chart (die „visuelle Chart-Analyse", die du wolltest).
4. **Backtest-Panel** — Equity-Kurve Strategie vs Buy&Hold vs Exposure-Matched, Kennzahlen, Drawdown-Chart.
   Macht die Ehrlichkeit *sichtbar*.
5. **Konfidenz & Disclaimer** — sichtbarer Hinweis „Entscheidungsunterstützung, kein Anlagerat" + Konfidenz-Quelle.
6. **Checkpoint/HITL** — bei niedriger Konfidenz oder grossem Sizing-Schritt fragt der Director im UI nach
   (bestehendes Checkpoint-Pattern wiederverwenden).

**Technik:** Next.js 14 bestehend; neue Komponenten `CryptoSignalTable`, `ExplainabilityPanel`,
`IndicatorChart` (z. B. lightweight-charts/Recharts), `BacktestPanel`. Alle Daten aus typisierten API-Endpunkten
(OpenAPI-generierte Typen, keine `any`).

---

## 8 · Roadmap (Phasen, je benotbar, risikoarm)

**Branch-Workflow (verbindlich, aus der Repo-`AGENTS.md`): `feature/* → develop → main`.** Jede Phase läuft auf
einem `feat/*`-Branch und wird per PR nach **`develop`** gemerged (develop = Integration, geschützt). `main`
(Production, geschützt) wird **nur beim Release** aus develop aktualisiert — siehe Phase V4-7. CI muss grün sein.
Umsetzung über **GSD** (`/gsd-plan-phase` → `/gsd-execute-phase` → `/gsd-verify-work` → `/gsd-ship`).

| Phase | Inhalt | Ergebnis / Benotbarkeit |
|---|---|---|
| **V4-0 Daten** | Top-10-Krypto-Universum, Coin-Metrics-/Fear&Greed-Adapter, Coverage-Gate | sauberer PIT-Datensatz (live+hist) |
| **V4-1 Signal-Engine** | Indikatoren + Konsens-Voting + Vol-Forecast + Sizing, Backtest-Härtung | **erster positiver ML-Befund**, ehrliche Backtests |
| **V4-2 Meta-Labeling** | Triple-Barrier/Trend-Scan-Labels + Klassifikator, gegen „immer-traden" getestet | ML-Filter-Schicht, Methodik-Nachweis |
| **V4-3 Agentic-Layer** | Analyst-/Bull-Bear-/Risk-Agenten, Director-Synthese, Halluzinations-Guards | **Agentic-AI-Vorgabe** voll erfüllt |
| **V4-4 RAG-Sentiment** | News/Fear&Greed → Sentiment-Feature/Veto in Schicht 2 | **RAG-Vorgabe** funktional erfüllt |
| **V4-5 UI** | Signal-Dashboard, Explainability, Chart-Indikatoren, Backtest-Panel | sichtbare, benotbare Krönung |
| **V4-6 Begleitdoku** | Negativ- + Positivbefund + Methodik für den Dozenten | starke wissenschaftliche Story |
| **V4-7 Release → `main`** | **Abschluss-Release.** Wenn V4-1…V4-6 auf `develop` integriert & grün sind: Release-PR `develop → main`, CI grün, Tag `v4.0`. In GSD via `/gsd-complete-milestone`. | vorzeig-/abgabefähiger Production-Stand auf `main` |

**Empfohlene Reihenfolge:** V4-0 → V4-1 zuerst (liefert den positiven Befund + die Engine, auf der alles
aufbaut). V4-3 (Agenten) und V4-5 (UI) danach, weil sie auf den Engine-Outputs sitzen. **V4-7 (Release nach
`main`) ist der letzte Schritt** — erst wenn der Meilenstein steht (spätestens vor der Modul-Abgabe), nicht nach
jeder Einzelphase. Faustregel: `main` = jederzeit vorzeig-/abgabefähig, `develop` = woran gerade gebaut wird.

---

## 9 · Risiken & ehrliche Erwartungen

- **Overfitting/In-Sample-Optimismus** bleibt der Hauptfeind → strikter Walk-Forward, Baselines, feste Parameter.
- **LLM-Halluzination** → Agenten rechnen nie selbst; Zahlen aus Engine/Tools, Diff-Guards in Tests.
- **Regimewechsel**: Trend-Folge hat lange Durststrecken (Bullenjahre/Whipsaws); Vorteil ist *zyklusweit* & im Risiko.
- **Live ≠ Backtest**: Slippage, Ausfälle, Gebühren. Vor echtem Kapital: Paper-Trading.
- **Realistische Renditeerwartung**: seriöse Quant-Fonds zielen auf 15–25 % p. a.; alles „100 %+ garantiert" ist
  ein Warnsignal. PRISMA ist Entscheidungsunterstützung, kein Geldautomat.

---

## 10 · Sofort-nächster Schritt

**Phase V4-0 + V4-1 starten.** Top-10-Universum seeden, Signal-Engine (Indikator-Konsens + Vol-Forecast +
Sizing) bauen und ehrlich walk-forward backtesten. Das liefert den ersten positiven ML-Befund und die Basis für
Agenten + UI. Übergabe an GSD/Sub-Agenten gemäss `PRISMA_V4_AGENTS.md`.

---

### Quellen
- TradingAgents (Multi-Agent-LLM-Trading): https://arxiv.org/abs/2412.20138 · https://github.com/TauricResearch/TradingAgents
- LLM-Agent-Grenzen/Halluzination: https://arxiv.org/html/2605.19337v1 · https://arxiv.org/pdf/2512.02261
- Triple-Barrier/Trend-Scanning Krypto 2025: https://link.springer.com/article/10.1186/s40854-025-00866-w
- Indikator-Kombination (MACD+RSI): https://web3.gate.com/crypto-wiki/article/how-to-use-macd-rsi-and-bollinger-bands-to-predict-crypto-price-movements-in-2025-20260127
- TA-Profitabilität (ehrlich): https://farmdoc.illinois.edu/assets/marketing/agmas/AgMAS04_04.pdf
- Gratis-Daten: https://www.cryptodatadownload.com/data/ · Coin Metrics Community API
- Eigene Backtests: `prisma_v35_poc/` (poc_feasibility.py, indicator_backtest.py)

*PRISMA V4 Projektplan · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
