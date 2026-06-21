# PRISMA V4 — Agent-Orchestrierung & Sub-Agent-Brief

**Zweck:** Verbindlicher Bau- und Verhaltensbrief für die Agentic-AI-Schicht von PRISMA V4 — welche Agenten
buy/hold/sell **unterstützen**, welche **neu** gebaut und welche bestehenden **angepasst** werden.
**Adressat:** Du (Orchestrator) + die GSD-Sub-Agenten, die diesen Brief ausführen.
**Schwester-Dokument:** `PRISMA_V4_PROJEKTPLAN.md` · **Bestand:** `PRISMA_V2_AGENTS.md`, `PRISMA_MultiAgent_Revised.md`
**Stand:** 2026-06-21

> Dieser Brief erbt **alle goldenen Regeln** aus `PRISMA_V2_AGENTS.md` (Spec-First, kein Merge ohne grüne CI,
> kein direkter Push auf main/develop, Pydantic-Pflicht, Test-First für Domain-Code). Er ergänzt sie um die
> Agentic-Signal-Schicht. Bei Konflikt gilt die strengere Regel.

---

## 0 · Die eine eiserne Regel der Agentic-Schicht

**LLM-Agenten rechnen NICHTS aus. Sie interpretieren, debattieren und begründen — auf Basis von Zahlen, die
ausschliesslich aus der deterministischen Signal-Engine oder aus Tools kommen.**

Begründung (aus der Forschung, nicht Meinung): LLM-Trading-Agenten **halluzinieren** Finanzmetriken und
„vergessen" Portfolio-Zustände (epistemische Halluzination → „strategische Lähmung"). Jede Kennzahl, jeder
Preis, jede Position MUSS aus einem Tool/Store kommen und wird Pydantic-validiert. Ein Agent, der einen Score
erfindet, ist ein Bug. Tests erzwingen das (Halluzinations-Guard, siehe §6).

Das ist die natürliche Erweiterung eurer bestehenden Regel „kein LLM-Freitext ins Frontend".

---

## 1 · Vorbild: TradingAgents — warum Multi-Agent für Signale hilft

Das **TradingAgents**-Framework (Tauric Research, arXiv 2412.20138) zeigt empirisch: Ein Team spezialisierter
LLM-Agenten schlägt Single-Model-Baselines bei kumulativem Return, Sharpe und Max-Drawdown — *weil die
Aufgabenteilung Single-Model-Bias reduziert*. Struktur dort: **Analyst-Team** (Fundamental/Sentiment/Technical/
News) → **Research-Team** (Bull vs Bear Debatte) → **Trader** → **Risk-Team** → **Fund-Manager**.

**Wie das buy/hold/sell *unterstützt* (der Mehrwert für PRISMA):**
1. **Mehrere Perspektiven statt einer Box** — Technical, On-Chain, Macro, Sentiment werden getrennt bewertet und
   dann zusammengeführt; das reduziert Einseitigkeit gegenüber einem monolithischen Score.
2. **Bull/Bear-Debatte = eingebauter Advocatus Diaboli** — zwingt das System, Gegenargumente zu prüfen, bevor
   ein Signal steht. Das ist die agentische Entsprechung des „Konsens-Votings" aus den Indikatoren.
3. **Risk-Agent als Veto** — eigene Instanz prüft das Signal gegen Drawdown/Vol-Limits, bevor es ins UI geht.
4. **Erklärbarkeit** — jeder Agent liefert seine Begründung → die Reasoning-Kette ist der Audit-Trail fürs Modul.

**Ehrliche Grenze (auch aus Forschung):** Konsens-Mechanismen können *korrekte Minderheitsmeinungen
unterdrücken*, gerade in schnellen/datenarmen Regimes. Gegenmittel: Risk-Agent darf ein einstimmiges Bull-Votum
overrulen; Minderheits-Argumente werden im Audit-Trail *immer* protokolliert (nicht weggemittelt).

---

## 2 · Bestehende Agenten — was bleibt, was sich ändert

| Agent (Bestand) | Heutige Rolle | Anpassung in V4 |
|---|---|---|
| **InvestmentDirector** | Orchestrator, Tool-Use + Checkpoint-HITL | → **SignalDirector**: orchestriert die neue Analyst→Research→Risk-Kette; Synthese der Schicht-1–3-Engine-Outputs zu BUY/HOLD/SELL. Checkpoint-Pattern bleibt. |
| **SteuerAgent** | Gold-Standard (RAG+LLM+Pydantic+Fallback) | bleibt **unverändert** als Referenz-Pattern für alle neuen Agenten. SMI/3a-Kontext behalten. |
| **MacroAgentV2** | LLM-Tool-Use Makro-Reasoning | → **MacroRegimeAgent**: zusätzliche Krypto-relevante Tools (US-Realzins, DXY, globale Liquidität, BTC-Korrelation zu Risk-Assets). Liefert Regime-Kontext für die Krypto-Signale. |
| **PortfolioAgent / DeltaAgent** | Markowitz + Delta-Umschichtung | bleibt; wird von der **Sizing-Schicht** gespeist (Vol-Targeting-Gewichte statt nur Ranking). Krypto-Caps ergänzen. |
| **DataStewardAgent** | Background-Freshness/Quality (06:00) | → erweitert auf Krypto-Quellen (Coin Metrics, Fear&Greed, Exchange-OHLCV); Anomalie-Checks für 24/7-Daten (Gaps, Wicks). |
| **SIXCryptoETPAgent** | SIX-Krypto-ETPs (kein Spot) | bleibt für das **SMI/3a-Anzeige-Universum**. V4 ergänzt **Spot-Krypto separat** — die alte „kein Spot"-Regel galt für 3a, nicht fürs neue Krypto-Kern-Universum. Klar trennen (3a ≠ Spot-Signale). |
| **ReportAgent** | HTML-Report/Dashboard | → erweitert um Signal-Explainability-Panel + Backtest-View + Indikator-Charts. |
| **MailAlertAgent** | Mail bei Anomalien | bleibt; ergänzt um Signal-Wechsel-Alerts (optional, opt-in). |

**Grundsatz:** Wir **bauen nicht neu, was funktioniert.** SteuerAgent-Pattern wird kopiert; Director und
DataSteward werden erweitert; nur die genuin neue Signal-Logik bekommt neue Agenten (§3).

---

## 3 · Neue Agenten (die buy/hold/sell tragen)

Alle neuen Agenten folgen dem **SteuerAgent-Pattern**: schmaler Zweck, Tools für alle Zahlen, Pydantic-Output,
deterministischer Fallback. Sie sitzen über der Signal-Engine (Schicht 1–3) und **interpretieren deren Outputs**.

### 3.1 TechnicalAnalystAgent  🟢 neu
**Zweck:** Liest die Indikator-Konsens-Outputs der Engine (MA/MACD/RSI/Bollinger/ATR) und formuliert die
technische Lesart + Konfidenz. **Rechnet nicht** — bekommt die Werte als Tool.
```
Tools: get_indicator_state(coin) -> {ma_cross, macd_hist, rsi, bb_pos, atr, consensus_vote}
       get_price_context(coin)   -> {trend_age_days, dist_to_high, dist_to_low}
Output (Pydantic): TechnicalView{
   coin, stance: Literal["BULLISH","NEUTRAL","BEARISH"],
   consensus: "3/3"|"2/3"|..., key_signals: list[str], confidence: 0..1, reasoning: str(≤3 Sätze)}
```

### 3.2 OnChainAnalystAgent  🟢 neu  (Krypto-Spezialvorteil)
**Zweck:** Interpretiert On-Chain-Health (MVRV-Z, Realized Cap, aktive Adressen) aus Coin Metrics — die
Information, die viele Retail-Modelle ignorieren.
```
Tools: get_onchain(coin) -> {mvrv_z, realized_cap_trend, active_addr_z, exchange_flow}
Output: OnChainView{coin, valuation: "CHEAP"|"FAIR"|"EXPENSIVE", network_health: ..., confidence, reasoning}
```

### 3.3 SentimentAnalystAgent (RAG)  🟢 neu  → erfüllt RAG-Vorgabe funktional
**Zweck:** Aggregiert News-/Fear&Greed-RAG zu einem Sentiment-Score, der als **Feature/Veto** in Schicht 2
einfliesst (nicht nur Anzeige).
```
Tools: search_news_rag(coin, k)  -> relevante News-Chunks (pgvector)
       get_fear_greed()          -> aktueller + 7d-Trend Index
Output: SentimentView{coin, score: -1..1, regime: "FEAR"|"NEUTRAL"|"GREED",
        news_surprise: bool, veto: bool, reasoning, sources: list[url]}  # sources = RAG-Nachweis
```

### 3.4 BullResearchAgent / BearResearchAgent  🟢 neu  (die Debatte)
**Zweck:** Erhalten alle Analyst-Views + Engine-Signal und argumentieren **bewusst einseitig** (Bull baut die
stärkste Kauf-These, Bear die stärkste Verkaufs-/Aussetz-These). Erzwingt Gegenprüfung.
```
Input: {TechnicalView, OnChainView, SentimentView, MacroRegime, engine_signal}
Output: BullCase{thesis, strongest_points: list[str], risks_acknowledged: list[str]}
        BearCase{thesis, strongest_points: list[str], counter_to_bull: list[str]}
```
**Regel:** Beide Cases werden **immer** im Audit-Trail gespeichert (keine Unterdrückung der Minderheit).

### 3.5 SignalDirector  🟠 Erweiterung des InvestmentDirector
**Zweck:** Synthese. Wägt Bull vs Bear + Engine-Signal + Risk-Veto zu **einem** Signal mit Größe ab.
```
Input: {BullCase, BearCase, engine_signal(dir+size), RiskVerdict}
Output (Pydantic): TradeSignal{
   coin, action: Literal["BUY","HOLD","SELL"],     # SELL = raus/cash, KEIN Shorting
   size_factor: 0..1.5,                            # aus Vol-Targeting (Engine)
   confidence: 0..1, rationale_by_layer: dict, audit_trail_id: UUID, disclaimer: str}
```
**Checkpoint:** bei confidence < 0.65 oder size-Sprung > Schwelle → HITL-Rückfrage (bestehendes Pattern).

### 3.6 RiskAgent  🟢 neu  (das Veto)
**Zweck:** Unabhängige Instanz prüft das vorgeschlagene Signal gegen Risikolimits — kann Bull-Konsens overrulen.
```
Tools: get_vol_forecast(coin), get_portfolio_exposure(), get_drawdown_state(), get_correlation_matrix()
Output: RiskVerdict{approve: bool, max_size: float, breaches: list[str], reasoning}
```
**Regel:** Portfolio-Exposure kommt aus dem **Store/Tool**, NIE aus LLM-Memory (epistemische-Halluzination-Schutz).

---

## 4 · Zusammenspiel — ein Signal-Durchlauf (Sequenz)

```
SignalDirector.run(coin):
  1. engine_signal      = SignalEngine.evaluate(coin)         # deterministisch: dir + size + sub-scores
  2. tech   = TechnicalAnalystAgent(engine_signal.indicators)
     onchain= OnChainAnalystAgent(coin)                       # parallel
     senti  = SentimentAnalystAgent(coin)                     # parallel (RAG)
     macro  = MacroRegimeAgent.regime()                       # gecached
  3. bull   = BullResearchAgent(tech, onchain, senti, macro, engine_signal)
     bear   = BearResearchAgent(tech, onchain, senti, macro, engine_signal)
  4. risk   = RiskAgent.assess(coin, engine_signal)           # Veto/Cap
  5. signal = synthesize(bull, bear, engine_signal, risk)     # → TradeSignal (Pydantic)
  6. if signal.confidence < 0.65: checkpoint(user)            # HITL
  7. persist(audit_trail: alle Views+Cases+Verdict); return signal
```

Alle Zahlen in Schritt 1/4 sind deterministisch. Die Agenten in 2/3 liefern *Interpretation + Sprache*. Schritt
5 ist regelgeleitet (gewichtete Synthese), nicht „LLM rät frei".

---

## 5 · Mapping auf Renold-Anforderungen

| Renold-Anforderung | Umsetzung V4-Agentic | 
|---|---|
| Multiple Agents kommunizieren | Director + 6 Analyst/Research/Risk-Agenten via typisierte Messages |
| Director-Mode | SignalDirector: Plan → Dispatch → Synthese |
| Agentic RAG | SentimentAnalystAgent (`search_news_rag`) → Feature/Veto |
| Echtes Tool-Use (kein if/elif) | Alle Agenten als LLM-Tool-Use-Loop; Zahlen aus Tools |
| Bull/Bear-Debatte / Mehr-Perspektiven | Bull- vs BearResearchAgent |
| Human-in-the-Loop | Checkpoint-Pattern (confidence/size) |
| Memory + Dazulernen | Trust-Scores (DataSteward) + Audit-Trail-Historie |
| Erklärbarkeit (STRESSS) | `rationale_by_layer` + Bull/Bear/Risk im Audit-Trail |
| Verlässlichkeit | Halluzinations-Guards, Fallback auf Engine-Signal |

---

## 6 · Agent-Tests (Pflicht, vor Merge)

1. **Halluzinations-Guard**: Jede Zahl im Agent-Output == zugehörige Engine-/Tool-Zahl (Diff < 1e-9). Sonst Fail.
2. **State-aus-Tool-Test**: RiskAgent liest Exposure aus gemocktem Store; Test stellt sicher, dass kein Wert aus
   dem Prompt/Memory „erfunden" wird.
3. **Minderheits-Schutz-Test**: Szenario mit 1 starkem Bear-Argument gegen 3 Bull → Audit-Trail enthält das
   Bear-Argument; RiskAgent kann overrulen.
4. **Fallback-Test**: LLM wirft Exception → `TradeSignal` kommt trotzdem (aus deterministischem Engine-Signal),
   `confidence` gesenkt, `disclaimer` gesetzt.
5. **Pydantic-Schema-Test**: Kein Agent gibt Freitext; alle Outputs schema-validiert.
6. **Checkpoint-Test**: confidence < 0.65 → genau ein HITL-Checkpoint, ≤ 4 Optionen (UI-Constraint).
7. **No-Shorting-Test**: `action == "SELL"` impliziert Ziel-Exposure 0 (cash), nie negativ.

---

## 7 · Bau-Reihenfolge (GSD)

Über GSD (`/gsd-discuss-phase` → `/gsd-plan-phase` → `/gsd-execute-phase` → `/gsd-verify-work`), frischer
Sub-Agent-Kontext pro Task. Voraussetzung: **Signal-Engine (V4-1) existiert** — die Agenten brauchen ihre Outputs.

```
Branch: feat/v4-agentic-signal-layer  (gegen develop; PR; CI grün; kein Direkt-Push)

Schritt 1  TechnicalAnalystAgent   (+ Tests)      ← SteuerAgent-Pattern kopieren
Schritt 2  OnChainAnalystAgent     (+ Tests)
Schritt 3  SentimentAnalystAgent   (+ Tests, RAG) ← erfüllt RAG-Vorgabe
Schritt 4  RiskAgent               (+ Tests)      ← State-aus-Tool
Schritt 5  Bull/BearResearchAgent  (+ Tests)
Schritt 6  SignalDirector-Synthese (+ Tests)      ← Erweiterung InvestmentDirector
Schritt 7  Integration Daten→Engine→Agenten→API   (+ E2E)
Schritt 8  Coverage-Gate ≥80 %, Halluzinations-Guards grün
```

**Modell-Routing (bestehende Konvention):** Synthese/Risk = Sonnet; Analyst-Agenten = Haiku (schnell, billig);
Architektur-Entscheide = Opus. Prompt-Caching für lange System-Prompts.

---

## 8 · Was die Agenten NICHT dürfen (Verbote)

❌ Einen Score, Preis, eine Position oder Kennzahl selbst „schätzen" statt aus Tool/Engine zu lesen
❌ Portfolio-Zustand aus dem Gesprächs-Memory ableiten (immer Store/Tool)
❌ Freitext direkt ins UI (alles Pydantic)
❌ Ein Shorting-Signal erzeugen (SELL = cash; kein negatives Exposure)
❌ Minderheits-Argumente aus dem Audit-Trail entfernen/wegmitteln
❌ Ein Signal ohne RiskAgent-Verdict ans UI geben
❌ Automatisch echte Trades ausführen (PRISMA ist Decision-Support; Mensch handelt selbst)

---

### Quellen
- TradingAgents: https://arxiv.org/abs/2412.20138 · https://github.com/TauricResearch/TradingAgents
- Agentic Trading / Grenzen: https://arxiv.org/html/2605.19337v1
- TradeTrap (Verlässlichkeit LLM-Trading-Agenten): https://arxiv.org/pdf/2512.02261
- TrustTrade (selektiver Konsens): https://arxiv.org/pdf/2603.22567
- Bestand: `PRISMA_V2_AGENTS.md`, `PRISMA_MultiAgent_Revised.md`

*PRISMA V4 Agent-Brief · 2026-06-21 · Andrea Petretta · FHNW BI Modul FS 2026*
